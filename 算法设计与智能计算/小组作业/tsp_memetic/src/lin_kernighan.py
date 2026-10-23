from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

try:
    from .instance import TSPInstance
    from .or_opt import or_opt
    from .tour import Tour
    from .two_opt import two_opt_dlb
except ImportError:
    from instance import TSPInstance  # type: ignore
    from or_opt import or_opt  # type: ignore
    from tour import Tour  # type: ignore
    from two_opt import two_opt_dlb  # type: ignore


Edge = tuple[int, int]
_EPS = 1e-12


@dataclass(frozen=True)
class _LKMove:
    gain: float
    removed: tuple[Edge, ...]
    added: tuple[Edge, ...]
    tour: Tour


def lin_kernighan(
    tour: Tour,
    instance: TSPInstance,
    max_iter: int | None = None,
    max_depth: int = 5,
    candidate_k: int | None = 20,
    backtracking_width: int = 5,
    seed: int | np.random.Generator | None = None,
    max_improvements: int | None = None,
    fixed_edges: set[Edge] | None = None,
    callback: Callable[[int, Tour, float], None] | None = None,
) -> tuple[Tour, int]:
    """Run a bounded classic Lin-Kernighan variable-depth edge exchange.

    This implements the LK core idea used in the Merz/Freisleben-style MA:
    build a sequential exchange by alternating removed tour edges X and added
    non-tour edges Y, keep only positive partial-gain branches, backtrack over
    promising alternatives, and accept the best improving closure found.
    It is intentionally not an LKH implementation; LKH adds alpha-nearness
    candidate sets, patching, and more specialized data structures.
    """

    _validate_lk_params(
        tour,
        instance,
        max_iter,
        max_depth,
        candidate_k,
        backtracking_width,
        max_improvements,
    )
    rng = _make_rng(seed)
    current = tour.copy()
    improvements = 0
    passes = 0
    fixed = _normalize_edges(fixed_edges or set())
    candidates = _candidate_sets(instance, candidate_k)

    while max_iter is None or passes < max_iter:
        if max_improvements is not None and improvements >= max_improvements:
            break
        passes += 1
        move = _find_best_lk_move(
            current,
            instance,
            candidates,
            max_depth=max_depth,
            backtracking_width=backtracking_width,
            fixed_edges=fixed,
            rng=rng,
        )
        if move is None or move.gain <= _EPS:
            break

        current = move.tour.copy()
        improvements += 1
        if callback is not None:
            callback(improvements, current.copy(), current.length(instance))

    return current.copy(), improvements


def lin_kernighan_style(
    tour: Tour,
    instance: TSPInstance,
    max_iter: int = 3,
    seed: int | np.random.Generator | None = None,
    max_improvements: int | None = None,
    callback: Callable[[int, Tour, float], None] | None = None,
) -> tuple[Tour, int]:
    """Run a compact LK-style strong local search.

    This is not a full Lin-Kernighan-Helsgaun implementation. It is a practical
    project-level proxy that repeatedly combines edge-exchange 2-opt and
    short-segment Or-opt until no further improvement is found. The interface is
    intentionally compatible with the other local-search functions so experiments
    can compare weak and strong local-search regimes.
    """

    if max_iter < 0:
        raise ValueError("max_iter must be non-negative")
    if max_improvements is not None and max_improvements < 0:
        raise ValueError("max_improvements must be non-negative or None")

    rng = _make_rng(seed)
    current = tour.copy()
    improvements = 0

    for _ in range(max_iter):
        before = current.length(instance)
        remaining = _remaining(max_improvements, improvements)
        if remaining == 0:
            break
        current, two_count = two_opt_dlb(
            current,
            instance,
            seed=rng,
            max_improvements=remaining,
            callback=_offset_callback(callback, improvements),
        )
        improvements += two_count

        remaining = _remaining(max_improvements, improvements)
        if remaining == 0:
            break
        current, or_count = or_opt(
            current,
            instance,
            seed=rng,
            max_improvements=remaining,
            callback=_offset_callback(callback, improvements),
        )
        improvements += or_count

        after = current.length(instance)
        if after >= before - 1e-12:
            break

    return current.copy(), improvements


