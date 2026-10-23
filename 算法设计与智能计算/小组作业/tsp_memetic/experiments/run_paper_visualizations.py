from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from time import perf_counter

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ga import GeneticAlgorithm
from src.baselines import nearest_neighbor
from src.instance import TSPInstance
from src.lin_kernighan import lin_kernighan
from src.memetic import MemeticAlgorithm
from src.operators import apply_crossover, edge_recombination_metrics, tour_edges
from src.tour import Tour
from src.two_opt import two_opt_dlb


OPTIMAL = {
    "burma14": 3323.0,
    "berlin52": 7542.0,
    "eil51": 426.0,
    "eil101": 629.0,
    "ch130": 6110.0,
    "kroA200": 29368.0,
    "pcb442": 50778.0,
    "rat575": 6773.0,
}

BASE_SEED = 20260615
plt.rcParams["font.family"] = "DejaVu Sans"


@dataclass(frozen=True)
class SolverSpec:
    name: str
    kind: str
    crossover: str = "ox"
    local_search: str = "2-opt"
    pc: float = 0.9
    pm: float = 0.2


@dataclass(frozen=True)
class LKBudget:
    warm_start_max_improvements: int | None
    max_improvements: int | None
    max_depth: int
    candidate_k: int | None
    backtracking_width: int


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate paper-driven TSP crossover and local-search visualizations."
    )
    parser.add_argument("--instance", default="ch130")
    parser.add_argument("--runs", type=int, default=15)
    parser.add_argument("--generations", type=int, default=15)
    parser.add_argument("--pop-size", type=int, default=8)
    parser.add_argument(
        "--lk-warm-start-max-improvements",
        type=_optional_nonnegative_int,
        default=None,
        help="2-opt warm-start improvement cap for LK variants; use 'none' for unbounded.",
    )
    parser.add_argument(
        "--lk-max-improvements",
        type=_optional_nonnegative_int,
        default=3,
        help="Variable-depth LK improvement cap after warm start; use 'none' for unbounded.",
    )
    parser.add_argument("--lk-max-depth", type=int, default=3)
    parser.add_argument(
        "--lk-candidate-k",
        type=_optional_nonnegative_int,
        default=12,
        help="Nearest-neighbor candidate-set size for LK; use 'none' for all cities.",
    )
    parser.add_argument("--lk-backtracking-width", type=int, default=2)
    args = parser.parse_args()
    lk_budget = LKBudget(
        warm_start_max_improvements=args.lk_warm_start_max_improvements,
        max_improvements=args.lk_max_improvements,
        max_depth=args.lk_max_depth,
        candidate_k=args.lk_candidate_k,
        backtracking_width=args.lk_backtracking_width,
    )
    if lk_budget.max_depth < 2:
        parser.error("--lk-max-depth must be at least 2")
    if lk_budget.backtracking_width <= 0:
        parser.error("--lk-backtracking-width must be positive")

    instance = _load_instance(args.instance)
    optimal = OPTIMAL.get(args.instance)
    visual_dir = ROOT / "report" / "figures"
    table_dir = ROOT / "results" / "paper_tables"
    visual_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        table_dir / "run_metadata.csv",
        [
            {
                "instance": args.instance,
                "runs": args.runs,
                "generations": args.generations,
                "pop_size": args.pop_size,
                "lk_warm_start_max_improvements": _limit_label(
                    lk_budget.warm_start_max_improvements
                ),
                "lk_max_improvements": _limit_label(lk_budget.max_improvements),
                "lk_max_depth": lk_budget.max_depth,
                "lk_candidate_k": _limit_label(lk_budget.candidate_k),
                "lk_backtracking_width": lk_budget.backtracking_width,
                "base_seed": BASE_SEED,
                "local_search_note": (
                    "Critical bounded LK regime = full 2-opt warm start + "
                    "moderately capped variable-depth lin_kernighan; stronger "
                    "than 2-opt but not strong enough to wash out crossover effects"
                ),
            }
        ],
    )

    print("6.1 edge structure visualization")
    _edge_structure_visualization(instance, visual_dir, table_dir)

    print("6.1.2 common-edge preservation contrast")
    _edge_structure_contrast_visualization(instance, visual_dir, table_dir)

    print("6.2 local search before/after visualization")
    _local_search_before_after(instance, lk_budget, visual_dir, table_dir)

    print("6.3 convergence curves")
    convergence_rows = _run_convergence_experiment(
        instance,
        args.runs,
        args.generations,
        args.pop_size,
        lk_budget,
        optimal,
        visual_dir,
        table_dir,
    )

    print("6.4 crossover ablation")
    _run_recombination_ablation(
        instance,
        args.runs,
        args.generations,
        args.pop_size,
        lk_budget,
        optimal,
        convergence_rows,
        visual_dir,
        table_dir,
    )

    print("6.5 edge inheritance and foreign edge curves")
    _edge_metric_curves(
        instance,
        args.generations,
        args.pop_size,
        lk_budget,
        visual_dir,
        table_dir,
    )

    print("6.6 population diversity curves")
    _diversity_curves(
        instance,
        args.generations,
        args.pop_size,
        lk_budget,
        visual_dir,
        table_dir,
    )

    print(f"visualizations saved to {visual_dir}")
    print(f"tables saved to {table_dir}")


def _load_instance(name: str) -> TSPInstance:
    path = ROOT / "data" / "tsplib" / f"{name}.tsp"
    if not path.exists():
        raise FileNotFoundError(path)
    return TSPInstance.load_tsplib(path)


def _optional_nonnegative_int(value: str) -> int | None:
    normalized = value.strip().lower()
    if normalized in {"none", "unbounded", "full"}:
        return None
    try:
        parsed = int(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected a non-negative integer, 'none', 'unbounded', or 'full'"
        ) from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def _limit_label(value: int | None) -> str:
    return "unbounded" if value is None else str(value)


