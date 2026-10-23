from __future__ import annotations

import argparse
import csv
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from time import perf_counter

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ga import GeneticAlgorithm
from src.instance import TSPInstance
from src.lin_kernighan import lin_kernighan
from src.memetic import MemeticAlgorithm
from src.operators import apply_crossover
from src.tour import Tour
from src.two_opt import two_opt_dlb


OPTIMAL = {
    "ch130": 6110.0,
    "kroA200": 29368.0,
    "pcb442": 50778.0,
    "d493": 35002.0,
    "rat575": 6773.0,
    "p654": 34643.0,
    "d657": 48912.0,
    "rat783": 8806.0,
    "pr1002": 259045.0,
    "pcb1173": 56892.0,
    "d1291": 50801.0,
}

BASE_SEED = 20260617


@dataclass(frozen=True)
class SolverSpec:
    name: str
    kind: str
    crossover: str
    local_search: str = "2-opt"
    pc: float = 0.9
    pm: float = 0.2


@dataclass(frozen=True)
class LKBudget:
    warm_start_max_improvements: int
    max_improvements: int
    max_depth: int
    candidate_k: int
    backtracking_width: int


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pilot larger TSPLIB instances under bounded local search."
    )
    parser.add_argument("--instances", nargs="+", default=["d493"])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--generations", type=int, default=4)
    parser.add_argument("--pop-size", type=int, default=4)
    parser.add_argument("--ls-step-budget", type=int, default=12)
    parser.add_argument("--lk-warm-start-max-improvements", type=int, default=12)
    parser.add_argument("--lk-max-improvements", type=int, default=1)
    parser.add_argument("--lk-max-depth", type=int, default=2)
    parser.add_argument("--lk-candidate-k", type=int, default=5)
    parser.add_argument("--lk-backtracking-width", type=int, default=1)
    parser.add_argument("--profile-trials", type=int, default=1)
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Parallel solver workers. Use 0 for a conservative CPU-count default.",
    )
    args = parser.parse_args()

    if args.runs <= 0:
        parser.error("--runs must be positive")
    if args.generations <= 0:
        parser.error("--generations must be positive")
    if args.pop_size <= 1:
        parser.error("--pop-size must be greater than 1")
    if args.ls_step_budget < 0:
        parser.error("--ls-step-budget must be non-negative")
    if args.workers < 0:
        parser.error("--workers must be non-negative")

    budget = LKBudget(
        warm_start_max_improvements=args.lk_warm_start_max_improvements,
        max_improvements=args.lk_max_improvements,
        max_depth=args.lk_max_depth,
        candidate_k=args.lk_candidate_k,
        backtracking_width=args.lk_backtracking_width,
    )

    table_dir = ROOT / "results" / "paper_tables"
    figure_dir = ROOT / "report" / "figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    specs = [
        SolverSpec("OX + no LS", "ga", "ox"),
        SolverSpec("OX + 2-opt", "ma", "ox", "2-opt"),
        SolverSpec("PMX + 2-opt", "ma", "pmx", "2-opt"),
        SolverSpec("DPX + 2-opt", "ma", "dpx", "2-opt"),
        SolverSpec("GX + 2-opt", "ma", "gx", "2-opt"),
        SolverSpec("OX + L-K", "ma", "ox", "lk"),
        SolverSpec("PMX + L-K", "ma", "pmx", "lk"),
        SolverSpec("DPX + L-K", "ma", "dpx", "lk"),
        SolverSpec("GX + L-K", "ma", "gx", "lk"),
    ]
    workers = _resolve_workers(args.workers)

    metadata = {
        "instances": " ".join(args.instances),
        "runs": args.runs,
        "generations": args.generations,
        "pop_size": args.pop_size,
        "ls_step_budget": args.ls_step_budget,
        "lk_warm_start_max_improvements": budget.warm_start_max_improvements,
        "lk_max_improvements": budget.max_improvements,
        "lk_max_depth": budget.max_depth,
        "lk_candidate_k": budget.candidate_k,
        "lk_backtracking_width": budget.backtracking_width,
        "base_seed": BASE_SEED,
        "workers": workers,
    }
    _write_csv(table_dir / "large_instance_pilot_metadata.csv", [metadata])

    raw_rows: list[dict[str, object]] = []
    profile_rows: list[dict[str, object]] = []
    tasks: list[
        tuple[str, SolverSpec, int, int, int, int, int, LKBudget]
    ] = []
    for instance_index, instance_name in enumerate(args.instances):
        instance = _load_instance(instance_name)
        print(f"\n== {instance_name} ({instance.dimension} cities) ==")
        profile_rows.extend(
            _profile_components(
                instance,
                trials=args.profile_trials,
                two_opt_budget=args.ls_step_budget,
                lk_budget=budget,
                seed=BASE_SEED + instance_index * 1000,
            )
        )
        for spec in specs:
            for run_id in range(args.runs):
                seed = BASE_SEED + instance_index * 1000 + run_id
                tasks.append(
                    (
                        instance_name,
                        spec,
                        seed,
                        run_id,
                        args.generations,
                        args.pop_size,
                        args.ls_step_budget,
                        budget,
                    )
                )
    print(f"\nRunning {len(tasks)} solver tasks with workers={workers}")
    for row in _run_tasks(tasks, workers):
        raw_rows.append(row)
        print(
            f"  {row['instance']:<8} {row['method']:<22} run={row['run_id']:<2} "
            f"gap={row['final_gap_pct']:.3f}% time={row['runtime_s']:.2f}s"
        )

    summary_rows = _summarize(raw_rows)
    _write_csv(table_dir / "large_instance_pilot_raw.csv", raw_rows)
    _write_csv(table_dir / "large_instance_pilot_summary.csv", summary_rows)
    _write_csv(table_dir / "large_instance_runtime_profile.csv", profile_rows)
    _plot_convergence(
        raw_rows,
        args.instances,
        figure_dir / "6_3_large_instance_pilot.png",
    )
    _plot_summary(
        summary_rows,
        args.instances,
        figure_dir / "6_4_large_instance_pilot_summary.png",
    )

    print("\nWrote:")
    print(f"  {table_dir / 'large_instance_pilot_raw.csv'}")
    print(f"  {table_dir / 'large_instance_pilot_summary.csv'}")
    print(f"  {table_dir / 'large_instance_runtime_profile.csv'}")
    print(f"  {figure_dir / '6_3_large_instance_pilot.png'}")
    print(f"  {figure_dir / '6_4_large_instance_pilot_summary.png'}")


