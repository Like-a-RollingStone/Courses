from __future__ import annotations

import argparse
import csv
import math
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
from src.memetic import MemeticAlgorithm


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

BASE_SEED = 20260619


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
    label: str
    warm_start_max_improvements: int | None
    max_improvements: int | None
    max_depth: int
    candidate_k: int | None
    backtracking_width: int


@dataclass(frozen=True)
class Task:
    experiment: str
    instance_name: str
    spec: SolverSpec
    seed: int
    run_id: int
    generations: int
    pop_size: int
    two_opt_budget: int | None
    lk_budget: LKBudget


METHODS_SCALE = [
    SolverSpec("OX + no LS", "ga", "ox"),
    SolverSpec("OX + 2-opt", "ma", "ox", "2-opt"),
    SolverSpec("PMX + 2-opt", "ma", "pmx", "2-opt"),
    SolverSpec("DPX + 2-opt", "ma", "dpx", "2-opt"),
    SolverSpec("GX + 2-opt", "ma", "gx", "2-opt"),
    SolverSpec("OX + L-K", "ma", "ox", "lk"),
    SolverSpec("DPX + L-K", "ma", "dpx", "lk"),
    SolverSpec("GX + L-K", "ma", "gx", "lk"),
]

METHODS_LK = [
    SolverSpec("OX + L-K", "ma", "ox", "lk"),
    SolverSpec("DPX + L-K", "ma", "dpx", "lk"),
    SolverSpec("GX + L-K", "ma", "gx", "lk"),
]

METHODS_ROBUSTNESS = [
    SolverSpec("PMX + L-K", "ma", "pmx", "lk"),
    SolverSpec("DPX + L-K", "ma", "dpx", "lk"),
    SolverSpec("GX + L-K", "ma", "gx", "lk"),
    SolverSpec("GX + 2-opt", "ma", "gx", "2-opt"),
]

LK_WEAK = LKBudget("weak", 20, 1, 2, 8, 1)
LK_MEDIUM = LKBudget("medium", 60, 3, 3, 12, 2)
LK_STRONG = LKBudget("strong", None, 5, 3, 15, 3)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run extra exploratory experiments for the conclusion slide."
    )
    parser.add_argument(
        "--mode",
        choices=["smoke", "report"],
        default="report",
        help="Use smoke for a tiny validation run; report produces the markdown data.",
    )
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--base-seed", type=int, default=BASE_SEED)
    args = parser.parse_args()

    workers = _resolve_workers(args.workers)
    output_dir = ROOT / "results" / "conclusion_exploration"
    figure_dir = ROOT / "report" / "figures" / "conclusion_exploration"
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    tasks = _build_tasks(args.mode, args.base_seed)
    print(f"Running {len(tasks)} tasks, mode={args.mode}, workers={workers}")
    raw_path = output_dir / f"{args.mode}_raw.csv"
    rows = _run_tasks(tasks, workers, raw_path)
    rows.sort(key=lambda row: (row["experiment"], row["instance"], row["method"], row["run_id"]))

    summary_rows = _summarize(rows)
    if args.mode == "report":
        summary_rows.extend(_large_instance_reference_rows())
        summary_rows.sort(
            key=lambda row: (
                str(row["experiment"]),
                str(row["instance"]),
                str(row["method"]),
                str(row["pop_size"]),
            )
        )
    _write_csv(raw_path, rows)
    _write_csv(output_dir / f"{args.mode}_summary.csv", summary_rows)
    _write_csv(
        output_dir / f"{args.mode}_metadata.csv",
        [_metadata(args.mode, workers, tasks, args.base_seed)],
    )

    _plot_scale(summary_rows, figure_dir / f"{args.mode}_scale_final_gap.png")
    _plot_lk_strength(summary_rows, figure_dir / f"{args.mode}_lk_strength.png")
    _plot_population(summary_rows, figure_dir / f"{args.mode}_population_size.png")

    print("Wrote:")
    print(f"  {output_dir / f'{args.mode}_raw.csv'}")
    print(f"  {output_dir / f'{args.mode}_summary.csv'}")
    print(f"  {output_dir / f'{args.mode}_metadata.csv'}")
    print(f"  {figure_dir / f'{args.mode}_scale_final_gap.png'}")
    print(f"  {figure_dir / f'{args.mode}_lk_strength.png'}")
    print(f"  {figure_dir / f'{args.mode}_population_size.png'}")


