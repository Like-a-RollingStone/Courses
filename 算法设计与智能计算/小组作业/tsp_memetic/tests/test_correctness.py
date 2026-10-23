from pathlib import Path

import numpy as np
import pytest

from src.baselines import held_karp, nearest_neighbor
from src.ga import GeneticAlgorithm
from src.instance import TSPInstance
from src.memetic import MemeticAlgorithm
from src.lin_kernighan import lin_kernighan, lin_kernighan_style
from src.operators import apply_crossover, order_crossover, pmx_crossover, tour_edges
from src.or_opt import or_opt
from src.tour import Tour
from src.two_opt import two_opt_basic, two_opt_dlb


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "tsplib"


@pytest.fixture(scope="session")
def burma14() -> TSPInstance:
    return TSPInstance.load_tsplib(DATA_DIR / "burma14.tsp")


@pytest.fixture(scope="session")
def berlin52() -> TSPInstance:
    return TSPInstance.load_tsplib(DATA_DIR / "berlin52.tsp")


def test_held_karp_finds_burma14_optimum(burma14: TSPInstance) -> None:
    tour = held_karp(burma14)
    assert abs(tour.length(burma14) - 3323) < 1


def test_two_opt_basic_equals_dlb(berlin52: TSPInstance) -> None:
    initial = nearest_neighbor(berlin52, start=0)
    basic, _ = two_opt_basic(initial, berlin52)
    dlb, _ = two_opt_dlb(initial, berlin52)
    assert abs(basic.length(berlin52) - dlb.length(berlin52)) < 1


def test_two_opt_dlb_callback_emits_each_improvement(berlin52: TSPInstance) -> None:
    initial = nearest_neighbor(berlin52, start=0)
    events: list[tuple[int, float]] = []

    improved, improvements = two_opt_dlb(
        initial,
        berlin52,
        max_improvements=5,
        callback=lambda step, tour, length: events.append((step, length)),
    )

    assert improvements == len(events)
    assert improvements > 0
    assert events[-1][1] == improved.length(berlin52)
    assert all(prev >= cur for (_, prev), (_, cur) in zip(events, events[1:]))


def test_or_opt_returns_valid_non_worse_tour(berlin52: TSPInstance) -> None:
    initial = nearest_neighbor(berlin52, start=0)
    improved, improvements = or_opt(initial, berlin52)
    assert improved.is_valid(berlin52.dimension)
    assert improved.length(berlin52) <= initial.length(berlin52)
    assert improvements >= 0


def test_crossovers_produce_valid_permutations() -> None:
    rng = np.random.default_rng(0)
    p1 = list(range(20))
    p2 = rng.permutation(20).astype(int).tolist()
    expected = set(p1)

    for _ in range(100):
        ox1, ox2 = order_crossover(p1, p2, rng)
        pmx1, pmx2 = pmx_crossover(p1, p2, rng)
        assert set(ox1) == expected
        assert set(ox2) == expected
        assert set(pmx1) == expected
        assert set(pmx2) == expected


def test_distance_aware_crossovers_produce_valid_permutations(
    berlin52: TSPInstance,
) -> None:
    rng = np.random.default_rng(0)
    p1 = list(range(berlin52.dimension))
    p2 = rng.permutation(berlin52.dimension).astype(int).tolist()
    expected = set(p1)

    for name in ["dpx", "gx"]:
        child1, child2 = apply_crossover(name, p1, p2, rng, berlin52)
        assert set(child1) == expected
        assert set(child2) == expected


def test_lk_style_returns_valid_non_worse_tour(berlin52: TSPInstance) -> None:
    initial = nearest_neighbor(berlin52, start=0)
    improved, improvements = lin_kernighan_style(initial, berlin52)
    assert improved.is_valid(berlin52.dimension)
    assert improved.length(berlin52) <= initial.length(berlin52)
    assert improvements >= 0


def test_lin_kernighan_returns_valid_non_worse_tour(
    berlin52: TSPInstance,
) -> None:
    initial = nearest_neighbor(berlin52, start=0)
    improved, improvements = lin_kernighan(
        initial,
        berlin52,
        seed=0,
        max_depth=4,
        candidate_k=20,
        backtracking_width=5,
        max_improvements=5,
    )
    assert improved.is_valid(berlin52.dimension)
    assert improved.length(berlin52) <= initial.length(berlin52)
    assert improvements >= 0


