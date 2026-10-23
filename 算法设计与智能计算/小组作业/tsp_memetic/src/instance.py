from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class TSPInstance:
    """A TSPLIB-style Euclidean TSP instance."""

    name: str
    dimension: int
    coords: np.ndarray
    dist_matrix: np.ndarray

    def __post_init__(self) -> None:
        coords = np.asarray(self.coords, dtype=np.float64)
        dist_matrix = np.asarray(self.dist_matrix, dtype=np.float64)

        if self.dimension <= 0:
            raise ValueError("dimension must be positive")
        if coords.shape != (self.dimension, 2):
            raise ValueError(
                f"coords must have shape ({self.dimension}, 2), got {coords.shape}"
            )
        if dist_matrix.shape != (self.dimension, self.dimension):
            raise ValueError(
                "dist_matrix must have shape "
                f"({self.dimension}, {self.dimension}), got {dist_matrix.shape}"
            )

        object.__setattr__(self, "coords", coords)
        object.__setattr__(self, "dist_matrix", dist_matrix)

    @classmethod
    def load_tsplib(cls, filepath: str | Path) -> "TSPInstance":
        """Load a standard TSPLIB EUC_2D instance."""

        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(path)

        metadata: dict[str, str] = {}
        coords_by_id: dict[int, tuple[float, float]] = {}
        in_coord_section = False

        with path.open("r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line:
                    continue

                upper_line = line.upper()
                if upper_line == "EOF":
                    break
                if upper_line == "NODE_COORD_SECTION":
                    in_coord_section = True
                    continue

                if in_coord_section:
                    parts = line.split()
                    if len(parts) < 3:
                        raise ValueError(f"invalid coordinate line: {line!r}")
                    node_id = int(parts[0])
                    coords_by_id[node_id] = (float(parts[1]), float(parts[2]))
                else:
                    key, value = _parse_header_line(line)
                    if key:
                        metadata[key] = value

        name = metadata.get("NAME", path.stem)
        dimension = _required_int(metadata, "DIMENSION")
        edge_weight_type = metadata.get("EDGE_WEIGHT_TYPE", "").upper()
        if edge_weight_type not in {"EUC_2D", "GEO"}:
            raise ValueError(
                "only EDGE_WEIGHT_TYPE: EUC_2D and GEO are supported, "
                f"got {edge_weight_type or 'missing'}"
            )

        expected_ids = set(range(1, dimension + 1))
        actual_ids = set(coords_by_id)
        if actual_ids != expected_ids:
            missing = sorted(expected_ids - actual_ids)
            extra = sorted(actual_ids - expected_ids)
            raise ValueError(
                "node ids must be exactly 1..DIMENSION; "
                f"missing={missing[:5]}, extra={extra[:5]}"
            )

        coords = np.array(
            [coords_by_id[node_id] for node_id in range(1, dimension + 1)],
            dtype=np.float64,
        )
        if edge_weight_type == "EUC_2D":
            dist_matrix = _euc_2d_distance_matrix(coords)
        else:
            dist_matrix = _geo_distance_matrix(coords)
        return cls(
            name=name,
            dimension=dimension,
            coords=coords,
            dist_matrix=dist_matrix,
        )

    def __repr__(self) -> str:
        return f"TSPInstance(name={self.name!r}, dimension={self.dimension})"


def _parse_header_line(line: str) -> tuple[str, str]:
    if ":" in line:
        key, value = line.split(":", 1)
    else:
        parts = line.split(maxsplit=1)
        key = parts[0]
        value = parts[1] if len(parts) > 1 else ""
    return key.strip().upper(), value.strip()


def _required_int(metadata: dict[str, str], key: str) -> int:
    value = metadata.get(key)
    if value is None:
        raise ValueError(f"missing required TSPLIB field: {key}")
    return int(value)


def _euc_2d_distance_matrix(coords: np.ndarray) -> np.ndarray:
    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
    euclidean = np.sqrt(np.sum(diff * diff, axis=2))
    dist_matrix = np.floor(euclidean + 0.5).astype(np.float64)
    np.fill_diagonal(dist_matrix, 0.0)
    return dist_matrix


def _geo_distance_matrix(coords: np.ndarray) -> np.ndarray:
    radians = _geo_coords_to_radians(coords)
    lat = radians[:, 0]
    lon = radians[:, 1]
    q1 = np.cos(lon[:, np.newaxis] - lon[np.newaxis, :])
    q2 = np.cos(lat[:, np.newaxis] - lat[np.newaxis, :])
    q3 = np.cos(lat[:, np.newaxis] + lat[np.newaxis, :])
    inner = 0.5 * ((1.0 + q1) * q2 - (1.0 - q1) * q3)
    central_angle = np.arccos(np.clip(inner, -1.0, 1.0))
    dist_matrix = np.floor(6378.388 * central_angle + 1.0).astype(np.float64)
    np.fill_diagonal(dist_matrix, 0.0)
    return dist_matrix


def _geo_coords_to_radians(coords: np.ndarray) -> np.ndarray:
    degrees = np.floor(coords)
    minutes = coords - degrees
    return np.pi * (degrees + 5.0 * minutes / 3.0) / 180.0


def _berlin52_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "tsplib" / "berlin52.tsp"


def _run_demo() -> None:
    path = _berlin52_path()
    if not path.exists():
        print(f"berlin52.tsp not found: {path}")
        print("Please put berlin52.tsp under data/tsplib/ and run again.")
        return

    instance = TSPInstance.load_tsplib(path)
    print(instance)
    print(f"coords shape: {instance.coords.shape}")
    print(f"dist_matrix shape: {instance.dist_matrix.shape}")

    try:
        from .tour import Tour
    except ImportError:
        from tour import Tour  # type: ignore

    rng = np.random.default_rng(0)
    tour = Tour(rng.permutation(instance.dimension).tolist())
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
