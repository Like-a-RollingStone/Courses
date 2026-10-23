from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    from .instance import TSPInstance
    from .tour import Tour
except ImportError:
    from instance import TSPInstance  # type: ignore
    from tour import Tour  # type: ignore


def nearest_neighbor(
    instance: TSPInstance, start: int = 0, seed: int | None = None
) -> Tour:
    """Build a TSP tour by repeatedly visiting the nearest unvisited city."""

    n = instance.dimension
    if not 0 <= start < n:
        raise ValueError(f"start must be in [0, {n - 1}], got {start}")

    rng = np.random.default_rng(seed) if seed is not None else None
    unvisited = np.ones(n, dtype=bool)
    unvisited[start] = False
    cities = [start]
    current = start

    while len(cities) < n:
        candidates = np.flatnonzero(unvisited)
        distances = instance.dist_matrix[current, candidates]
        min_distance = distances.min()
        nearest = candidates[distances == min_distance]
        if rng is None:
            next_city = int(nearest[0])
        else:
            next_city = int(rng.choice(nearest))

        cities.append(next_city)
        unvisited[next_city] = False
        current = next_city

    return Tour(cities)


def held_karp(instance: TSPInstance, force: bool = False) -> Tour:
    """Solve TSP exactly with Held-Karp bitmask dynamic programming."""

    n = instance.dimension
    if n > 20:
        gb = n * (2**n) * 8 / 1e9
        raise ValueError(
            "held_karp has O(n*2^n) memory cost; "
            f"n={n} would require about {gb:.1f} GB"
        )
    if n > 18 and not force:
        mb = n * (2**n) * 8 / 1e6
        raise ValueError(
            "held_karp is exact but memory-heavy; "
            f"n={n} requires about {mb:.0f} MB. "
            "Pass force=True to run explicitly."
        )
    if n == 1:
        return Tour([0])

    dist = instance.dist_matrix
    num_masks = 1 << n
    start_mask = 1
    full_mask = num_masks - 1
    dp = np.full((num_masks, n), np.inf, dtype=np.float64)
    parent = np.full((num_masks, n), -1, dtype=np.int16)
    dp[start_mask, 0] = 0.0

    for mask in range(num_masks):
        if (mask & start_mask) == 0:
            continue

        row = dp[mask]
        if not np.isfinite(row).any():
            continue

        unvisited_mask = full_mask ^ mask
        while unvisited_mask:
            next_bit = unvisited_mask & -unvisited_mask
            next_city = next_bit.bit_length() - 1
            new_mask = mask | next_bit
            costs = row + dist[:, next_city]
            prev_city = int(np.argmin(costs))
            best_cost = float(costs[prev_city])

            dp[new_mask, next_city] = best_cost
            parent[new_mask, next_city] = prev_city
            unvisited_mask ^= next_bit

    final_costs = dp[full_mask] + dist[:, 0]
    last_city = int(np.argmin(final_costs))
    if not np.isfinite(final_costs[last_city]):
        raise ValueError("failed to construct a finite Held-Karp tour")

    cities = [0] * n
    mask = full_mask
    current = last_city
    for position in range(n - 1, 0, -1):
        cities[position] = current
        previous = int(parent[mask, current])
        if previous < 0:
            raise ValueError("failed to reconstruct Held-Karp tour")
        mask ^= 1 << current
        current = previous
    cities[0] = 0

    return Tour(cities)


def _tsplib_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "tsplib" / filename


def _run_nearest_neighbor_demo() -> None:
    path = _tsplib_path("berlin52.tsp")
    if not path.exists():
        print(f"berlin52.tsp not found: {path}")
        return

    instance = TSPInstance.load_tsplib(path)
    tour = nearest_neighbor(instance, start=0)
    print(f"berlin52 nearest_neighbor length: {tour.length(instance):.0f}")


def _run_held_karp_demo() -> None:
    path = _tsplib_path("burma14.tsp")
    if not path.exists():
        print(f"burma14.tsp not found: {path}")
        return

    instance = TSPInstance.load_tsplib(path)
    tour = held_karp(instance)
    length = tour.length(instance)
    print(f"burma14 held_karp length: {length:.0f}")
    print(f"matches known optimum 3323: {round(length) == 3323}")


if __name__ == "__main__":
    _run_nearest_neighbor_demo()
    _run_held_karp_demo()