def _load_instance(name: str) -> TSPInstance:
    path = ROOT / "data" / "tsplib" / f"{name}.tsp"
    if not path.exists():
        raise FileNotFoundError(path)
    return TSPInstance.load_tsplib(path)


def _resolve_workers(requested: int) -> int:
    if requested > 0:
        return requested
    cpu_count = os.cpu_count() or 1
    return max(1, min(4, cpu_count - 1))


def _run_tasks(
    tasks: list[tuple[str, SolverSpec, int, int, int, int, int, LKBudget]],
    workers: int,
) -> list[dict[str, object]]:
    if workers <= 1 or len(tasks) <= 1:
        return [_solve_task(task) for task in tasks]

    rows: list[dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_solve_task, task) for task in tasks]
        for future in as_completed(futures):
            rows.append(future.result())
    return rows


def _solve_task(
    task: tuple[str, SolverSpec, int, int, int, int, int, LKBudget],
) -> dict[str, object]:
    (
        instance_name,
        spec,
        seed,
        run_id,
        generations,
        pop_size,
        ls_step_budget,
        lk_budget,
    ) = task
    instance = _load_instance(instance_name)
    best, history, elapsed = _run_solver(
        instance=instance,
        spec=spec,
        seed=seed,
        generations=generations,
        pop_size=pop_size,
        ls_step_budget=ls_step_budget,
        lk_budget=lk_budget,
    )
    optimal = OPTIMAL.get(instance_name)
    return {
        "instance": instance_name,
        "dimension": instance.dimension,
        "method": spec.name,
        "run_id": run_id,
        "seed": seed,
        "best": best,
        "final_gap_pct": _gap(best, optimal),
        "gap_auc": _gap_auc(history, optimal),
        "runtime_s": elapsed,
        "history": " ".join(f"{value:.6f}" for value in history),
    }


