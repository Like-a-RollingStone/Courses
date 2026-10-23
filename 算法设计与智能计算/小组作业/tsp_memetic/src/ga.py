from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from tqdm.auto import tqdm

try:
    from .baselines import nearest_neighbor
    from .instance import TSPInstance
    from .operators import (
        apply_crossover,
        canonical_tour_key,
        edge_set_key,
        get_crossover,
        inversion_mutation,
        tour_edges,
        tournament_selection,
    )
    from .tour import Tour
except ImportError:
    from baselines import nearest_neighbor  # type: ignore
    from instance import TSPInstance  # type: ignore
    from operators import (  # type: ignore
        apply_crossover,
        canonical_tour_key,
        edge_set_key,
        get_crossover,
        inversion_mutation,
        tour_edges,
        tournament_selection,
    )
    from tour import Tour  # type: ignore


class GeneticAlgorithm:
    def __init__(
        self,
        pop_size: int = 100,
        n_generations: int = 500,
        pc: float = 0.9,
        pm: float = 0.2,
        tournament_k: int = 3,
        elite_size: int = 2,
        crossover: str = "ox",
        seed: int | None = None,
        show_progress: bool = True,
    ):
        _validate_ga_params(
            pop_size=pop_size,
            n_generations=n_generations,
            pc=pc,
            pm=pm,
            tournament_k=tournament_k,
            elite_size=elite_size,
            crossover=crossover,
        )
        self.pop_size = pop_size
        self.n_generations = n_generations
        self.pc = pc
        self.pm = pm
        self.tournament_k = tournament_k
        self.elite_size = elite_size
        self.crossover = crossover
        self.seed = seed
        self.show_progress = show_progress

    def solve(
        self,
        instance: TSPInstance,
        callback: Callable[[int, Tour, float, dict[str, float | int]], None]
        | None = None,
    ) -> tuple[Tour, list[float]]:
        """
        Return (best Tour, best-so-far length history per generation).
        """

        rng = np.random.default_rng(self.seed)
        population = _initialize_population(instance, self.pop_size, rng)
        lengths = _evaluate_population(population, instance)
        best_tour, best_length = _best_from_population(population, lengths)
        history: list[float] = []

        iterator = tqdm(
            range(1, self.n_generations + 1),
            desc="GA",
            unit="gen",
            disable=not self.show_progress,
        )
        for generation in iterator:
            lengths = _evaluate_population(population, instance)
            elites = _select_elites(population, lengths, self.elite_size)
            fitnesses = (-lengths).tolist()
            parents = [
                tournament_selection(
                    population,
                    fitnesses,
                    k=self.tournament_k,
                    rng=rng,
                )
                for _ in range(self.pop_size)
            ]
            children = _make_children(
                parents,
                self.pc,
                self.pm,
                rng,
                self.pop_size,
                self.crossover,
                instance,
            )

            merged = elites + children
            merged_lengths = _evaluate_population(merged, instance)
            population, lengths = _take_best(merged, merged_lengths, self.pop_size)

            generation_best, generation_best_length = _best_from_population(
                population, lengths
            )
            if generation_best_length < best_length:
                best_tour = generation_best.copy()
                best_length = generation_best_length

            history.append(best_length)
            stats = _population_stats(population, lengths)
            if callback is not None:
                try:
                    callback(generation, best_tour.copy(), best_length, stats)
                except StopIteration:
                    break
            iterator.set_postfix(best=f"{best_length:.0f}")

        return best_tour.copy(), history


def _validate_ga_params(
    pop_size: int,
    n_generations: int,
    pc: float,
    pm: float,
    tournament_k: int,
    elite_size: int,
    crossover: str,
) -> None:
    if pop_size <= 0:
        raise ValueError("pop_size must be positive")
    if n_generations < 0:
        raise ValueError("n_generations must be non-negative")
    if not 0.0 <= pc <= 1.0:
        raise ValueError("pc must be in [0, 1]")
    if not 0.0 <= pm <= 1.0:
        raise ValueError("pm must be in [0, 1]")
    if not 1 <= tournament_k <= pop_size:
        raise ValueError("tournament_k must be in [1, pop_size]")
    if not 0 <= elite_size <= pop_size:
        raise ValueError("elite_size must be in [0, pop_size]")
    get_crossover(crossover)