def _build_tasks(mode: str, base_seed: int) -> list[Task]:
    if mode == "smoke":
        return [
            Task("scale", "ch130", spec, base_seed + idx, idx, 2, 4, 10, LK_WEAK)
            for idx, spec in enumerate(METHODS_SCALE[:3])
        ]

    tasks: list[Task] = []
    tasks.extend(_scale_tasks(base_seed))
    tasks.extend(_lk_strength_tasks(base_seed + 10_000))
    tasks.extend(_population_tasks(base_seed + 20_000))
    tasks.extend(_robustness_tasks(base_seed + 30_000))
    return tasks


def _scale_tasks(base_seed: int) -> list[Task]:
    tasks: list[Task] = []
    settings = [
        ("ch130", 5, 6, 6),
    ]
    for instance_idx, (instance_name, runs, generations, pop_size) in enumerate(settings):
        for spec_idx, spec in enumerate(METHODS_SCALE):
            for run_id in range(runs):
                tasks.append(
                    Task(
                        "scale",
                        instance_name,
                        spec,
                        base_seed + instance_idx * 1000 + spec_idx * 100 + run_id,
                        run_id,
                        generations,
                        pop_size,
                        60,
                        LK_MEDIUM,
                    )
                )
    return tasks


def _lk_strength_tasks(base_seed: int) -> list[Task]:
    tasks: list[Task] = []
    settings = [
        ("ch130", [LK_WEAK, LK_MEDIUM, LK_STRONG], 4, 6, 6),
    ]
    for instance_idx, (instance_name, budgets, runs, generations, pop_size) in enumerate(settings):
        for budget_idx, lk_budget in enumerate(budgets):
            for spec_idx, spec in enumerate(METHODS_LK):
                for run_id in range(runs):
                    tasks.append(
                        Task(
                            f"lk_strength_{lk_budget.label}",
                            instance_name,
                            spec,
                            base_seed
                            + instance_idx * 2000
                            + budget_idx * 500
                            + spec_idx * 100
                            + run_id,
                            run_id,
                            generations,
                            pop_size,
                            None,
                            lk_budget,
                        )
                    )
    return tasks


def _population_tasks(base_seed: int) -> list[Task]:
    tasks: list[Task] = []
    for pop_idx, pop_size in enumerate([6, 12]):
        for spec_idx, spec in enumerate([METHODS_SCALE[4], METHODS_SCALE[6], METHODS_SCALE[7]]):
            for run_id in range(4):
                tasks.append(
                    Task(
                        f"population_{pop_size}",
                        "ch130",
                        spec,
                        base_seed + pop_idx * 1000 + spec_idx * 100 + run_id,
                        run_id,
                        6,
                        pop_size,
                        60,
                        LK_MEDIUM,
                    )
                )
    return tasks


def _robustness_tasks(base_seed: int) -> list[Task]:
    tasks: list[Task] = []
    for spec_idx, spec in enumerate(METHODS_ROBUSTNESS):
        for run_id in range(8):
            tasks.append(
                Task(
                    "multi_seed",
                    "ch130",
                    spec,
                    base_seed + spec_idx * 100 + run_id,
                    run_id,
                    8,
                    8,
                    60,
                    LK_MEDIUM,
                )
            )
    return tasks


def _run_tasks(
    tasks: list[Task],
    workers: int,
    raw_path: Path,
) -> list[dict[str, object]]:
    if raw_path.exists():
        raw_path.unlink()
    if workers <= 1 or len(tasks) <= 1:
        rows = []
        for task in tasks:
            row = _solve_task(task)
            rows.append(row)
            _append_csv(raw_path, row)
        return rows

    rows: list[dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_solve_task, task) for task in tasks]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            _append_csv(raw_path, row)
            print(
                f"  {row['experiment']:<18} {row['instance']:<6} "
                f"{row['method']:<14} run={row['run_id']:<2} "
                f"gap={row['final_gap_pct']:.3f}% time={row['runtime_s']:.2f}s"
            )
    return rows