def _run_solver(
    instance: TSPInstance,
    spec: SolverSpec,
    seed: int,
    generations: int,
    pop_size: int,
    ls_step_budget: int,
    lk_budget: LKBudget,
) -> tuple[float, list[float], float]:
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
        best_tour, history = solver.solve(instance)
    else:
        ls_strategy = "full" if spec.local_search == "lk" else "bounded"
        solver = MemeticAlgorithm(
            pop_size=pop_size,
            n_generations=generations,
            pc=spec.pc,
            pm=spec.pm,
            crossover=spec.crossover,
            local_search=spec.local_search,
            ls_strategy=ls_strategy,
            ls_max_iter=ls_step_budget,
            lk_warm_start_max_improvements=lk_budget.warm_start_max_improvements,
            lk_max_improvements=lk_budget.max_improvements,
            lk_max_depth=lk_budget.max_depth,
            lk_candidate_k=lk_budget.candidate_k,
            lk_backtracking_width=lk_budget.backtracking_width,
            seed=seed,
            show_progress=False,
            verbose=False,
        )
        best_tour, history = solver.solve(instance)
    return best_tour.length(instance), history, perf_counter() - start


def _profile_components(
    instance: TSPInstance,
    trials: int,
    two_opt_budget: int,
    lk_budget: LKBudget,
    seed: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    rng = np.random.default_rng(seed)
    p1 = rng.permutation(instance.dimension).astype(int).tolist()
    p2 = rng.permutation(instance.dimension).astype(int).tolist()
    for name in ["ox", "pmx", "dpx", "gx"]:
        start = perf_counter()
        for _ in range(trials):
            apply_crossover(name, p1, p2, rng, instance)
        rows.append(
            {
                "instance": instance.name,
                "dimension": instance.dimension,
                "component": f"{name}_crossover",
                "trials": trials,
                "total_s": perf_counter() - start,
            }
        )

    two_opt_times: list[float] = []
    lk_times: list[float] = []
    for _ in range(max(1, min(3, trials))):
        tour = Tour(rng.permutation(instance.dimension).astype(int).tolist())
        start = perf_counter()
        warmed, _ = two_opt_dlb(
            tour,
            instance,
            max_improvements=two_opt_budget,
        )
        two_opt_times.append(perf_counter() - start)

        start = perf_counter()
        lin_kernighan(
            warmed,
            instance,
            max_depth=lk_budget.max_depth,
            candidate_k=lk_budget.candidate_k,
            backtracking_width=lk_budget.backtracking_width,
            max_improvements=lk_budget.max_improvements,
        )
        lk_times.append(perf_counter() - start)

    rows.append(
        {
            "instance": instance.name,
            "dimension": instance.dimension,
            "component": f"two_opt_{two_opt_budget}_improvements",
            "trials": len(two_opt_times),
            "total_s": sum(two_opt_times),
            "mean_s": mean(two_opt_times),
        }
    )
    rows.append(
        {
            "instance": instance.name,
            "dimension": instance.dimension,
            "component": "bounded_lk_after_warm_start",
            "trials": len(lk_times),
            "total_s": sum(lk_times),
            "mean_s": mean(lk_times),
        }
    )
    return rows


def _gap(value: float, optimal: float | None) -> float:
    if optimal is None:
        return float("nan")
    return (value - optimal) / optimal * 100.0


def _gap_auc(history: list[float], optimal: float | None) -> float:
    if optimal is None or not history:
        return float("nan")
    gaps = [_gap(value, optimal) for value in history]
    return float(np.trapz(gaps, dx=1.0))


def _summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["instance"]), str(row["method"])), []).append(row)

    summary: list[dict[str, object]] = []
    for (instance, method), group in sorted(grouped.items()):
        gaps = [float(row["final_gap_pct"]) for row in group]
        aucs = [float(row["gap_auc"]) for row in group]
        times = [float(row["runtime_s"]) for row in group]
        summary.append(
            {
                "instance": instance,
                "method": method,
                "runs": len(group),
                "final_gap_mean_pct": mean(gaps),
                "final_gap_sd_pct": stdev(gaps) if len(gaps) > 1 else 0.0,
                "gap_auc_mean": mean(aucs),
                "gap_auc_sd": stdev(aucs) if len(aucs) > 1 else 0.0,
                "runtime_mean_s": mean(times),
                "runtime_sd_s": stdev(times) if len(times) > 1 else 0.0,
            }
        )
    return summary