def _find_best_lk_move(
    tour: Tour,
    instance: TSPInstance,
    candidates: dict[int, list[int]],
    max_depth: int,
    backtracking_width: int,
    fixed_edges: set[Edge],
    rng: np.random.Generator | None,
) -> _LKMove | None:
    cities = tour.cities
    old_edges = _tour_edges(cities)
    neighbors = _tour_neighbors(cities)
    old_length = tour.length(instance)
    best: _LKMove | None = None

    for t1 in _ordered(cities, rng):
        for t2 in _ordered(neighbors[t1], rng):
            first_removed = _edge(t1, t2)
            if first_removed in fixed_edges:
                continue
            gain = float(instance.dist_matrix[t1, t2])
            move = _search_lk_branch(
                t1=t1,
                last=t2,
                path=(t1, t2),
                removed=(first_removed,),
                added=(),
                partial_gain=gain,
                depth=1,
                old_edges=old_edges,
                neighbors=neighbors,
                candidates=candidates,
                cities=cities,
                old_length=old_length,
                instance=instance,
                max_depth=max_depth,
                backtracking_width=backtracking_width,
                fixed_edges=fixed_edges,
                rng=rng,
                best=best,
            )
            if move is not None and (best is None or move.gain > best.gain):
                best = move

    return best


def _search_lk_branch(
    *,
    t1: int,
    last: int,
    path: tuple[int, ...],
    removed: tuple[Edge, ...],
    added: tuple[Edge, ...],
    partial_gain: float,
    depth: int,
    old_edges: set[Edge],
    neighbors: dict[int, tuple[int, int]],
    candidates: dict[int, list[int]],
    cities: list[int],
    old_length: float,
    instance: TSPInstance,
    max_depth: int,
    backtracking_width: int,
    fixed_edges: set[Edge],
    rng: np.random.Generator | None,
    best: _LKMove | None,
) -> _LKMove | None:
    dist = instance.dist_matrix
    path_set = set(path)
    y_choices: list[tuple[float, int, Edge]] = []

    for t_next in candidates[last]:
        y_edge = _edge(last, t_next)
        gain_after_add = partial_gain - float(dist[last, t_next])
        if (
            t_next == t1
            or t_next in path_set
            or y_edge in old_edges
            or y_edge in added
            or gain_after_add <= _EPS
        ):
            continue
        y_choices.append((gain_after_add, t_next, y_edge))

    y_choices.sort(key=lambda item: item[0], reverse=True)
    y_choices = y_choices[:backtracking_width]
    if rng is not None and len(y_choices) > 1:
        # Keep good choices first, but randomize ties/nearly equivalent branches.
        y_choices = sorted(
            y_choices,
            key=lambda item: (-round(item[0], 10), int(rng.integers(0, 1_000_000))),
        )

    for gain_after_add, t_odd, y_edge in y_choices:
        x_choices: list[tuple[float, int, Edge]] = []
        for t_even in neighbors[t_odd]:
            x_edge = _edge(t_odd, t_even)
            if (
                t_even == t1
                or t_even in path_set
                or x_edge in removed
                or x_edge in fixed_edges
            ):
                continue
            gain_after_remove = gain_after_add + float(dist[t_odd, t_even])
            if gain_after_remove <= _EPS:
                continue
            x_choices.append((gain_after_remove, t_even, x_edge))

        x_choices.sort(key=lambda item: item[0], reverse=True)
        x_choices = x_choices[:backtracking_width]

        for gain_after_remove, t_even, x_edge in x_choices:
            next_removed = removed + (x_edge,)
            next_added = added + (y_edge,)
            closing_edge = _edge(t_even, t1)
            if closing_edge not in old_edges and closing_edge not in next_added:
                total_gain = gain_after_remove - float(dist[t_even, t1])
                if total_gain > _EPS:
                    move = _make_lk_move(
                        old_edges=old_edges,
                        removed=next_removed,
                        added=next_added + (closing_edge,),
                        cities=cities,
                        old_length=old_length,
                        instance=instance,
                    )
                    if move is not None and (best is None or move.gain > best.gain):
                        best = move

            if depth < max_depth:
                move = _search_lk_branch(
                    t1=t1,
                    last=t_even,
                    path=path + (t_odd, t_even),
                    removed=next_removed,
                    added=next_added,
                    partial_gain=gain_after_remove,
                    depth=depth + 1,
                    old_edges=old_edges,
                    neighbors=neighbors,
                    candidates=candidates,
                    cities=cities,
                    old_length=old_length,
                    instance=instance,
                    max_depth=max_depth,
                    backtracking_width=backtracking_width,
                    fixed_edges=fixed_edges,
                    rng=rng,
                    best=best,
                )
                if move is not None and (best is None or move.gain > best.gain):
                    best = move

    return best