def _solve_task(task: Task) -> dict[str, object]:
    instance = _load_instance(task.instance_name)
    best, history, elapsed = _run_solver(
        instance=instance,
        spec=task.spec,
        seed=task.seed,
        generations=task.generations,
        pop_size=task.pop_size,
        two_opt_budget=task.two_opt_budget,
        lk_budget=task.lk_budget,
    )
    optimal = OPTIMAL.get(task.instance_name)
    history_gaps = [_gap(value, optimal) for value in history]
    best_gap = min(history_gaps) if history_gaps else _gap(best, optimal)
    return {
        "experiment": task.experiment,
        "instance": task.instance_name,
        "dimension": instance.dimension,
        "method": task.spec.name,
        "run_id": task.run_id,
        "seed": task.seed,
        "generations": task.generations,
        "pop_size": task.pop_size,
        "two_opt_budget": _limit_label(task.two_opt_budget),
        "lk_strength": task.lk_budget.label,
        "lk_warm_start_max_improvements": _limit_label(
            task.lk_budget.warm_start_max_improvements
        ),
        "lk_max_improvements": _limit_label(task.lk_budget.max_improvements),
        "lk_max_depth": task.lk_budget.max_depth,
        "lk_candidate_k": _limit_label(task.lk_budget.candidate_k),
        "lk_backtracking_width": task.lk_budget.backtracking_width,
        "best_length": best,
        "final_gap_pct": _gap(best, optimal),
        "best_gap_pct": best_gap,
        "gap_auc": _gap_auc(history_gaps),
        "runtime_s": elapsed,
        "history": " ".join(f"{value:.6f}" for value in history),
    }