def _edge_structure_visualization(
    instance: TSPInstance,
    visual_dir: Path,
    table_dir: Path,
) -> None:
    parent_a, parent_b = _teaching_parents(instance)
    parent_edges = tour_edges(parent_a.cities) | tour_edges(parent_b.cities)
    common_edges = tour_edges(parent_a.cities) & tour_edges(parent_b.cities)

    operators = ["ox", "pmx", "dpx", "gx"]
    children = {
        name: Tour(
            apply_crossover(
                name,
                parent_a.cities,
                parent_b.cities,
                np.random.default_rng(BASE_SEED + idx * 10000),
                instance,
            )[0]
        )
        for idx, name in enumerate(operators)
    }

    rows = []
    for name, child in children.items():
        metrics = edge_recombination_metrics(child.cities, parent_a.cities, parent_b.cities)
        rows.append(
            {
                "operator": name.upper(),
                "common_edges": len(common_edges),
                "common_preserved": len(tour_edges(child.cities) & common_edges),
                "common_broken": len(common_edges - tour_edges(child.cities)),
                "parent_edge_inheritance_rate": f"{metrics['parent_edge_inheritance_rate']:.6f}",
                "common_edge_preservation_rate": f"{metrics['common_edge_preservation_rate']:.6f}",
                "foreign_edges_count": int(metrics["foreign_edges_count"]),
            }
        )
    _write_csv(table_dir / "edge_structure_metrics.csv", rows)
    _write_edge_structure_sample_summary(
        instance,
        parent_a,
        parent_b,
        operators,
        table_dir,
        sample_count=40,
    )

    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(
        3,
        4,
        height_ratios=[1.0, 0.18, 1.12],
        hspace=0.16,
        wspace=0.12,
    )
    parent_a_ax = fig.add_subplot(gs[0, 0])
    backbone_ax = fig.add_subplot(gs[0, 1:3])
    parent_b_ax = fig.add_subplot(gs[0, 3])
    _plot_edge_structure_panel(
        parent_a_ax,
        instance,
        parent_a,
        title="Parent A",
        common_edges=common_edges,
        parent_edges=parent_edges,
    )
    _plot_common_backbone_panel(
        backbone_ax,
        instance,
        common_edges,
        title=f"Foundation: {len(common_edges)} common edges shared by both parents",
    )
    _plot_edge_structure_panel(
        parent_b_ax,
        instance,
        parent_b,
        title="Parent B",
        common_edges=common_edges,
        parent_edges=parent_edges,
    )

    left_label_ax = fig.add_subplot(gs[1, 0:2])
    right_label_ax = fig.add_subplot(gs[1, 2:4])
    for ax in (left_label_ax, right_label_ax):
        ax.axis("off")
    left_label_ax.text(
        0.5,
        0.5,
        "Position/order crossovers: OX and PMX\nfew foreign edges, weaker edge-building-block focus",
        ha="center",
        va="center",
        fontsize=11,
        color="#27496d",
        weight="semibold",
    )
    right_label_ax.text(
        0.5,
        0.5,
        "Fragment/reconnect crossovers: DPX and GX\nkeep the common backbone, then add more foreign edges",
        ha="center",
        va="center",
        fontsize=11,
        color="#7f1d1d",
        weight="semibold",
    )

    child_axes = [fig.add_subplot(gs[2, idx]) for idx in range(4)]
    for ax, name in zip(child_axes, operators, strict=True):
        _plot_child_edge_panel(ax, instance, children[name], parent_edges, common_edges, name)
    fig.add_artist(
        Line2D(
            [0.5, 0.5],
            [0.08, 0.52],
            transform=fig.transFigure,
            color="#d0d0d0",
            linewidth=1.0,
        )
    )
    fig.suptitle("Edge-structure tension: position/order inheritance vs fragment reconnection")
    fig.legend(
        handles=[
            Line2D([0], [0], color="#2ca02c", linewidth=2.4, label="common edge kept"),
            Line2D([0], [0], color="#8fb8d8", linewidth=2.0, label="parent-only edge"),
            Line2D([0], [0], color="#d62728", linewidth=2.8, label="foreign edge"),
            Line2D([0], [0], color="#c9c9c9", linewidth=1.0, label="unused parent edge"),
        ],
        loc="lower center",
        ncol=4,
        frameon=False,
    )
    fig.subplots_adjust(left=0.04, right=0.98, top=0.9, bottom=0.09)
    fig.savefig(visual_dir / "6_1_edge_structure_breakdown.png", dpi=180)
    plt.close(fig)


