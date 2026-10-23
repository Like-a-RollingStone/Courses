from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from time import perf_counter
from typing import Callable

import numpy as np

try:
    from .baselines import nearest_neighbor
    from .instance import TSPInstance
    from .tour import Tour
except ImportError:
    from baselines import nearest_neighbor  # type: ignore
    from instance import TSPInstance  # type: ignore
    from tour import Tour  # type: ignore


_EPS = 1e-12


def two_opt_basic(
    tour: Tour,
    instance: TSPInstance,
    max_iter: int | None = None,
    seed: int | np.random.Generator | None = None,
    max_improvements: int | None = None,
) -> tuple[Tour, int]:
    """Run first-improvement 2-opt by scanning all edge pairs."""

    _validate_tour(tour, instance)
    if max_iter is not None and max_iter < 0:
        raise ValueError("max_iter must be non-negative or None")
    if max_improvements is not None and max_improvements < 0:
        raise ValueError("max_improvements must be non-negative or None")

    n = instance.dimension
    cities = tour.cities.copy()
    rng = _make_rng(seed)
    improvements = 0
    passes = 0

    while max_iter is None or passes < max_iter:
        passes += 1
        improved_this_pass = False

        for i, j in _edge_pair_order(n, rng):
            if max_improvements is not None and improvements >= max_improvements:
                break
            delta = _delta_edge_pair(cities, i, j, instance.dist_matrix)
            if delta < -_EPS:
                _reverse_after_edge_pair(cities, i, j)
                improvements += 1
                improved_this_pass = True

        if max_improvements is not None and improvements >= max_improvements:
            break
        if not improved_this_pass:
            break

    return Tour(cities), improvements


def two_opt_dlb(
    tour: Tour,
    instance: TSPInstance,
    max_iter: int | None = None,
    seed: int | np.random.Generator | None = None,
    max_improvements: int | None = None,
    callback: Callable[[int, Tour, float], None] | None = None,
) -> tuple[Tour, int]:
    """Run 2-opt with Don't Look Bits acceleration."""

    _validate_tour(tour, instance)
    if max_iter is not None and max_iter < 0:
        raise ValueError("max_iter must be non-negative or None")
    if max_improvements is not None and max_improvements < 0:
        raise ValueError("max_improvements must be non-negative or None")

    n = instance.dimension
    cities = tour.cities.copy()
    dont_look = np.zeros(n, dtype=bool)
    rng = _make_rng(seed)
    improvements = 0
    passes = 0

    while max_iter is None or passes < max_iter:
        passes += 1
        improved_this_pass = False
        skipped_this_pass = False

        for i in _position_order(n, rng):
            if max_improvements is not None and improvements >= max_improvements:
                break
            city = cities[i]
            if dont_look[city]:
                skipped_this_pass = True
                continue

            found_improvement = False
            for j in _candidate_edge_order(n, i, rng):
                if max_improvements is not None and improvements >= max_improvements:
                    break
                left, right = (i, j) if i < j else (j, i)
                delta = _delta_edge_pair(cities, left, right, instance.dist_matrix)
                if delta < -_EPS:
                    impacted = _impacted_cities(cities, left, right)
                    _reverse_after_edge_pair(cities, left, right)
                    dont_look[impacted] = False
                    improvements += 1
                    improved_this_pass = True
                    found_improvement = True
                    if callback is not None:
                        improved_tour = Tour(cities.copy())
                        callback(
                            improvements,
                            improved_tour,
                            improved_tour.length(instance),
                        )

            if not found_improvement:
                dont_look[city] = True

        if max_improvements is not None and improvements >= max_improvements:
            break
        if not improved_this_pass:
            if skipped_this_pass:
                dont_look[:] = False
                continue
            break

    return Tour(cities), improvements


