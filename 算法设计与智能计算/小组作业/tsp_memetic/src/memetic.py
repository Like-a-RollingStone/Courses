from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from tqdm.auto import tqdm

try:
    from .ga import GeneticAlgorithm, _initialize_population
    from .instance import TSPInstance
    from .lin_kernighan import lin_kernighan, lin_kernighan_style
    from .operators import (
        apply_crossover,
        canonical_tour_key,
        edge_recombination_metrics,
        edge_set_key,
        get_crossover,
        inversion_mutation,
        tour_edges,
        tournament_selection,
    )
    from .or_opt import or_opt
    from .tour import Tour
    from .two_opt import two_opt_dlb
except ImportError:
    from ga import GeneticAlgorithm, _initialize_population  # type: ignore
    from instance import TSPInstance  # type: ignore
    from lin_kernighan import lin_kernighan, lin_kernighan_style  # type: ignore
    from operators import (  # type: ignore
        apply_crossover,
        canonical_tour_key,
        edge_recombination_metrics,
        edge_set_key,
        get_crossover,
        inversion_mutation,
        tour_edges,
        tournament_selection,
    )
    from or_opt import or_opt  # type: ignore
    from tour import Tour  # type: ignore
    from two_opt import two_opt_dlb  # type: ignore


class MemeticAlgorithm:
    """Memetic Algorithm with explicit Lamarckian/Baldwinian semantics.

    Lamarckian:
        Local-search improvements replace the chromosome, so improved
        experience is inherited by later genetic operators.
    Baldwinian:
        Local-search improvements are used only as phenotypes for evaluation;
        the original chromosome remains unchanged for selection/crossover.
    """

    def __init__(
        self,
        pop_size: int = 50,
        n_generations: int = 200,
        pc: float = 0.9,
        pm: float = 0.2,
        tournament_k: int = 3,
        elite_size: int = 2,
        crossover: str = "ox",
        ls_strategy: str = "partial",
        ls_probability: float = 0.3,
        ls_max_iter: int = 20,
        local_search: str = "2-opt",
        lk_warm_start_max_improvements: int | None = None,
        lk_max_improvements: int | None = 5,
        lk_max_depth: int = 3,
        lk_candidate_k: int | None = 15,
        lk_backtracking_width: int = 3,
        paradigm: str = "lamarckian",
        seed: int | None = None,
        show_progress: bool = True,
        verbose: bool = False,
    ):
        _validate_ma_params(
            pop_size=pop_size,
            n_generations=n_generations,
            pc=pc,
            pm=pm,
            tournament_k=tournament_k,
            elite_size=elite_size,
            crossover=crossover,
            ls_strategy=ls_strategy,
            ls_probability=ls_probability,
            ls_max_iter=ls_max_iter,
            local_search=local_search,
            lk_warm_start_max_improvements=lk_warm_start_max_improvements,
            lk_max_improvements=lk_max_improvements,
            lk_max_depth=lk_max_depth,
            lk_candidate_k=lk_candidate_k,
            lk_backtracking_width=lk_backtracking_width,
            paradigm=paradigm,
        )
        self.pop_size = pop_size
        self.n_generations = n_generations
        self.pc = pc
        self.pm = pm
        self.tournament_k = tournament_k
        self.elite_size = elite_size
        self.crossover = crossover
        self.ls_strategy = ls_strategy
        self.ls_probability = ls_probability
        self.ls_max_iter = ls_max_iter
        self.local_search = _normalize_local_search(local_search)
        self.lk_warm_start_max_improvements = lk_warm_start_max_improvements
        self.lk_max_improvements = lk_max_improvements
        self.lk_max_depth = lk_max_depth
        self.lk_candidate_k = lk_candidate_k
        self.lk_backtracking_width = lk_backtracking_width
        self.paradigm = paradigm
        self.seed = seed
        self.show_progress = show_progress
        self.verbose = verbose
        self.last_stats_history: list[dict[str, float | int]] = []

    def solve(
        self,
        instance: TSPInstance,
        callback: Callable[[int, Tour, float, dict[str, float | int]], None]
        | None = None,
    ) -> tuple[Tour, list[float]]:
        rng = np.random.default_rng(self.seed)
        population = _initialize_population(instance, self.pop_size, rng)

        population, lengths, phenotypes = self._initial_local_search(
            population,
            instance,
            rng,
        )
        best_tour, best_length = _best_from_records(population, lengths, phenotypes)
        history: list[float] = []
        self.last_stats_history = []

        iterator = tqdm(
            range(1, self.n_generations + 1),
            desc="MA",
            unit="gen",
            disable=not self.show_progress,
        )
        for generation in iterator:
            elite_population, elite_lengths, elite_phenotypes = _select_elite_records(
                population,
                lengths,
                phenotypes,
                self.elite_size,
            )
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
            children, edge_stats = _make_children_with_edge_stats(
                parents,
                self.pc,
                self.pm,
                rng,
                self.pop_size,
                self.crossover,
                instance,
            )
            (
                child_population,
                child_lengths,
                child_phenotypes,
            ) = self._local_search_children(children, instance, rng)

            merged_population = elite_population + child_population
            merged_lengths = np.concatenate([elite_lengths, child_lengths])
            merged_phenotypes = elite_phenotypes + child_phenotypes
            population, lengths, phenotypes = _take_best_records(
                merged_population,
                merged_lengths,
                merged_phenotypes,
                self.pop_size,
            )

            generation_best, generation_best_length = _best_from_records(
                population,
                lengths,
                phenotypes,
            )
            if generation_best_length < best_length:
                best_tour = generation_best.copy()
                best_length = generation_best_length

            history.append(best_length)
            stats = _population_stats(population, lengths)
            stats.update(edge_stats)
            self.last_stats_history.append(stats.copy())
            if callback is not None:
                try:
                    callback(generation, best_tour.copy(), best_length, stats)
                except StopIteration:
                    break
            if self.verbose:
                tqdm.write(
                    "generation="
                    f"{generation}, best_length={best_length:.0f}, "
                    f"mean_length={stats['population_mean_length']:.2f}, "
                    f"diversity={stats['unique_tours_count']}"
                )
            iterator.set_postfix(best=f"{best_length:.0f}")

        return best_tour.copy(), history

    def _initial_local_search(
        self,
        population: list[Tour],
        instance: TSPInstance,
        rng: np.random.Generator,
    ) -> tuple[list[Tour], np.ndarray, list[Tour]]:
        next_population: list[Tour] = []
        phenotypes: list[Tour] = []
        lengths: list[float] = []

        for chromosome in population:
            should_search, max_improvements = self._local_search_decision(rng)
            next_chromosome, length, phenotype = self._apply_local_search(
                chromosome,
                instance,
                force=should_search,
                max_improvements=max_improvements,
            )
            next_population.append(next_chromosome)
            lengths.append(length)
            phenotypes.append(phenotype)

        return next_population, np.array(lengths, dtype=np.float64), phenotypes

    def _local_search_children(
        self,
        children: list[Tour],
        instance: TSPInstance,
        rng: np.random.Generator,
    ) -> tuple[list[Tour], np.ndarray, list[Tour]]:
        next_population: list[Tour] = []
        phenotypes: list[Tour] = []
        lengths: list[float] = []

        for child in children:
            should_search, max_improvements = self._local_search_decision(rng)
            next_chromosome, length, phenotype = self._apply_local_search(
                child,
                instance,
                force=should_search,
                max_improvements=max_improvements,
            )
            next_population.append(next_chromosome)
            lengths.append(length)
            phenotypes.append(phenotype)

        return next_population, np.array(lengths, dtype=np.float64), phenotypes

    def _local_search_decision(
        self,
        rng: np.random.Generator,
    ) -> tuple[bool, int | None]:
        if self.ls_strategy == "full":
            return True, None
        if self.ls_strategy == "partial":
            return bool(rng.random() < self.ls_probability), None
        return True, self.ls_max_iter

    def _apply_local_search(
        self,
        chromosome: Tour,
        instance: TSPInstance,
        force: bool,
        max_improvements: int | None,
    ) -> tuple[Tour, float, Tour]:
        if not force:
            copied = chromosome.copy()
            return copied, copied.length(instance), copied.copy()

        improved, _ = self._run_local_search(
            chromosome,
            instance,
            max_improvements=max_improvements,
        )
        improved_length = improved.length(instance)

        if self.paradigm == "lamarckian":
            return improved.copy(), improved_length, improved.copy()

        return chromosome.copy(), improved_length, improved.copy()

    def _run_local_search(
        self,
        tour: Tour,
        instance: TSPInstance,
        max_improvements: int | None = None,
    ) -> tuple[Tour, int]:
        if self.local_search == "2-opt":
            return two_opt_dlb(
                tour,
                instance,
                max_improvements=max_improvements,
            )
        if self.local_search == "or-opt":
            return or_opt(
                tour,
                instance,
                max_improvements=max_improvements,
            )
        if self.local_search == "lk-style":
            return lin_kernighan_style(
                tour,
                instance,
                max_improvements=max_improvements,
            )
        if self.local_search == "lk":
            warm_start_limit = _combine_limits(
                max_improvements,
                self.lk_warm_start_max_improvements,
            )
            improved, two_opt_count = two_opt_dlb(
                tour,
                instance,
                max_improvements=warm_start_limit,
            )
            remaining = (
                None
                if max_improvements is None
                else max(0, max_improvements - two_opt_count)
            )
            if remaining == 0:
                return improved, two_opt_count
            lk_limit = _combine_limits(remaining, self.lk_max_improvements)
            if lk_limit == 0:
                return improved, two_opt_count
            improved, lk_count = lin_kernighan(
                improved,
                instance,
                max_depth=self.lk_max_depth,
                candidate_k=self.lk_candidate_k,
                backtracking_width=self.lk_backtracking_width,
                max_improvements=lk_limit,
            )
            return improved, two_opt_count + lk_count

        improved, two_opt_count = two_opt_dlb(
            tour,
            instance,
            max_improvements=max_improvements,
        )
        remaining = None
        if max_improvements is not None:
            remaining = max(0, max_improvements - two_opt_count)
            if remaining == 0:
                return improved, two_opt_count
        improved, or_opt_count = or_opt(
            improved,
            instance,
            max_improvements=remaining,
        )
        return improved, two_opt_count + or_opt_count