def test_lin_kernighan_depth_two_covers_two_opt(
    berlin52: TSPInstance,
) -> None:
    initial = nearest_neighbor(berlin52, start=0)
    two_opt_tour, _ = two_opt_dlb(initial, berlin52)
    lk_tour, _ = lin_kernighan(
        initial,
        berlin52,
        seed=0,
        max_depth=2,
        candidate_k=None,
        backtracking_width=berlin52.dimension,
    )
    assert lk_tour.is_valid(berlin52.dimension)
    assert lk_tour.length(berlin52) <= two_opt_tour.length(berlin52) + 1e-6


def test_lin_kernighan_preserves_fixed_edges(
    berlin52: TSPInstance,
) -> None:
    initial = nearest_neighbor(berlin52, start=0)
    fixed_edges = {
        tuple(sorted((initial.cities[idx], initial.cities[(idx + 1) % len(initial)])))
        for idx in range(3)
    }
    improved, _ = lin_kernighan(
        initial,
        berlin52,
        seed=0,
        max_depth=4,
        candidate_k=20,
        backtracking_width=5,
        max_improvements=5,
        fixed_edges=fixed_edges,
    )
    assert improved.is_valid(berlin52.dimension)
    assert fixed_edges <= tour_edges(improved.cities)


def test_delta_two_opt_matches_full_recompute(berlin52: TSPInstance) -> None:
    rng = np.random.default_rng(0)
    tour = Tour(rng.permutation(berlin52.dimension).astype(int).tolist())

    for _ in range(20):
        i, j = sorted(rng.choice(berlin52.dimension, 2, replace=False).astype(int).tolist())
        old_length = tour.length(berlin52)
        delta = tour.delta_two_opt(i, j, berlin52)
        new_cities = tour.cities.copy()
        new_cities[i : j + 1] = reversed(new_cities[i : j + 1])
        actual = Tour(new_cities).length(berlin52) - old_length
        assert abs(delta - actual) < 1e-6


def test_memetic_reaches_berlin52_optimum(berlin52: TSPInstance) -> None:
    ma = MemeticAlgorithm(seed=0, show_progress=False, verbose=False)
    best, _ = ma.solve(berlin52)
    assert abs(best.length(berlin52) - 7542) < 1


def test_memetic_supports_all_local_search_modes(berlin52: TSPInstance) -> None:
    for mode in ["2-opt", "or-opt", "both", "lk-style"]:
        ma = MemeticAlgorithm(
            seed=0,
            pop_size=20,
            n_generations=2,
            local_search=mode,
            show_progress=False,
            verbose=False,
        )
        best, history = ma.solve(berlin52)
        assert best.is_valid(berlin52.dimension)
        assert len(history) == 2


def test_ga_and_ma_callbacks_include_population_stats(berlin52: TSPInstance) -> None:
    ga_events: list[dict[str, float | int]] = []
    ga = GeneticAlgorithm(
        seed=0,
        pop_size=20,
        n_generations=1,
        show_progress=False,
    )
    ga.solve(
        berlin52,
        callback=lambda generation, tour, length, stats: ga_events.append(stats),
    )

    ma_events: list[dict[str, float | int]] = []
    ma = MemeticAlgorithm(
        seed=0,
        pop_size=20,
        n_generations=1,
        show_progress=False,
        verbose=False,
    )
    ma.solve(
        berlin52,
        callback=lambda generation, tour, length, stats: ma_events.append(stats),
    )

    assert ga_events
    assert ma_events
    assert {"population_mean_length", "population_std", "unique_tours_count"} <= set(
        ga_events[-1]
    )
    assert {"population_mean_length", "population_std", "unique_tours_count"} <= set(
        ma_events[-1]
    )


def test_lamarckian_not_worse_than_baldwinian_early(berlin52: TSPInstance) -> None:
    ma_l = MemeticAlgorithm(
        seed=0,
        n_generations=10,
        paradigm="lamarckian",
        show_progress=False,
        verbose=False,
    )
    ma_b = MemeticAlgorithm(
        seed=0,
        n_generations=10,
        paradigm="baldwinian",
        show_progress=False,
        verbose=False,
    )
    _, h_l = ma_l.solve(berlin52)
    _, h_b = ma_b.solve(berlin52)
    assert h_l[-1] <= h_b[-1]