def _plot_convergence(
    rows: list[dict[str, object]],
    instances: list[str],
    path: Path,
) -> None:
    if len(instances) != 1:
        _plot_convergence_simple(rows, instances, path)
        return

    instance = instances[0]
    series = _convergence_series(rows, instance)
    non_baseline_values = [
        value
        for method, _, values in series
        if method != "OX + no LS"
        for value in values
        if not np.isnan(value)
    ]
    zoom_min = max(0.0, min(non_baseline_values) - 0.35)
    zoom_max = max(non_baseline_values) + 0.35

    fig, (ax_overview, ax_zoom) = plt.subplots(
        1,
        2,
        figsize=(12.8, 4.8),
        gridspec_kw={"width_ratios": [1.0, 1.3]},
    )
    colors = _method_palette()
    for method, xs, values in series:
        color = colors.get(method)
        linewidth = 2.6 if method.endswith("L-K") else 2.1
        if method != "OX + no LS":
            ax_zoom.plot(xs, values, linewidth=linewidth, color=color, label=method)
        ax_overview.plot(xs, values, linewidth=linewidth, color=color, label=method)

    ax_overview.set_title("Overview")
    ax_overview.set_xlabel("Generation")
    ax_overview.set_ylabel("Best-so-far gap (%)")
    ax_overview.grid(True, color="#e8e8e8", linewidth=0.8)
    ax_overview.legend(loc="center right", fontsize=8.5, frameon=True)

    run_count = _run_count(rows, instance)
    ax_zoom.set_title(f"{instance} zoom (N={run_count})")
    ax_zoom.set_ylim(zoom_min, zoom_max)
    ax_zoom.set_xlabel("Generation")
    ax_zoom.grid(True, color="#e8e8e8", linewidth=0.8)

    fig.suptitle("Large-instance pilot: 2-opt vs L-K")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_summary(
    rows: list[dict[str, object]],
    instances: list[str],
    path: Path,
) -> None:
    if len(instances) != 1:
        _plot_summary_simple(rows, instances, path)
        return

    methods = _display_methods(
        _ordered_methods(list(dict.fromkeys(str(row["method"]) for row in rows)))
    )
    palette = _method_palette()
    instance = instances[0]
    lookup = {(row["instance"], row["method"]): row for row in rows}
    zoom_methods = [method for method in methods if method != "OX + no LS"]
    fig, (ax_overview, ax_zoom) = plt.subplots(
        1,
        2,
        figsize=(13.2, 4.9),
        gridspec_kw={"width_ratios": [1.0, 1.35]},
    )
    _draw_summary_bars(ax_overview, instance, methods, lookup, palette)
    _draw_summary_bars(ax_zoom, instance, zoom_methods, lookup, palette)

    zoom_values = [
        float(lookup[(instance, method)]["final_gap_mean_pct"])
        for method in zoom_methods
        if (instance, method) in lookup
    ]
    ax_zoom.set_ylim(0, max(zoom_values) + 1.0)
    ax_overview.set_title("Overview")
    ax_zoom.set_title(f"{instance} zoom")

    fig.suptitle("Large-instance pilot: final quality")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_convergence_simple(
    rows: list[dict[str, object]],
    instances: list[str],
    path: Path,
) -> None:
    colors = _method_palette()
    fig, axes = plt.subplots(
        1,
        len(instances),
        figsize=(6.4 * len(instances), 4.6),
        squeeze=False,
    )
    for ax, instance in zip(axes[0], instances):
        for method, xs, values in _convergence_series(rows, instance):
            ax.plot(
                xs,
                values,
                linewidth=2.0,
                color=colors.get(method, None),
                label=method,
            )
        ax.set_title(instance)
        ax.set_xlabel("Generation")
        ax.set_ylabel("Best-so-far gap (%)")
        ax.grid(True, color="#e8e8e8", linewidth=0.8)
    axes[0, 0].legend(loc="best", fontsize=9)
    fig.suptitle("Large-instance pilot: 2-opt vs L-K")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_summary_simple(
    rows: list[dict[str, object]],
    instances: list[str],
    path: Path,
) -> None:
    methods = _display_methods(
        _ordered_methods(list(dict.fromkeys(str(row["method"]) for row in rows)))
    )
    palette = _method_palette()
    fig, axes = plt.subplots(
        1,
        len(instances),
        figsize=(6.8 * len(instances), 4.4),
        squeeze=False,
    )
    lookup = {(row["instance"], row["method"]): row for row in rows}
    for ax, instance in zip(axes[0], instances):
        _draw_summary_bars(ax, instance, methods, lookup, palette)
        ax.set_title(instance)
    fig.suptitle("Large-instance pilot: final quality")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _convergence_series(
    rows: list[dict[str, object]],
    instance: str,
) -> list[tuple[str, list[int], list[float]]]:
    inst_rows = [row for row in rows if row["instance"] == instance]
    methods = _display_methods(
        _ordered_methods(
        list(dict.fromkeys(str(row["method"]) for row in inst_rows))
        )
    )
    series: list[tuple[str, list[int], list[float]]] = []
    for method in methods:
        histories = [
            [float(value) for value in str(row["history"]).split()]
            for row in inst_rows
            if row["method"] == method
        ]
        if not histories:
            continue
        max_len = max(len(history) for history in histories)
        padded = np.full((len(histories), max_len), np.nan)
        for idx, history in enumerate(histories):
            padded[idx, : len(history)] = history
        optimal = OPTIMAL.get(instance)
        mean_history = np.nanmean(padded, axis=0)
        y = (
            [_gap(value, optimal) for value in mean_history]
            if optimal is not None
            else [float(value) for value in mean_history]
        )
        series.append((method, list(range(1, len(y) + 1)), y))
    return series