def _initialize_population(
    instance: TSPInstance,
    pop_size: int,
    rng: np.random.Generator,
) -> list[Tour]:
    n = instance.dimension
    nn_count = pop_size // 2
    population: list[Tour] = []

    starts: list[int] = []
    while len(starts) < nn_count:
        starts.extend(rng.permutation(n).astype(int).tolist())

    for start in starts[:nn_count]:
        tie_seed = int(rng.integers(0, np.iinfo(np.uint32).max))
        population.append(nearest_neighbor(instance, start=start, seed=tie_seed))

    while len(population) < pop_size:
        population.append(Tour(rng.permutation(n).astype(int).tolist()))

    return population


def _evaluate_population(
    population: list[Tour],
    instance: TSPInstance,
) -> np.ndarray:
    return np.array([tour.length(instance) for tour in population], dtype=np.float64)


def _select_elites(
    population: list[Tour],
    lengths: np.ndarray,
    elite_size: int,
) -> list[Tour]:
    if elite_size == 0:
        return []
    order = np.argsort(lengths, kind="stable")
    return [population[int(idx)].copy() for idx in order[:elite_size]]


def _make_children(
    parents: list[Tour],
    pc: float,
    pm: float,
    rng: np.random.Generator,
    target_size: int,
    crossover: str = "ox",
    instance: TSPInstance | None = None,
) -> list[Tour]:
    children: list[Tour] = []
    for idx in range(0, len(parents), 2):
        parent1 = parents[idx]
        parent2 = parents[(idx + 1) % len(parents)]

        if rng.random() < pc:
            child1_cities, child2_cities = apply_crossover(
                crossover,
                parent1.cities,
                parent2.cities,
                rng,
                instance,
            )
        else:
            child1_cities = parent1.cities.copy()
            child2_cities = parent2.cities.copy()

        for cities in (child1_cities, child2_cities):
            if rng.random() < pm:
                cities = inversion_mutation(cities, rng)
            children.append(Tour(cities))
            if len(children) >= target_size:
                return children

    return children


def _take_best(
    population: list[Tour],
    lengths: np.ndarray,
    target_size: int,
) -> tuple[list[Tour], np.ndarray]:
    order = np.argsort(lengths, kind="stable")[:target_size]
    next_population = [population[int(idx)].copy() for idx in order]
    next_lengths = lengths[order].copy()
    return next_population, next_lengths


def _best_from_population(
    population: list[Tour],
    lengths: np.ndarray,
) -> tuple[Tour, float]:
    best_idx = int(np.argmin(lengths))
    return population[best_idx].copy(), float(lengths[best_idx])


def _population_stats(
    population: list[Tour],
    lengths: np.ndarray,
) -> dict[str, float | int]:
    edge_sets = [tour_edges(tour.cities) for tour in population]
    return {
        "population_mean_length": float(np.mean(lengths)),
        "population_std": float(np.std(lengths)),
        "unique_tours_count": len({canonical_tour_key(tour.cities) for tour in population}),
        "unique_edge_sets_count": len({edge_set_key(tour.cities) for tour in population}),
        "edge_diversity": len(set().union(*edge_sets)) if edge_sets else 0,
        "pairwise_edge_distance": _average_pairwise_edge_distance(edge_sets),
    }


def _average_pairwise_edge_distance(edge_sets: list[set[tuple[int, int]]]) -> float:
    if len(edge_sets) < 2:
        return 0.0
    distances: list[float] = []
    for i in range(len(edge_sets) - 1):
        for j in range(i + 1, len(edge_sets)):
            distances.append(float(len(edge_sets[i] ^ edge_sets[j])))
    return float(np.mean(distances)) if distances else 0.0


def _tsplib_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "tsplib" / filename


def _results_path(filename: str) -> Path:
    path = Path(__file__).resolve().parents[1] / "results" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _run_demo() -> None:
    path = _tsplib_path("berlin52.tsp")
    if not path.exists():
        print(f"berlin52.tsp not found: {path}")
        return

    instance = TSPInstance.load_tsplib(path)
    ga = GeneticAlgorithm(pop_size=100, n_generations=500, seed=0)
    best_tour, history = ga.solve(instance)
    best_length = best_tour.length(instance)
    print(f"GA final length: {best_length:.0f}")
    print(f"final length in [7700, 8200]: {7700 <= best_length <= 8200}")

    import matplotlib.pyplot as plt

    output_path = _results_path("ga_convergence.png")
    plt.figure(figsize=(8, 5))
    plt.plot(range(1, len(history) + 1), history, label="GA")
    plt.xlabel("Generation")
    plt.ylabel("Best-so-far length")
    plt.title("GA convergence on berlin52")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"saved convergence curve: {output_path}")


if __name__ == "__main__":
    _run_demo()
