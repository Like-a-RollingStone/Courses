from __future__ import annotations

from collections.abc import Iterable
from typing import Callable

import numpy as np

try:
    from .instance import TSPInstance
    from .tour import Tour
except ImportError:
    from instance import TSPInstance  # type: ignore
    from tour import Tour  # type: ignore


_EPS = 1e-12


def or_opt(
    tour: Tour,
    instance: TSPInstance,
    max_iter: int | None = None,
    seed: int | np.random.Generator | None = None,
    max_improvements: int | None = None,
    segment_lengths: Iterable[int] = (1, 2, 3),
    callback: Callable[[int, Tour, float], None] | None = None,
) -> tuple[Tour, int]:
    """Run first-improvement Or-opt with segment lengths 1, 2 and 3.

    Or-opt relocates a short contiguous segment to another position in the
    tour. It complements 2-opt: 2-opt flips edge pairs, while Or-opt moves
    small city blocks without reversing their internal order.
    """

    _validate_tour(tour, instance)
    if max_iter is not None and max_iter < 0:
        raise ValueError("max_iter must be non-negative or None")
    if max_improvements is not None and max_improvements < 0:
        raise ValueError("max_improvements must be non-negative or None")

    n = instance.dimension
    if n <= 3:
        return tour.copy(), 0

    lengths = tuple(
        length for length in (int(value) for value in segment_lengths) if 1 <= length < n
    )
    if not lengths:
        return tour.copy(), 0

    cities = tour.cities.copy()
    rng = _make_rng(seed)
    improvements = 0
    passes = 0

    while max_iter is None or passes < max_iter:
        passes += 1
        accepted = False

        for segment_length in _ordered_values(lengths, rng):
            if max_improvements is not None and improvements >= max_improvements:
                break

            for start in _ordered_values(range(0, n - segment_length + 1), rng):
                if max_improvements is not None and improvements >= max_improvements:
                    break

                for insert_after in _ordered_values(range(n), rng):
                    if max_improvements is not None and improvements >= max_improvements:
                        break
                    if _invalid_relocation(start, segment_length, insert_after, n):
                        continue

                    delta = _delta_relocate_segment(
                        cities,
                        start,
                        segment_length,
                        insert_after,
                        instance.dist_matrix,
                    )
                    if delta < -_EPS:
                        _relocate_segment(cities, start, segment_length, insert_after)
                        improvements += 1
                        accepted = True
                        if callback is not None:
                            improved_tour = Tour(cities.copy())
                            callback(
                                improvements,
                                improved_tour,
                                improved_tour.length(instance),
                            )
                        break

                if accepted:
                    break
            if accepted:
                break

        if max_improvements is not None and improvements >= max_improvements:
            break
        if not accepted:
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


def _ordered_values(
    values: Iterable[int],
    rng: np.random.Generator | None,
) -> list[int]:
    ordered = [int(value) for value in values]
    if rng is None or len(ordered) <= 1:
        return ordered
    order = rng.permutation(len(ordered))
    return [ordered[int(idx)] for idx in order]


def _invalid_relocation(
    start: int,
    segment_length: int,
    insert_after: int,
    n: int,
) -> bool:
    end = start + segment_length - 1
    if start <= insert_after <= end:
        return True
    return insert_after == (start - 1) % n


def _delta_relocate_segment(
    cities: list[int],
    start: int,
    segment_length: int,
    insert_after: int,
    dist_matrix: np.ndarray,
) -> float:
    n = len(cities)
    end = start + segment_length - 1

    a = cities[start - 1] if start > 0 else cities[-1]
    b = cities[start]
    c = cities[end]
    d = cities[(end + 1) % n]
    e = cities[insert_after]
    f = cities[(insert_after + 1) % n]

    removed = dist_matrix[a, b] + dist_matrix[c, d] + dist_matrix[e, f]
    added = dist_matrix[a, d] + dist_matrix[e, b] + dist_matrix[c, f]
    return float(added - removed)


def _relocate_segment(
    cities: list[int],
    start: int,
    segment_length: int,
    insert_after: int,
) -> None:
    segment = cities[start : start + segment_length]
    remaining = cities[:start] + cities[start + segment_length :]

    if insert_after < start:
        insert_pos = insert_after + 1
    else:
        insert_pos = insert_after - segment_length + 1

    cities[:] = remaining[:insert_pos] + segment + remaining[insert_pos:]
