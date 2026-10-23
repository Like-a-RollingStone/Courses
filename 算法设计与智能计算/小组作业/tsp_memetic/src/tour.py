from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from pathlib import Path
from typing import TYPE_CHECKING, overload

import numpy as np

if TYPE_CHECKING:
    from .instance import TSPInstance


@dataclass
class Tour:
    """A permutation of city indices using zero-based indexing."""

    cities: list[int]

    def __post_init__(self) -> None:
        self.cities = [int(city) for city in self.cities]

    def length(self, instance: "TSPInstance") -> float:
        """Return the closed tour length for the given instance."""

        n = instance.dimension
        if not self.is_valid(n):
            raise ValueError(f"tour must be a valid permutation of 0..{n - 1}")

        dist = instance.dist_matrix
        total = 0.0
        for idx, city in enumerate(self.cities):
            next_city = self.cities[(idx + 1) % n]
            total += dist[city, next_city]
        return float(total)

    def delta_two_opt(self, i: int, j: int, instance: "TSPInstance") -> float:
        """Return the O(1) length change after reversing cities[i:j + 1]."""

        n = len(self.cities)
        if n != instance.dimension:
            raise ValueError(
                f"tour length {n} does not match instance dimension {instance.dimension}"
            )
        if not (0 <= i < n and 0 <= j < n):
            raise IndexError("2-opt indices out of range")
        if i > j:
            i, j = j, i
        if i == j or (i == 0 and j == n - 1):
            return 0.0

        a = self.cities[i - 1]
        b = self.cities[i]
        c = self.cities[j]
        d = self.cities[(j + 1) % n]
        dist = instance.dist_matrix
        removed = dist[a, b] + dist[c, d]
        added = dist[a, c] + dist[b, d]
        return float(added - removed)

    def copy(self) -> "Tour":
        return Tour(self.cities.copy())

    def is_valid(self, n: int) -> bool:
        if len(self.cities) != n:
            return False
        if not all(
            isinstance(city, Integral) and not isinstance(city, bool)
            for city in self.cities
        ):
            return False
        return set(self.cities) == set(range(n))

    def __len__(self) -> int:
        return len(self.cities)

    @overload
    def __getitem__(self, index: int) -> int:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[int]:
        ...

    def __getitem__(self, index: int | slice) -> int | list[int]:
        return self.cities[index]

    def __repr__(self) -> str:
        return f"Tour(cities={self.cities!r})"


def _berlin52_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "tsplib" / "berlin52.tsp"


def _load_instance(filepath: Path) -> "TSPInstance":
    try:
        from .instance import TSPInstance
    except ImportError:
        from instance import TSPInstance  # type: ignore

    return TSPInstance.load_tsplib(filepath)


def _run_demo() -> None:
    path = _berlin52_path()
    if not path.exists():
        print(f"berlin52.tsp not found: {path}")
        print("Please put berlin52.tsp under data/tsplib/ and run again.")
        return

    instance = _load_instance(path)
    print(instance)

    rng = np.random.default_rng(0)
    tour = Tour(rng.permutation(instance.dimension).tolist())
    print(f"random tour: {tour}")
    print(f"random tour valid: {tour.is_valid(instance.dimension)}")
    print(f"random tour length: {tour.length(instance):.0f}")

    i, j = 1, instance.dimension - 2
    old_length = tour.length(instance)
    delta = tour.delta_two_opt(i, j, instance)
    new_cities = tour.cities.copy()
    new_cities[i : j + 1] = reversed(new_cities[i : j + 1])
    actual_delta = Tour(new_cities).length(instance) - old_length
    print(f"delta_two_opt({i}, {j}): {delta:.0f}")
    print(f"actual delta: {actual_delta:.0f}")
    print(f"delta correct: {abs(delta - actual_delta) < 1e-9}")


if __name__ == "__main__":
    _run_demo()