def _draw_summary_bars(
    ax: plt.Axes,
    instance: str,
    methods: list[str],
    lookup: dict[tuple[object, object], dict[str, object]],
    palette: dict[str, str],
) -> None:
    values = [
        float(lookup[(instance, method)]["final_gap_mean_pct"])
        if (instance, method) in lookup
        else float("nan")
        for method in methods
    ]
    errors = [
        float(lookup[(instance, method)]["final_gap_sd_pct"])
        if (instance, method) in lookup
        else 0.0
        for method in methods
    ]
    x = np.arange(len(methods))
    colors = [palette.get(method, "#8c8c8c") for method in methods]
    ax.bar(x, values, yerr=errors, color=colors, edgecolor="white", linewidth=0.8)
    ax.set_ylabel("Final gap (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(methods, rotation=35, ha="right")
    ax.grid(axis="y", color="#e8e8e8", linewidth=0.8)


def _method_palette() -> dict[str, str]:
    return {
        "OX + no LS": "#8c8c8c",
        "OX + 2-opt": "#f28e2b",
        "PMX + 2-opt": "#ffbe7d",
        "DPX + 2-opt": "#8cd17d",
        "GX + 2-opt": "#ff9d9a",
        "OX + bounded 2-opt": "#f28e2b",
        "PMX + bounded 2-opt": "#ffbe7d",
        "DPX + bounded 2-opt": "#8cd17d",
        "GX + bounded 2-opt": "#ff9d9a",
        "OX + full 2-opt": "#f28e2b",
        "PMX + full 2-opt": "#ffbe7d",
        "DPX + full 2-opt": "#8cd17d",
        "GX + full 2-opt": "#ff9d9a",
        "OX + bounded LK": "#4e79a7",
        "PMX + bounded LK": "#b07aa1",
        "DPX + bounded LK": "#59a14f",
        "GX + bounded LK": "#e15759",
        "OX + L-K": "#4e79a7",
        "PMX + L-K": "#b07aa1",
        "DPX + L-K": "#59a14f",
        "GX + L-K": "#e15759",
        "OX + stronger LK": "#4e79a7",
        "PMX + stronger LK": "#b07aa1",
        "DPX + stronger LK": "#59a14f",
        "GX + stronger LK": "#e15759",
    }


def _run_count(rows: list[dict[str, object]], instance: str) -> int:
    run_ids = {
        int(row["run_id"])
        for row in rows
        if row["instance"] == instance and str(row["method"]) != "OX + no LS"
    }
    return len(run_ids)


def _ordered_methods(methods: list[str]) -> list[str]:
    preferred = [
        "OX + no LS",
        "OX + 2-opt",
        "PMX + 2-opt",
        "DPX + 2-opt",
        "GX + 2-opt",
        "OX + bounded 2-opt",
        "PMX + bounded 2-opt",
        "DPX + bounded 2-opt",
        "GX + bounded 2-opt",
        "OX + full 2-opt",
        "PMX + full 2-opt",
        "DPX + full 2-opt",
        "GX + full 2-opt",
        "OX + bounded LK",
        "PMX + bounded LK",
        "DPX + bounded LK",
        "GX + bounded LK",
        "OX + L-K",
        "PMX + L-K",
        "DPX + L-K",
        "GX + L-K",
        "OX + stronger LK",
        "PMX + stronger LK",
        "DPX + stronger LK",
        "GX + stronger LK",
    ]
    rank = {method: idx for idx, method in enumerate(preferred)}
    return sorted(methods, key=lambda method: (rank.get(method, len(preferred)), method))


def _display_methods(methods: list[str]) -> list[str]:
    return methods


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