def _validate_ma_params(
    pop_size: int,
    n_generations: int,
    pc: float,
    pm: float,
    tournament_k: int,
    elite_size: int,
    crossover: str,
    ls_strategy: str,
    ls_probability: float,
    ls_max_iter: int,
    local_search: str,
    lk_warm_start_max_improvements: int | None,
    lk_max_improvements: int | None,
    lk_max_depth: int,
    lk_candidate_k: int | None,
    lk_backtracking_width: int,
    paradigm: str,
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
    if ls_strategy not in {"full", "partial", "bounded"}:
        raise ValueError("ls_strategy must be one of: full, partial, bounded")
    if not 0.0 <= ls_probability <= 1.0:
        raise ValueError("ls_probability must be in [0, 1]")
    if ls_max_iter < 0:
        raise ValueError("ls_max_iter must be non-negative")
    if (
        lk_warm_start_max_improvements is not None
        and lk_warm_start_max_improvements < 0
    ):
        raise ValueError(
            "lk_warm_start_max_improvements must be non-negative or None"
        )
    if lk_max_improvements is not None and lk_max_improvements < 0:
        raise ValueError("lk_max_improvements must be non-negative or None")
    if lk_max_depth < 2:
        raise ValueError("lk_max_depth must be at least 2")
    if lk_candidate_k is not None and lk_candidate_k <= 0:
        raise ValueError("lk_candidate_k must be positive or None")
    if lk_backtracking_width <= 0:
        raise ValueError("lk_backtracking_width must be positive")
    local_search = _normalize_local_search(local_search)
    if local_search not in {"2-opt", "or-opt", "both", "lk-style", "lk"}:
        raise ValueError(
            "local_search must be one of: 2-opt, or-opt, both, lk-style, lk"
        )
    if paradigm not in {"lamarckian", "baldwinian"}:
        raise ValueError("paradigm must be one of: lamarckian, baldwinian")


def _normalize_local_search(local_search: str) -> str:
    normalized = local_search.strip().lower().replace("_", "-")
    if normalized in {"lk", "lin-kernighan"}:
        return "lk"
    return normalized


def _combine_limits(first: int | None, second: int | None) -> int | None:
    if first is None:
        return second
    if second is None:
        return first
    return min(first, second)


def _select_elite_records(
    population: list[Tour],
    lengths: np.ndarray,
    phenotypes: list[Tour],
    elite_size: int,
) -> tuple[list[Tour], np.ndarray, list[Tour]]:
    if elite_size == 0:
        return [], np.array([], dtype=np.float64), []
    order = np.argsort(lengths, kind="stable")[:elite_size]
    return (
        [population[int(idx)].copy() for idx in order],
        lengths[order].copy(),
        [phenotypes[int(idx)].copy() for idx in order],
    )


def _take_best_records(
    population: list[Tour],
    lengths: np.ndarray,
    phenotypes: list[Tour],
    target_size: int,
) -> tuple[list[Tour], np.ndarray, list[Tour]]:
    order = np.argsort(lengths, kind="stable")[:target_size]
    return (
        [population[int(idx)].copy() for idx in order],
        lengths[order].copy(),
        [phenotypes[int(idx)].copy() for idx in order],
    )


def _best_from_records(
    population: list[Tour],
    lengths: np.ndarray,
    phenotypes: list[Tour],
) -> tuple[Tour, float]:
    del population
    best_idx = int(np.argmin(lengths))
    return phenotypes[best_idx].copy(), float(lengths[best_idx])


def _diversity(population: list[Tour]) -> int:
    return len({canonical_tour_key(tour.cities) for tour in population})


def _make_children_with_edge_stats(
    parents: list[Tour],
    pc: float,
    pm: float,
    rng: np.random.Generator,
    target_size: int,
    crossover: str,
    instance: TSPInstance | None = None,
) -> tuple[list[Tour], dict[str, float | int]]:
    children: list[Tour] = []
    metrics: list[dict[str, float | int]] = []

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
            metrics.append(
                edge_recombination_metrics(cities, parent1.cities, parent2.cities)
            )
            children.append(Tour(cities))
            if len(children) >= target_size:
                return children, _average_edge_metrics(metrics)

    return children, _average_edge_metrics(metrics)


def _average_edge_metrics(
    metrics: list[dict[str, float | int]],
) -> dict[str, float | int]:
    if not metrics:
        return {}

    keys = [
        "edge_overlap_rate",
        "parent_edge_inheritance_rate",
        "common_edge_preservation_rate",
        "foreign_edges_count",
        "child_parent_edge_distance",
    ]
    return {
        key: float(np.mean([float(row[key]) for row in metrics]))
        for key in keys
    }


def _population_stats(
    population: list[Tour],
    lengths: np.ndarray,
) -> dict[str, float | int]:
    edge_sets = [tour_edges(tour.cities) for tour in population]
    return {
        "population_mean_length": float(np.mean(lengths)),
        "population_std": float(np.std(lengths)),
        "unique_tours_count": _diversity(population),
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
    ma = MemeticAlgorithm(seed=0)

    ga_best, ga_history = ga.solve(instance)
    ma_best, ma_history = ma.solve(instance)
    print(f"GA final length: {ga_best.length(instance):.0f}")
    print(f"MA final length: {ma_best.length(instance):.0f}")

    import matplotlib.pyplot as plt

    output_path = _results_path("ma_vs_ga.png")
    plt.figure(figsize=(8, 5))
    plt.plot(range(1, len(ga_history) + 1), ga_history, label="GA")
    plt.plot(range(1, len(ma_history) + 1), ma_history, label="MA")
    plt.xlabel("Generation")
    plt.ylabel("Best-so-far length")
    plt.title("GA vs MA convergence on berlin52")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"saved convergence curve: {output_path}")


if __name__ == "__main__":
    _run_demo()