def _make_lk_move(
    *,
    old_edges: set[Edge],
    removed: tuple[Edge, ...],
    added: tuple[Edge, ...],
    cities: list[int],
    old_length: float,
    instance: TSPInstance,
) -> _LKMove | None:
    new_edges = set(old_edges)
    for edge in removed:
        new_edges.discard(edge)
    new_edges.update(added)

    new_tour = _tour_from_edges(new_edges, cities)
    if new_tour is None:
        return None

    gain = old_length - new_tour.length(instance)
    if gain <= _EPS:
        return None
    return _LKMove(gain=gain, removed=removed, added=added, tour=new_tour)


def _tour_from_edges(edges: set[Edge], cities: list[int]) -> Tour | None:
    if len(edges) != len(cities):
        return None

    adjacency: dict[int, list[int]] = {city: [] for city in cities}
    for a, b in edges:
        if a == b or a not in adjacency or b not in adjacency:
            return None
        adjacency[a].append(b)
        adjacency[b].append(a)

    if any(len(neighbors) != 2 for neighbors in adjacency.values()):
        return None

    start = cities[0]
    current = start
    previous: int | None = None
    tour = [start]
    seen = {start}

    while True:
        first, second = adjacency[current]
        next_city = first if first != previous else second
        if next_city == start:
            break
        if next_city in seen:
            return None
        tour.append(next_city)
        seen.add(next_city)
        previous, current = current, next_city

    if len(tour) != len(cities):
        return None
    return Tour(tour)


def _candidate_sets(
    instance: TSPInstance,
    candidate_k: int | None,
) -> dict[int, list[int]]:
    n = instance.dimension
    limit = n - 1 if candidate_k is None else min(candidate_k, n - 1)
    candidates: dict[int, list[int]] = {}
    for city in range(n):
        ordered = np.argsort(instance.dist_matrix[city], kind="stable").astype(int)
        nearest = [int(other) for other in ordered if int(other) != city]
        candidates[city] = nearest[:limit]
    return candidates


def _tour_edges(cities: list[int]) -> set[Edge]:
    return {_edge(city, cities[(idx + 1) % len(cities)]) for idx, city in enumerate(cities)}


def _tour_neighbors(cities: list[int]) -> dict[int, tuple[int, int]]:
    n = len(cities)
    return {
        city: (cities[(idx - 1) % n], cities[(idx + 1) % n])
        for idx, city in enumerate(cities)
    }


def _normalize_edges(edges: set[Edge]) -> set[Edge]:
    return {_edge(a, b) for a, b in edges}


def _edge(a: int, b: int) -> Edge:
    return (a, b) if a <= b else (b, a)


def _ordered(values, rng: np.random.Generator | None) -> list[int]:
    items = [int(value) for value in values]
    if rng is None or len(items) <= 1:
        return items
    order = rng.permutation(len(items)).astype(int).tolist()
    return [items[idx] for idx in order]


def _validate_lk_params(
    tour: Tour,
    instance: TSPInstance,
    max_iter: int | None,
    max_depth: int,
    candidate_k: int | None,
    backtracking_width: int,
    max_improvements: int | None,
) -> None:
    if not tour.is_valid(instance.dimension):
        raise ValueError(
            f"tour must be a valid permutation of 0..{instance.dimension - 1}"
        )
    if max_iter is not None and max_iter < 0:
        raise ValueError("max_iter must be non-negative or None")
    if max_depth < 2:
        raise ValueError("max_depth must be at least 2")
    if candidate_k is not None and candidate_k <= 0:
        raise ValueError("candidate_k must be positive or None")
    if backtracking_width <= 0:
        raise ValueError("backtracking_width must be positive")
    if max_improvements is not None and max_improvements < 0:
        raise ValueError("max_improvements must be non-negative or None")


def _remaining(max_improvements: int | None, improvements: int) -> int | None:
    if max_improvements is None:
        return None
    return max(0, max_improvements - improvements)


def _offset_callback(
    callback: Callable[[int, Tour, float], None] | None,
    offset: int,
) -> Callable[[int, Tour, float], None] | None:
    if callback is None:
        return None

    def wrapped(step: int, tour: Tour, length: float) -> None:
        callback(offset + step, tour, length)

    return wrapped


def _make_rng(
    seed: int | np.random.Generator | None,
) -> np.random.Generator | None:
    if seed is None:
        return None
    if isinstance(seed, np.random.Generator):
        return seed
    return np.random.default_rng(seed)