def _validate_tour(tour: Tour, instance: TSPInstance) -> None:
    if not tour.is_valid(instance.dimension):
        raise ValueError(
            f"tour must be a valid permutation of 0..{instance.dimension - 1}"
        )


def _make_rng(
    seed: int | np.random.Generator | None,
) -> np.random.Generator | None:
    if seed is None:
        return None
    if isinstance(seed, np.random.Generator):
        return seed
    return np.random.default_rng(seed)


def _edge_pair_order(
    n: int, rng: np.random.Generator | None
) -> list[tuple[int, int]]:
    pairs = [(i, j) for i in range(n - 1) for j in range(i + 1, n)]
    if rng is None or len(pairs) <= 1:
        return pairs
    order = rng.permutation(len(pairs))
    return [pairs[int(idx)] for idx in order]


def _position_order(n: int, rng: np.random.Generator | None) -> Iterable[int]:
    if rng is None:
        return range(n)
    return rng.permutation(n).astype(int).tolist()


def _candidate_edge_order(
    n: int, i: int, rng: np.random.Generator | None
) -> Iterable[int]:
    if rng is None:
        return range(i + 1, n)
    candidates = list(range(i + 1, n))
    if len(candidates) <= 1:
        return candidates
    order = rng.permutation(len(candidates))
    return [candidates[int(idx)] for idx in order]


def _delta_edge_pair(
    cities: list[int], i: int, j: int, dist_matrix: np.ndarray
) -> float:
    if i == j:
        return 0.0
    if i > j:
        i, j = j, i

    n = len(cities)
    a = cities[i]
    b = cities[(i + 1) % n]
    c = cities[j]
    d = cities[(j + 1) % n]
    removed = dist_matrix[a, b] + dist_matrix[c, d]
    added = dist_matrix[a, c] + dist_matrix[b, d]
    return float(added - removed)


def _reverse_after_edge_pair(cities: list[int], i: int, j: int) -> None:
    if i > j:
        i, j = j, i
    start = i + 1
    end = j
    if start < end:
        cities[start : end + 1] = reversed(cities[start : end + 1])


def _impacted_cities(cities: list[int], i: int, j: int) -> np.ndarray:
    if i > j:
        i, j = j, i
    n = len(cities)
    impacted = cities[i : j + 1] + [cities[(j + 1) % n]]
    return np.array(impacted, dtype=np.int64)


def _tsplib_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "tsplib" / filename


def _run_berlin52_demo() -> None:
    path = _tsplib_path("berlin52.tsp")
    if not path.exists():
        print(f"berlin52.tsp not found: {path}")
        return

    instance = TSPInstance.load_tsplib(path)
    initial = nearest_neighbor(instance, start=0)
    initial_length = initial.length(instance)
    print(f"berlin52 nearest_neighbor length: {initial_length:.0f}")

    start_time = perf_counter()
    basic_tour, basic_improvements = two_opt_basic(initial, instance)
    basic_time = perf_counter() - start_time
    basic_length = basic_tour.length(instance)

    start_time = perf_counter()
    dlb_tour, dlb_improvements = two_opt_dlb(initial, instance)
    dlb_time = perf_counter() - start_time
    dlb_length = dlb_tour.length(instance)

    same_result = abs(basic_length - dlb_length) < _EPS
    in_expected_range = 7700 <= dlb_length <= 7900

    print(
        "two_opt_basic: "
        f"length={basic_length:.0f}, improvements={basic_improvements}, "
        f"time={basic_time:.4f}s"
    )
    print(
        "two_opt_dlb: "
        f"length={dlb_length:.0f}, improvements={dlb_improvements}, "
        f"time={dlb_time:.4f}s"
    )
    print(f"same result: {same_result}")
    print(f"DLB speedup: {basic_time / dlb_time:.2f}x" if dlb_time > 0 else "DLB speedup: inf")
    print(f"final length in [7700, 7900]: {in_expected_range}")


if __name__ == "__main__":
    _run_berlin52_demo()