def _run_solver(
    instance: TSPInstance,
    spec: SolverSpec,
    seed: int,
    generations: int,
    pop_size: int,
    two_opt_budget: int | None,
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
        solver = MemeticAlgorithm(
            pop_size=pop_size,
            n_generations=generations,
            pc=spec.pc,
            pm=spec.pm,
            crossover=spec.crossover,
            local_search=spec.local_search,
            ls_strategy="full" if spec.local_search == "lk" else "bounded",
            ls_max_iter=0 if two_opt_budget is None else two_opt_budget,
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


def _summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for row in rows:
        key = (
            row["experiment"],
            row["instance"],
            row["method"],
            row["pop_size"],
            row["generations"],
            row["lk_strength"],
        )
        groups.setdefault(key, []).append(row)

    summary: list[dict[str, object]] = []
    for key, group in sorted(groups.items(), key=lambda item: tuple(str(part) for part in item[0])):
        final_gaps = [float(row["final_gap_pct"]) for row in group]
        best_gaps = [float(row["best_gap_pct"]) for row in group]
        times = [float(row["runtime_s"]) for row in group]
        aucs = [float(row["gap_auc"]) for row in group]
        first = group[0]
        summary.append(
            {
                "experiment": key[0],
                "instance": key[1],
                "dimension": first["dimension"],
                "method": key[2],
                "runs": len(group),
                "pop_size": key[3],
                "generations": key[4],
                "two_opt_budget": first["two_opt_budget"],
                "lk_strength": key[5],
                "lk_warm_start_max_improvements": first[
                    "lk_warm_start_max_improvements"
                ],
                "lk_max_improvements": first["lk_max_improvements"],
                "lk_max_depth": first["lk_max_depth"],
                "lk_candidate_k": first["lk_candidate_k"],
                "lk_backtracking_width": first["lk_backtracking_width"],
                "final_gap_mean_pct": mean(final_gaps),
                "final_gap_sd_pct": stdev(final_gaps) if len(final_gaps) > 1 else 0.0,
                "best_gap_pct": min(best_gaps),
                "worst_gap_pct": max(final_gaps),
                "gap_auc_mean": mean(aucs),
                "runtime_mean_s": mean(times),
                "runtime_sd_s": stdev(times) if len(times) > 1 else 0.0,
            }
        )
    return summary


def _large_instance_reference_rows() -> list[dict[str, object]]:
    summary_path = ROOT / "results" / "paper_tables" / "large_instance_pilot_summary.csv"
    metadata_path = ROOT / "results" / "paper_tables" / "large_instance_pilot_metadata.csv"
    if not summary_path.exists():
        return []

    metadata: dict[str, str] = {}
    if metadata_path.exists():
        with metadata_path.open(newline="", encoding="utf-8") as handle:
            metadata = next(csv.DictReader(handle), {})

    rows: list[dict[str, object]] = []
    with summary_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("instance") != "d493":
                continue
            rows.append(
                {
                    "experiment": "scale",
                    "instance": row["instance"],
                    "dimension": 493,
                    "method": row["method"],
                    "runs": row["runs"],
                    "pop_size": metadata.get("pop_size", "6"),
                    "generations": metadata.get("generations", "8"),
                    "two_opt_budget": metadata.get("ls_step_budget", "100000"),
                    "lk_strength": "existing_d493_pilot",
                    "lk_warm_start_max_improvements": metadata.get(
                        "lk_warm_start_max_improvements", "100000"
                    ),
                    "lk_max_improvements": metadata.get("lk_max_improvements", "12"),
                    "lk_max_depth": metadata.get("lk_max_depth", "3"),
                    "lk_candidate_k": metadata.get("lk_candidate_k", "20"),
                    "lk_backtracking_width": metadata.get("lk_backtracking_width", "1"),
                    "final_gap_mean_pct": float(row["final_gap_mean_pct"]),
                    "final_gap_sd_pct": float(row["final_gap_sd_pct"]),
                    "best_gap_pct": "",
                    "worst_gap_pct": "",
                    "gap_auc_mean": float(row["gap_auc_mean"]),
                    "runtime_mean_s": float(row["runtime_mean_s"]),
                    "runtime_sd_s": float(row["runtime_sd_s"]),
                    "source": "existing large_instance_pilot_summary.csv",
                }
            )
    return rows


def _plot_scale(rows: list[dict[str, object]], path: Path) -> None:
    selected = [row for row in rows if row["experiment"] == "scale"]
    if not selected:
        return
    methods = _ordered_methods(list(dict.fromkeys(str(row["method"]) for row in selected)))
    methods = [method for method in methods if method != "PMX + L-K"]
    instances = list(dict.fromkeys(str(row["instance"]) for row in selected))
    palette = _method_palette()

    fig, axes = plt.subplots(1, len(instances), figsize=(7.0 * len(instances), 4.4), squeeze=False)
    lookup = {(row["instance"], row["method"]): row for row in selected}
    for ax, instance_name in zip(axes[0], instances):
        values = [
            float(lookup[(instance_name, method)]["final_gap_mean_pct"])
            if (instance_name, method) in lookup
            else float("nan")
            for method in methods
        ]
        errors = [
            float(lookup[(instance_name, method)]["final_gap_sd_pct"])
            if (instance_name, method) in lookup
            else 0.0
            for method in methods
        ]
        x = np.arange(len(methods))
        ax.bar(
            x,
            values,
            yerr=errors,
            color=[palette.get(method, "#8c8c8c") for method in methods],
            edgecolor="white",
            linewidth=0.8,
        )
        ax.set_title(instance_name)
        ax.set_ylabel("Final gap (%)")
        ax.set_xticks(x)
        ax.set_xticklabels(methods, rotation=35, ha="right")
        ax.grid(axis="y", color="#e8e8e8", linewidth=0.8)
    fig.suptitle("Scale exploration: final quality")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_lk_strength(rows: list[dict[str, object]], path: Path) -> None:
    selected = [row for row in rows if str(row["experiment"]).startswith("lk_strength")]
    if not selected:
        return
    instances = list(dict.fromkeys(str(row["instance"]) for row in selected))
    methods = _ordered_methods(list(dict.fromkeys(str(row["method"]) for row in selected)))
    strengths = ["weak", "medium", "strong"]
    palette = _method_palette()

    fig, axes = plt.subplots(1, len(instances), figsize=(6.4 * len(instances), 4.4), squeeze=False)
    for ax, instance_name in zip(axes[0], instances):
        for method in methods:
            xs: list[int] = []
            ys: list[float] = []
            for idx, strength in enumerate(strengths):
                match = [
                    row
                    for row in selected
                    if row["instance"] == instance_name
                    and row["method"] == method
                    and row["lk_strength"] == strength
                ]
                if match:
                    xs.append(idx)
                    ys.append(float(match[0]["final_gap_mean_pct"]))
            if xs:
                ax.plot(xs, ys, marker="o", linewidth=2.2, label=method, color=palette.get(method))
        ax.set_title(instance_name)
        ax.set_xticks(range(len(strengths)))
        ax.set_xticklabels(strengths)
        ax.set_ylabel("Final gap (%)")
        ax.grid(True, color="#e8e8e8", linewidth=0.8)
    axes[0, 0].legend(fontsize=9)
    fig.suptitle("L-K strength exploration")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_population(rows: list[dict[str, object]], path: Path) -> None:
    selected = [row for row in rows if str(row["experiment"]).startswith("population")]
    if not selected:
        return
    methods = _ordered_methods(list(dict.fromkeys(str(row["method"]) for row in selected)))
    populations = [6, 12]
    palette = _method_palette()

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    width = 0.35
    x = np.arange(len(methods))
    pop_colors = {6: "#4e79a7", 12: "#f28e2b"}
    for idx, pop_size in enumerate(populations):
        values = []
        for method in methods:
            match = [
                row
                for row in selected
                if int(row["pop_size"]) == pop_size and row["method"] == method
            ]
            values.append(float(match[0]["final_gap_mean_pct"]) if match else float("nan"))
        ax.bar(
            x + (idx - 0.5) * width,
            values,
            width=width,
            label=f"pop={pop_size}",
            color=pop_colors[pop_size],
            edgecolor="white",
            linewidth=0.8,
        )
    ax.set_title("ch130 population-size exploration")
    ax.set_ylabel("Final gap (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(methods, rotation=25, ha="right")
    ax.grid(axis="y", color="#e8e8e8", linewidth=0.8)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _metadata(
    mode: str,
    workers: int,
    tasks: list[Task],
    base_seed: int,
) -> dict[str, object]:
    return {
        "mode": mode,
        "workers": workers,
        "tasks": len(tasks),
        "base_seed": base_seed,
        "note": "Exploratory runs for conclusion extension; not a full benchmark.",
    }


def _load_instance(name: str) -> TSPInstance:
    path = ROOT / "data" / "tsplib" / f"{name}.tsp"
    if not path.exists():
        raise FileNotFoundError(path)
    return TSPInstance.load_tsplib(path)


def _gap(value: float, optimal: float | None) -> float:
    if optimal is None:
        return float("nan")
    return (value - optimal) / optimal * 100.0


def _gap_auc(gaps: list[float]) -> float:
    if not gaps:
        return float("nan")
    return float(np.trapezoid(gaps, dx=1.0))


def _limit_label(value: int | None) -> str:
    return "unbounded" if value is None else str(value)


def _resolve_workers(requested: int) -> int:
    if requested > 0:
        return requested
    cpu_count = os.cpu_count() or 1
    return max(1, min(4, cpu_count - 1))


def _ordered_methods(methods: list[str]) -> list[str]:
    preferred = [
        "OX + no LS",
        "OX + 2-opt",
        "PMX + 2-opt",
        "DPX + 2-opt",
        "GX + 2-opt",
        "OX + L-K",
        "PMX + L-K",
        "DPX + L-K",
        "GX + L-K",
    ]
    rank = {method: idx for idx, method in enumerate(preferred)}
    return sorted(methods, key=lambda method: (rank.get(method, len(preferred)), method))


def _method_palette() -> dict[str, str]:
    return {
        "OX + no LS": "#8c8c8c",
        "OX + 2-opt": "#f28e2b",
        "PMX + 2-opt": "#ffbe7d",
        "DPX + 2-opt": "#8cd17d",
        "GX + 2-opt": "#ff9d9a",
        "OX + L-K": "#4e79a7",
        "PMX + L-K": "#b07aa1",
        "DPX + L-K": "#59a14f",
        "GX + L-K": "#e15759",
    }


def _lighten(hex_color: str, amount: float) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key, value in row.items():
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                row[key] = ""
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _append_csv(path: Path, row: dict[str, object]) -> None:
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()


if __name__ == "__main__":
    main()