def _edge_structure_contrast_visualization(
    instance: TSPInstance,
    visual_dir: Path,
    table_dir: Path,
) -> None:
    parent_a, parent_b, crossover_seed = _contrast_teaching_parents(instance)
    parent_edges = tour_edges(parent_a.cities) | tour_edges(parent_b.cities)
    common_edges = tour_edges(parent_a.cities) & tour_edges(parent_b.cities)

    children = {
        name: Tour(
            apply_crossover(
                name,
                parent_a.cities,
                parent_b.cities,
                np.random.default_rng(crossover_seed),
                instance,
            )[0]
        )
        for name in ["pmx", "dpx"]
    }

    rows = []
    for name, child in children.items():
        child_edges = tour_edges(child.cities)
        rows.append(
            {
                "operator": name.upper(),
                "common_edges": len(common_edges),
                "common_preserved": len(child_edges & common_edges),
                "common_broken": len(common_edges - child_edges),
                "parent_only_edges": len((child_edges & parent_edges) - common_edges),
                "foreign_edges": len(child_edges - parent_edges),
                "crossover_seed": crossover_seed,
            }
        )
    _write_csv(table_dir / "edge_structure_contrast_metrics.csv", rows)

    fig = plt.figure(figsize=(8.2, 11.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.12], hspace=0.16, wspace=0.08)

    parent_a_ax = fig.add_subplot(gs[0, 0])
    parent_b_ax = fig.add_subplot(gs[0, 1])
    _plot_edge_structure_panel(
        parent_a_ax,
        instance,
        parent_a,
        title="Parent A",
        common_edges=common_edges,
        parent_edges=parent_edges,
    )
    _plot_edge_structure_panel(
        parent_b_ax,
        instance,
        parent_b,
        title="Parent B",
        common_edges=common_edges,
        parent_edges=parent_edges,
    )

    pmx_ax = fig.add_subplot(gs[1, 0])
    dpx_ax = fig.add_subplot(gs[1, 1])
    _plot_child_common_loss_panel(
        pmx_ax,
        instance,
        children["pmx"],
        parent_edges,
        common_edges,
        "PMX child",
        subtitle="position mapping can break shared edges",
    )
    _plot_child_common_loss_panel(
        dpx_ax,
        instance,
        children["dpx"],
        parent_edges,
        common_edges,
        "DPX child",
        subtitle="fragment recombination preserves the backbone",
    )

    fig.suptitle("Common-edge respectfulness: PMX disruption vs DPX preservation")
    fig.legend(
        handles=[
            Line2D([0], [0], color="#2ca02c", linewidth=2.4, label="common edge kept"),
            Line2D(
                [0],
                [0],
                color="#f28e2b",
                linewidth=2.0,
                linestyle=(0, (4, 3)),
                label="common edge broken",
            ),
            Line2D([0], [0], color="#8fb8d8", linewidth=2.0, label="parent-only edge"),
            Line2D([0], [0], color="#d62728", linewidth=2.6, label="foreign edge"),
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
    )
    fig.subplots_adjust(left=0.04, right=0.98, top=0.9, bottom=0.1)
    fig.savefig(visual_dir / "6_1_2_edge_preservation_contrast.png", dpi=180)
    plt.close(fig)


def _local_search_before_after(
    instance: TSPInstance,
    lk_budget: LKBudget,
    visual_dir: Path,
    table_dir: Path,
) -> None:
    rng = np.random.default_rng(BASE_SEED + 1)
    parent_a, parent_b = _teaching_parents(instance)
    child = Tour(apply_crossover("gx", parent_a.cities, parent_b.cities, rng, instance)[0])
    before_edges = tour_edges(child.cities)
    start = perf_counter()
    improved, improvements = _run_bounded_lk(child, instance, lk_budget)
    elapsed = perf_counter() - start
    after_edges = tour_edges(improved.cities)
    removed = before_edges - after_edges
    added = after_edges - before_edges

    _write_csv(
        table_dir / "local_search_before_after.csv",
        [
            {
                "initial_length": f"{child.length(instance):.6f}",
                "final_length": f"{improved.length(instance):.6f}",
                "improvement": f"{child.length(instance) - improved.length(instance):.6f}",
                "accepted_moves": improvements,
                "lk_warm_start_max_improvements": _limit_label(
                    lk_budget.warm_start_max_improvements
                ),
                "lk_max_improvements": _limit_label(lk_budget.max_improvements),
                "removed_edges": len(removed),
                "added_edges": len(added),
                "time": f"{elapsed:.6f}",
            }
        ],
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    _plot_tour_with_highlights(
        axes[0],
        instance,
        child,
        title=f"Raw GX child | length={child.length(instance):.0f}",
        highlighted=removed,
        highlight_color="#d62728",
        highlight_label="deleted by LK",
    )
    _plot_tour_with_highlights(
        axes[1],
        instance,
        improved,
        title=f"After LK | length={improved.length(instance):.0f}",
        highlighted=added,
        highlight_color="#2ca02c",
        highlight_label="added by LK",
    )
    fig.suptitle("Local search before and after")
    fig.tight_layout()
    fig.savefig(visual_dir / "6_2_local_search_before_after.png", dpi=180)
    plt.close(fig)


def _run_bounded_lk(
    tour: Tour,
    instance: TSPInstance,
    lk_budget: LKBudget,
) -> tuple[Tour, int]:
    improved, two_opt_count = two_opt_dlb(
        tour,
        instance,
        max_improvements=lk_budget.warm_start_max_improvements,
    )
    improved, lk_count = lin_kernighan(
        improved,
        instance,
        max_depth=lk_budget.max_depth,
        candidate_k=lk_budget.candidate_k,
        backtracking_width=lk_budget.backtracking_width,
        max_improvements=lk_budget.max_improvements,
    )
    return improved, two_opt_count + lk_count


def _write_edge_structure_sample_summary(
    instance: TSPInstance,
    parent_a: Tour,
    parent_b: Tour,
    operators: list[str],
    table_dir: Path,
    sample_count: int,
) -> None:
    common_edges = tour_edges(parent_a.cities) & tour_edges(parent_b.cities)
    sample_rows: list[dict[str, object]] = []
    rng = np.random.default_rng(BASE_SEED + 7)
    for name in operators:
        for sample_id in range(sample_count):
            child = Tour(
                apply_crossover(name, parent_a.cities, parent_b.cities, rng, instance)[0]
            )
            metrics = edge_recombination_metrics(
                child.cities,
                parent_a.cities,
                parent_b.cities,
            )
            child_edges = tour_edges(child.cities)
            sample_rows.append(
                {
                    "operator": name.upper(),
                    "sample_id": sample_id,
                    "common_edges": len(common_edges),
                    "common_preserved": len(child_edges & common_edges),
                    "common_broken": len(common_edges - child_edges),
                    "parent_edge_inheritance_rate": metrics[
                        "parent_edge_inheritance_rate"
                    ],
                    "common_edge_preservation_rate": metrics[
                        "common_edge_preservation_rate"
                    ],
                    "foreign_edges_count": metrics["foreign_edges_count"],
                }
            )
    _write_csv(
        table_dir / "edge_structure_metrics_samples.csv",
        _serializable_rows(sample_rows),
    )

    summary_rows = []
    for name in operators:
        group = [row for row in sample_rows if row["operator"] == name.upper()]
        summary_rows.append(
            {
                "operator": name.upper(),
                "samples": len(group),
                "mean_common_preserved": f"{_mean_metric(group, 'common_preserved'):.6f}",
                "std_common_preserved": f"{_std_metric(group, 'common_preserved'):.6f}",
                "mean_common_broken": f"{_mean_metric(group, 'common_broken'):.6f}",
                "mean_parent_edge_inheritance_rate": f"{_mean_metric(group, 'parent_edge_inheritance_rate'):.6f}",
                "mean_common_edge_preservation_rate": f"{_mean_metric(group, 'common_edge_preservation_rate'):.6f}",
                "mean_foreign_edges_count": f"{_mean_metric(group, 'foreign_edges_count'):.6f}",
                "std_foreign_edges_count": f"{_std_metric(group, 'foreign_edges_count'):.6f}",
            }
        )
    _write_csv(table_dir / "edge_structure_metrics_summary.csv", summary_rows)


def _run_convergence_experiment(
    instance: TSPInstance,
    runs: int,
    generations: int,
    pop_size: int,
    lk_budget: LKBudget,
    optimal: float | None,
    visual_dir: Path,
    table_dir: Path,
) -> list[dict[str, object]]:
    specs = [
        SolverSpec("OX + no LS (=Pure)", "ga", "ox"),
        SolverSpec("OX + 2-opt", "ma", "ox", "2-opt"),
        SolverSpec("PMX + 2-opt", "ma", "pmx", "2-opt"),
        SolverSpec("OX + LK", "ma", "ox", "lk"),
        SolverSpec("PMX + LK", "ma", "pmx", "lk"),
        SolverSpec("DPX + LK", "ma", "dpx", "lk"),
        SolverSpec("GX + LK", "ma", "gx", "lk"),
    ]
    rows = _run_specs(instance, specs, runs, generations, pop_size, lk_budget)
    _write_csv(table_dir / "convergence_raw.csv", _serializable_rows(rows))
    _write_summary(table_dir / "convergence_summary.csv", rows, optimal)
    _plot_average_convergence(rows, specs, optimal, visual_dir / "6_3_convergence_curves.png")
    return rows


def _teaching_parents(instance: TSPInstance) -> tuple[Tour, Tour]:
    """Pick two good but nonidentical parents with many shared edges."""

    parent_a, _ = two_opt_dlb(nearest_neighbor(instance, start=0), instance)
    start_b = min(30, instance.dimension - 1)
    parent_b, _ = two_opt_dlb(nearest_neighbor(instance, start=start_b), instance)
    if parent_a.cities == parent_b.cities:
        rng = np.random.default_rng(BASE_SEED + 99)
        parent_b = Tour(rng.permutation(instance.dimension).astype(int).tolist())
    return parent_a, parent_b


def _contrast_teaching_parents(instance: TSPInstance) -> tuple[Tour, Tour, int]:
    """Pick parents that make PMX common-edge loss and DPX preservation visible."""

    pool = _contrast_parent_pool(instance)
    if len(pool) > 72:
        return pool[61], pool[72], BASE_SEED + 100

    parent_a, parent_b = _teaching_parents(instance)
    return parent_a, parent_b, BASE_SEED + 100


def _contrast_parent_pool(instance: TSPInstance) -> list[Tour]:
    pool: list[Tour] = []
    seen: set[tuple[int, ...]] = set()

    for start in range(0, instance.dimension, 5):
        tour, _ = two_opt_dlb(nearest_neighbor(instance, start=start), instance)
        key = tuple(tour.cities)
        if key not in seen:
            seen.add(key)
            pool.append(tour)

    rng = np.random.default_rng(BASE_SEED + 777)
    base_tours = pool[:12]
    for tour in base_tours:
        n = len(tour.cities)
        for _ in range(6):
            cities = tour.cities.copy()
            for _ in range(2):
                i, j = sorted(rng.choice(n, size=2, replace=False).astype(int).tolist())
                if j - i < 8:
                    j = min(n - 1, i + 12)
                cities[i : j + 1] = reversed(cities[i : j + 1])
            variant, _ = two_opt_dlb(Tour(cities), instance, max_improvements=8)
            key = tuple(variant.cities)
            if key not in seen:
                seen.add(key)
                pool.append(variant)

    return pool


def _run_recombination_ablation(
    instance: TSPInstance,
    runs: int,
    generations: int,
    pop_size: int,
    lk_budget: LKBudget,
    optimal: float | None,
    existing_rows: list[dict[str, object]],
    visual_dir: Path,
    table_dir: Path,
) -> None:
    specs = [
        SolverSpec("OX + LK", "ma", "ox", "lk"),
        SolverSpec("PMX + LK", "ma", "pmx", "lk"),
        SolverSpec("DPX + LK", "ma", "dpx", "lk"),
        SolverSpec("GX + LK", "ma", "gx", "lk"),
    ]
    reusable = {
        "OX + LK": "OX + LK",
        "PMX + LK": "PMX + LK",
        "DPX + LK": "DPX + LK",
        "GX + LK": "GX + LK",
    }
    rows = []
    for spec in specs:
        source_name = reusable.get(spec.name)
        if source_name:
            rows.extend(
                {
                    **row,
                    "method": spec.name,
                }
                for row in existing_rows
                if row["method"] == source_name
            )
    missing_specs = [
        spec
        for spec in specs
        if not any(row["method"] == spec.name for row in rows)
    ]
    rows.extend(_run_specs(instance, missing_specs, runs, generations, pop_size, lk_budget))
    metric_rows = [_with_ablation_metrics(row, optimal) for row in rows]
    _write_csv(
        table_dir / "recombination_ablation_raw.csv",
        _serializable_rows(metric_rows),
    )
    summary = _write_summary(table_dir / "recombination_ablation_summary.csv", rows, optimal)
    _plot_recombination_ablation(
        summary,
        metric_rows,
        optimal,
        visual_dir / "6_4_recombination_ablation.png",
    )


def _with_ablation_metrics(
    row: dict[str, object],
    optimal: float | None,
) -> dict[str, object]:
    history = row["history"] if isinstance(row.get("history"), list) else []
    return {
        **row,
        "final_gap_pct": _gap_percent(float(row["best"]), optimal),
        "gap_auc": _gap_auc(history, optimal),  # type: ignore[arg-type]
        "runtime_s": float(row["time"]),
    }


def _edge_metric_curves(
    instance: TSPInstance,
    generations: int,
    pop_size: int,
    lk_budget: LKBudget,
    visual_dir: Path,
    table_dir: Path,
) -> None:
    rows: list[dict[str, object]] = []
    for crossover in ["ox", "pmx", "dpx", "gx"]:
        solver = MemeticAlgorithm(
            pop_size=pop_size,
            n_generations=generations,
            pc=1.0,
            pm=0.0,
            crossover=crossover,
            local_search="lk",
            lk_warm_start_max_improvements=lk_budget.warm_start_max_improvements,
            lk_max_improvements=lk_budget.max_improvements,
            lk_max_depth=lk_budget.max_depth,
            lk_candidate_k=lk_budget.candidate_k,
            lk_backtracking_width=lk_budget.backtracking_width,
            ls_strategy="full",
            seed=BASE_SEED + 200,
            show_progress=False,
            verbose=False,
        )
        solver.solve(instance)
        for generation, stats in enumerate(solver.last_stats_history, start=1):
            rows.append(
                {
                    "method": f"{crossover.upper()} + LK",
                    "generation": generation,
                    "pre_ls_common_edge_preservation_rate": stats.get(
                        "common_edge_preservation_rate", 0.0
                    ),
                    "pre_ls_parent_edge_inheritance_rate": stats.get(
                        "parent_edge_inheritance_rate", 0.0
                    ),
                    "pre_ls_foreign_edges_count": stats.get("foreign_edges_count", 0.0),
                }
            )
    _write_csv(table_dir / "edge_metric_curves.csv", _serializable_rows(rows))
    _plot_edge_metric_curves(
        rows,
        visual_dir / "6_5_edge_inheritance_foreign_edges.png",
    )


def _diversity_curves(
    instance: TSPInstance,
    generations: int,
    pop_size: int,
    lk_budget: LKBudget,
    visual_dir: Path,
    table_dir: Path,
) -> None:
    rows: list[dict[str, object]] = []
    specs = [
        SolverSpec("OX + no LS (=Pure)", "ga", "ox"),
        SolverSpec("OX + LK", "ma", "ox", "lk"),
        SolverSpec("DPX + LK", "ma", "dpx", "lk"),
        SolverSpec("GX + LK", "ma", "gx", "lk"),
    ]
    for idx, spec in enumerate(specs):
        _, _, stats_history, _ = _run_solver(
            instance,
            spec,
            seed=BASE_SEED + 300 + idx,
            generations=generations,
            pop_size=pop_size,
            lk_budget=lk_budget,
        )
        for generation, stats in enumerate(stats_history, start=1):
            rows.append(
                {
                    "method": spec.name,
                    "generation": generation,
                    "unique_tours_count": stats.get("unique_tours_count", 0),
                    "unique_edge_sets_count": stats.get("unique_edge_sets_count", 0),
                    "population_std": stats.get("population_std", 0.0),
                    "edge_diversity": stats.get("edge_diversity", 0),
                    "pairwise_edge_distance": stats.get("pairwise_edge_distance", 0.0),
                }
            )
    _write_csv(table_dir / "diversity_curves.csv", _serializable_rows(rows))
    _plot_diversity_curves(
        rows,
        visual_dir / "6_6_population_diversity.png",
    )


def _run_specs(
    instance: TSPInstance,
    specs: list[SolverSpec],
    runs: int,
    generations: int,
    pop_size: int,
    lk_budget: LKBudget,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in specs:
        for run_id in range(runs):
            seed = BASE_SEED + run_id
            best, history, _, elapsed = _run_solver(
                instance,
                spec,
                seed=seed,
                generations=generations,
                pop_size=pop_size,
                lk_budget=lk_budget,
            )
            rows.append(
                {
                    "method": spec.name,
                    "run_id": run_id,
                    "seed": seed,
                    "best": best,
                    "time": elapsed,
                    "history": history,
                }
            )
            print(f"  {spec.name} run {run_id}: best={best:.0f}, time={elapsed:.2f}s")
    return rows


def _run_solver(
    instance: TSPInstance,
    spec: SolverSpec,
    seed: int,
    generations: int,
    pop_size: int,
    lk_budget: LKBudget,
) -> tuple[float, list[float], list[dict[str, float | int]], float]:
    stats_history: list[dict[str, float | int]] = []
    start = perf_counter()
    if spec.kind == "ga":
        solver = GeneticAlgorithm(
            pop_size=pop_size,
            n_generations=generations,
            pc=spec.pc,
            pm=spec.pm,
            crossover=spec.crossover,
            seed=seed,
            show_progress=False,
        )

        def callback(
            generation: int,
            tour: Tour,
            best_length: float,
            stats: dict[str, float | int],
        ) -> None:
            del generation, tour, best_length
            stats_history.append(stats.copy())

        best_tour, history = solver.solve(instance, callback=callback)
    else:
        solver = MemeticAlgorithm(
            pop_size=pop_size,
            n_generations=generations,
            pc=spec.pc,
            pm=spec.pm,
            crossover=spec.crossover,
            local_search=spec.local_search,
            lk_warm_start_max_improvements=lk_budget.warm_start_max_improvements,
            lk_max_improvements=lk_budget.max_improvements,
            lk_max_depth=lk_budget.max_depth,
            lk_candidate_k=lk_budget.candidate_k,
            lk_backtracking_width=lk_budget.backtracking_width,
            ls_strategy="full",
            seed=seed,
            show_progress=False,
            verbose=False,
        )
        best_tour, history = solver.solve(instance)
        stats_history = solver.last_stats_history.copy()
    elapsed = perf_counter() - start
    return best_tour.length(instance), history, stats_history, elapsed


def _plot_edge_structure_panel(
    ax: plt.Axes,
    instance: TSPInstance,
    tour: Tour,
    title: str,
    common_edges: set[tuple[int, int]],
    parent_edges: set[tuple[int, int]],
) -> None:
    del parent_edges
    colors = {edge: "#2ca02c" for edge in common_edges}
    _draw_tour_edges(ax, instance, tour, colors, default_color="#b8b8b8")
    ax.set_title(title)


def _plot_common_backbone_panel(
    ax: plt.Axes,
    instance: TSPInstance,
    common_edges: set[tuple[int, int]],
    title: str,
) -> None:
    coords = instance.coords
    for a, b in common_edges:
        ax.plot(
            [coords[a, 0], coords[b, 0]],
            [coords[a, 1], coords[b, 1]],
            color="#2ca02c",
            linewidth=2.6,
            alpha=0.95,
        )
    ax.scatter(coords[:, 0], coords[:, 1], s=14, color="#222222", zorder=3)
    ax.set_title(title)
    ax.axis("equal")
    ax.axis("off")


def _plot_child_edge_panel(
    ax: plt.Axes,
    instance: TSPInstance,
    tour: Tour,
    parent_edges: set[tuple[int, int]],
    common_edges: set[tuple[int, int]],
    name: str,
) -> None:
    colors = {}
    for edge in tour_edges(tour.cities):
        if edge in common_edges:
            colors[edge] = "#2ca02c"
        elif edge in parent_edges:
            colors[edge] = "#8fb8d8"
        else:
            colors[edge] = "#d62728"
    preserved = len(tour_edges(tour.cities) & common_edges)
    foreign = len(tour_edges(tour.cities) - parent_edges)
    _draw_tour_edges(ax, instance, tour, colors, default_color="#b8b8b8")
    ax.set_title(
        f"{name.upper()} child\ncommon kept={preserved}, foreign={foreign}"
    )


def _plot_child_common_loss_panel(
    ax: plt.Axes,
    instance: TSPInstance,
    tour: Tour,
    parent_edges: set[tuple[int, int]],
    common_edges: set[tuple[int, int]],
    title: str,
    subtitle: str,
) -> None:
    child_edges = tour_edges(tour.cities)
    kept_common = child_edges & common_edges
    broken_common = common_edges - child_edges
    foreign_edges = child_edges - parent_edges

    coords = instance.coords
    for a, b in broken_common:
        ax.plot(
            [coords[a, 0], coords[b, 0]],
            [coords[a, 1], coords[b, 1]],
            color="#f28e2b",
            linewidth=2.4,
            linestyle=(0, (4, 3)),
            alpha=0.9,
            zorder=2.7,
        )

    colors = {}
    for edge in child_edges:
        if edge in common_edges:
            colors[edge] = "#2ca02c"
        elif edge in parent_edges:
            colors[edge] = "#8fb8d8"
        else:
            colors[edge] = "#d62728"
    _draw_tour_edges(ax, instance, tour, colors, default_color="#b8b8b8")
    ax.set_title(
        f"{title}\n"
        f"{subtitle}\n"
        f"common kept={len(kept_common)}/{len(common_edges)}, "
        f"broken={len(broken_common)}, foreign={len(foreign_edges)}",
        fontsize=10,
    )


def _plot_tour_with_highlights(
    ax: plt.Axes,
    instance: TSPInstance,
    tour: Tour,
    title: str,
    highlighted: set[tuple[int, int]],
    highlight_color: str,
    highlight_label: str,
) -> None:
    colors = {edge: highlight_color for edge in highlighted}
    _draw_tour_edges(ax, instance, tour, colors, default_color="#b8b8b8")
    ax.set_title(title)
    ax.plot([], [], color=highlight_color, linewidth=2.4, label=highlight_label)
    ax.legend(loc="best", fontsize=8)


def _draw_tour_edges(
    ax: plt.Axes,
    instance: TSPInstance,
    tour: Tour,
    colors: dict[tuple[int, int], str],
    default_color: str,
) -> None:
    coords = instance.coords
    for idx, city in enumerate(tour.cities):
        nxt = tour.cities[(idx + 1) % len(tour.cities)]
        edge = _edge(city, nxt)
        color = colors.get(edge, default_color)
        if color == "#d62728":
            linewidth = 2.8
            alpha = 0.92
            zorder = 2.5
        elif color == "#2ca02c":
            linewidth = 2.3
            alpha = 0.9
            zorder = 2.0
        elif color == "#8fb8d8":
            linewidth = 1.7
            alpha = 0.72
            zorder = 1.5
        else:
            linewidth = 0.9
            alpha = 0.6
            zorder = 1.0
        ax.plot(
            [coords[city, 0], coords[nxt, 0]],
            [coords[city, 1], coords[nxt, 1]],
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            zorder=zorder,
        )
    ax.scatter(coords[:, 0], coords[:, 1], s=14, color="#222222", zorder=3)
    ax.axis("equal")
    ax.axis("off")


def _plot_average_convergence(
    rows: list[dict[str, object]],
    specs: list[SolverSpec],
    optimal: float | None,
    path: Path,
) -> None:
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(14.5, 5.5),
        gridspec_kw={"width_ratios": [1.0, 1.2]},
    )
    histories_by_method: dict[str, list[list[float]]] = {}
    curves: dict[str, tuple[list[float], list[float]]] = {}
    for spec in specs:
        histories = [row["history"] for row in rows if row["method"] == spec.name]
        histories = [history for history in histories if isinstance(history, list)]
        if not histories:
            continue
        histories_by_method[spec.name] = histories
        curves[spec.name] = _mean_sem_histories(histories)

    method_colors = {
        "OX + no LS (=Pure)": "#1f77b4",
        "OX + 2-opt": "#ff7f0e",
        "PMX + 2-opt": "#2ca02c",
        "OX + LK": "#d62728",
        "PMX + LK": "#9467bd",
        "DPX + LK": "#8c564b",
        "GX + LK": "#e377c2",
    }

    for spec in specs:
        stats = curves.get(spec.name)
        if not stats:
            continue
        avg, _sem = stats
        x_values = list(range(1, len(avg) + 1))
        is_no_ls = spec.name == "OX + no LS (=Pure)"
        axes[0].plot(
            x_values,
            avg,
            color=method_colors.get(spec.name),
            linewidth=1.5 if is_no_ls else 2.1,
            marker="o",
            markersize=3.8,
            label=spec.name,
            zorder=3,
        )
    if optimal is not None:
        axes[0].axhline(
            optimal,
            color="black",
            linestyle="--",
            linewidth=1.1,
            label="Optimum",
        )
    axes[0].set_xlabel("Generation")
    axes[0].grid(alpha=0.25)

    zoom_methods = ["OX + LK", "PMX + LK", "DPX + LK", "GX + LK"]
    zoom_values: list[float] = []
    for method in zoom_methods:
        stats = curves.get(method)
        if not stats:
            continue
        avg, _sem = stats
        x_values = list(range(1, len(avg) + 1))
        if optimal is None:
            y_values = avg
        else:
            y_values = [_gap_percent(value, optimal) for value in avg]
        zoom_values.extend(y_values)
        axes[1].plot(
            x_values,
            y_values,
            color=method_colors.get(method),
            linewidth=2.2,
            marker="o",
            markersize=4.0,
            label=method,
            zorder=3,
        )
    if optimal is not None:
        axes[1].axhline(0.0, color="black", linestyle="--", linewidth=1.1)
    axes[1].set_xlabel("Generation")
    axes[1].grid(alpha=0.25)

    axes[0].set_ylabel("Best tour length")
    max_generations = max((len(avg) for avg, _sem in curves.values()), default=0)
    axes[0].set_title(f"{max_generations}-generation overview: mean best-so-far")
    axes[1].set_ylabel("Gap to optimum (%)" if optimal is not None else "Best tour length")
    axes[1].set_title("Zoom: LK crossover variants")
    if zoom_values:
        low = min(zoom_values)
        high = max(zoom_values)
        pad = max(0.03 if optimal is not None else 3.0, (high - low) * 0.18)
        axes[1].set_ylim(low - pad, high + pad)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("Convergence under one GA framework in the critical LK regime")
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.18, top=0.86)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_recombination_ablation(
    summary: list[dict[str, object]],
    rows: list[dict[str, object]],
    optimal: float | None,
    path: Path,
) -> None:
    summary_methods = {str(row["method"]) for row in summary}
    preferred_order = [
        "OX + LK",
        "PMX + LK",
        "DPX + LK",
        "GX + LK",
    ]
    ordered_methods = [method for method in preferred_order if method in summary_methods]
    ordered_methods.extend(sorted(summary_methods - set(ordered_methods)))
    positions = {method: idx for idx, method in enumerate(ordered_methods)}
    labels = [method.replace(" + ", "\n+ ") for method in ordered_methods]
    colors = {
        "OX + LK": "#4c78a8",
        "PMX + LK": "#72b7b2",
        "DPX + LK": "#f58518",
        "GX + LK": "#e45756",
    }

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.4))
    metrics = [
        (
            axes[0],
            "final_gap_pct",
            "Final gap (%)",
            "Final quality",
        ),
        (
            axes[1],
            "gap_auc",
            "Gap AUC",
            "Convergence area",
        ),
        (axes[2], "runtime_s", "Runtime (s)", "Runtime"),
    ]

    for ax, metric, ylabel, title in metrics:
        means: list[float] = []
        sems: list[float] = []
        bar_colors: list[str] = []
        for method in ordered_methods:
            group = [row for row in rows if row["method"] == method]
            values = [float(row[metric]) for row in group]
            values = [value for value in values if not np.isnan(value)]
            means.append(mean(values) if values else float("nan"))
            sems.append(_sem(values) if values else 0.0)
            bar_colors.append(colors.get(method, "#666666"))
        ax.bar(
            range(len(ordered_methods)),
            means,
            yerr=sems,
            color=bar_colors,
            alpha=0.58,
            edgecolor="#222222",
            linewidth=0.8,
            capsize=4,
            error_kw={"elinewidth": 1.2, "capthick": 1.2},
            zorder=2,
        )
        for method in ordered_methods:
            group = [row for row in rows if row["method"] == method]
            values = [float(row[metric]) for row in group]
            values = [value for value in values if not np.isnan(value)]
            if not values:
                continue
            color = colors.get(method, "#666666")
            n = len(values)
            jitter_step = min(0.045, 0.34 / max(1, n))
            for idx, value in enumerate(values):
                offset = (idx - (n - 1) / 2) * jitter_step
                ax.scatter(
                    positions[method] + offset,
                    value,
                    color=color,
                    s=38,
                    alpha=0.72,
                    edgecolor="black",
                    linewidth=0.35,
                    zorder=4,
                )
        ax.set_ylabel(ylabel)
        ax.set_title(title)

    for ax in axes:
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels)
        ax.grid(axis="y", alpha=0.25)

    runs = max(int(row["runs"]) for row in summary)
    fig.suptitle(
        f"Recombination ablation with fixed LK: bars are mean +/- SEM, dots are seeds (N={runs})"
    )
    fig.tight_layout()
    fig.subplots_adjust(top=0.83)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_edge_metric_curves(
    rows: list[dict[str, object]],
    path: Path,
) -> None:
    max_generation = max(int(row["generation"]) for row in rows)
    focus_generation = min(10, max_generation)
    focus_rows = [row for row in rows if int(row["generation"]) <= focus_generation]
    methods = _ordered_methods(focus_rows)
    metrics = [
        (
            "pre_ls_common_edge_preservation_rate",
            "Common-edge preservation",
            "Rate",
        ),
        (
            "pre_ls_parent_edge_inheritance_rate",
            "Parent-edge inheritance",
            "Rate",
        ),
        (
            "pre_ls_foreign_edges_count",
            "Foreign edges before local search",
            "Edges",
        ),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), sharex=True)
    for ax, (metric, title, ylabel) in zip(axes, metrics, strict=True):
        for method in methods:
            group = [row for row in focus_rows if row["method"] == method]
            group.sort(key=lambda row: int(row["generation"]))
            ax.plot(
                [int(row["generation"]) for row in group],
                [float(row[metric]) for row in group],
                linewidth=2.0,
                marker="o",
                markersize=3.2,
                label=method,
            )
        ax.set_title(title)
        ax.set_xlabel("Generation")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.25)
    axes[0].set_ylim(0.85, 1.02)
    axes[1].set_ylim(0.55, 1.02)
    axes[0].legend(loc="lower right", fontsize=8)
    fig.suptitle("Early pre-LS edge metrics under the critical LK budget")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_diversity_curves(
    rows: list[dict[str, object]],
    path: Path,
) -> None:
    methods = _ordered_methods(rows)
    metrics = [
        ("unique_edge_sets_count", "Unique edge sets", "Count"),
        ("edge_diversity", "Union of edges in population", "Edges"),
        ("pairwise_edge_distance", "Mean pairwise edge distance", "Edges"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), sharex=True)
    for ax, (metric, title, ylabel) in zip(axes, metrics, strict=True):
        for method in methods:
            group = [row for row in rows if row["method"] == method]
            group.sort(key=lambda row: int(row["generation"]))
            ax.plot(
                [int(row["generation"]) for row in group],
                [float(row[metric]) for row in group],
                linewidth=2.0,
                marker="o",
                markersize=3.0,
                label=method,
            )
        ax.set_title(title)
        ax.set_xlabel("Generation")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.25)
    axes[0].legend(loc="upper right", fontsize=8)
    fig.suptitle(
        "Population diversity: edge-based measures avoid length-std compression"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_metric_curves(
    rows: list[dict[str, object]],
    metrics: list[str],
    path: Path,
    title: str | None = None,
) -> None:
    methods = sorted({str(row["method"]) for row in rows})
    fig, axes = plt.subplots(len(metrics), 1, figsize=(9, 3.2 * len(metrics)), sharex=True)
    if len(metrics) == 1:
        axes = [axes]
    for ax, metric in zip(axes, metrics, strict=True):
        for method in methods:
            group = [row for row in rows if row["method"] == method]
            group.sort(key=lambda row: int(row["generation"]))
            ax.plot(
                [int(row["generation"]) for row in group],
                [float(row[metric]) for row in group],
                linewidth=1.6,
                label=method,
            )
        ax.set_ylabel(metric)
        ax.grid(alpha=0.25)
    axes[-1].set_xlabel("Generation")
    axes[0].legend(loc="best")
    if title:
        fig.suptitle(title)
        fig.tight_layout(rect=(0, 0, 1, 0.97))
    else:
        fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_summary(
    path: Path,
    rows: list[dict[str, object]],
    optimal: float | None,
) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    for method in sorted({str(row["method"]) for row in rows}):
        group = [row for row in rows if row["method"] == method]
        best_values = [float(row["best"]) for row in group]
        times = [float(row["time"]) for row in group]
        histories = [row["history"] for row in group if isinstance(row.get("history"), list)]
        mean_best = mean(best_values)
        best = min(best_values)
        gap_values = [_gap_percent(value, optimal) for value in best_values]
        mean_gap = _gap_percent(mean_best, optimal)
        best_gap = _gap_percent(best, optimal)
        generation_to_target = [
            _generation_to_gap(history, optimal, target_gap_percent=0.1)
            for history in histories  # type: ignore[arg-type]
        ]
        target_hits = [value for value in generation_to_target if value is not None]
        gap_auc = [
            _gap_auc(history, optimal)
            for history in histories  # type: ignore[arg-type]
        ]
        summary.append(
            {
                "method": method,
                "runs": len(group),
                "mean_best": f"{mean_best:.6f}",
                "std_best": f"{_std_values(best_values):.6f}",
                "sem_best": f"{_sem(best_values):.6f}",
                "best": f"{best:.6f}",
                "mean_gap_percent": f"{mean_gap:.6f}",
                "std_gap_percent": f"{_std_values(gap_values):.6f}",
                "sem_gap_percent": f"{_sem(gap_values):.6f}",
                "best_gap_percent": f"{best_gap:.6f}",
                "hit_rate_to_0.1pct_gap": f"{len(target_hits) / len(generation_to_target):.6f}"
                if generation_to_target
                else "",
                "mean_generation_to_0.1pct_gap_hits": f"{mean(target_hits):.6f}"
                if target_hits
                else "",
                "mean_gap_auc": f"{mean(gap_auc):.6f}" if gap_auc else "",
                "std_gap_auc": f"{_std_values(gap_auc):.6f}" if gap_auc else "",
                "sem_gap_auc": f"{_sem(gap_auc):.6f}" if gap_auc else "",
                "mean_time": f"{mean(times):.6f}",
                "std_time": f"{_std_values(times):.6f}",
                "sem_time": f"{_sem(times):.6f}",
            }
        )
    _write_csv(path, summary)
    return summary


def _mean_metric(rows: list[dict[str, object]], key: str) -> float:
    return mean(float(row[key]) for row in rows) if rows else float("nan")


def _std_metric(rows: list[dict[str, object]], key: str) -> float:
    values = [float(row[key]) for row in rows]
    return stdev(values) if len(values) > 1 else 0.0


def _std_values(values: list[float]) -> float:
    return stdev(values) if len(values) > 1 else 0.0


def _sem(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return stdev(values) / (len(values) ** 0.5)


def _ordered_methods(rows: list[dict[str, object]]) -> list[str]:
    preferred = [
        "OX + no LS (=Pure)",
        "OX + 2-opt",
        "PMX + 2-opt",
        "OX + LK",
        "PMX + LK",
        "DPX + LK",
        "GX + LK",
    ]
    present = {str(row["method"]) for row in rows}
    ordered = [method for method in preferred if method in present]
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def _gap_percent(value: float, optimal: float | None) -> float:
    if optimal is None:
        return float("nan")
    return (value - optimal) / optimal * 100.0


def _generation_to_gap(
    history: list[float],
    optimal: float | None,
    target_gap_percent: float,
) -> float | None:
    if optimal is None or not history:
        return None
    for generation, value in enumerate(history, start=1):
        if _gap_percent(value, optimal) <= target_gap_percent:
            return float(generation)
    return None


def _gap_auc(history: list[float], optimal: float | None) -> float:
    if optimal is None or not history:
        return float("nan")
    gaps = [max(0.0, _gap_percent(value, optimal)) for value in history]
    return float(sum(gaps))


def _average_histories(histories: list[list[float]]) -> list[float]:
    max_len = max(len(history) for history in histories)
    padded = []
    for history in histories:
        if len(history) < max_len:
            history = history + [history[-1]] * (max_len - len(history))
        padded.append(history)
    return np.mean(np.array(padded, dtype=np.float64), axis=0).tolist()


def _mean_sem_histories(histories: list[list[float]]) -> tuple[list[float], list[float]]:
    max_len = max(len(history) for history in histories)
    padded = []
    for history in histories:
        if len(history) < max_len:
            history = history + [history[-1]] * (max_len - len(history))
        padded.append(history)
    values = np.array(padded, dtype=np.float64)
    means = np.mean(values, axis=0)
    if values.shape[0] <= 1:
        sems = np.zeros(values.shape[1], dtype=np.float64)
    else:
        sems = np.std(values, axis=0, ddof=1) / np.sqrt(values.shape[0])
    return means.tolist(), sems.tolist()


def _serializable_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        converted = dict(row)
        if isinstance(converted.get("history"), list):
            converted["history"] = ";".join(
                f"{float(value):.10f}" for value in converted["history"]  # type: ignore[index]
            )
        output.append(converted)
    return output


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _edge(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


if __name__ == "__main__":
    main()
