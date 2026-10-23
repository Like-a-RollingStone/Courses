from __future__ import annotations

import argparse
import csv
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from statistics import mean, stdev
from time import perf_counter

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.run_conclusion_exploration import (  # noqa: E402
    LKBudget,
    OPTIMAL,
    SolverSpec,
    _gap,
    _load_instance,
    _run_solver,
)


BASE_SEED = 20260621
LK_MEDIUM = LKBudget("medium", 60, 3, 3, 12, 2)
OPTIMUMS = {
    **OPTIMAL,
    "eil51": 426.0,
    "eil101": 629.0,
}
SPECS = [
    SolverSpec("OX + L-K", "ma", "ox", "lk"),
    SolverSpec("PMX + L-K", "ma", "pmx", "lk"),
    SolverSpec("DPX + L-K", "ma", "dpx", "lk"),
    SolverSpec("GX + L-K", "ma", "gx", "lk"),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare L-K crossover variants on multiple TSPLIB maps."
    )
    parser.add_argument("--instances", nargs="+", default=["eil51", "eil101", "ch130"])
    parser.add_argument("--runs", type=int, default=8)
    parser.add_argument("--generations", type=int, default=8)
    parser.add_argument("--pop-size", type=int, default=8)
    parser.add_argument("--two-opt-budget", type=int, default=60)
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()

    workers = _resolve_workers(args.workers)
    output_dir = ROOT / "results" / "conclusion_exploration"
    figure_dir = ROOT / "report" / "figures" / "conclusion_exploration"
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    tasks = []
    for inst_idx, instance_name in enumerate(args.instances):
        for spec_idx, spec in enumerate(SPECS):
            for run_id in range(args.runs):
                seed = BASE_SEED + inst_idx * 1000 + spec_idx * 100 + run_id
                tasks.append(
                    (
                        instance_name,
                        spec,
                        seed,
                        run_id,
                        args.generations,
                        args.pop_size,
                        args.two_opt_budget,
                    )
                )

    print(f"Running {len(tasks)} tasks with workers={workers}")
    rows = _run_tasks(tasks, workers)
    summary_rows = _summarize(rows)
    summary_rows.extend(_d493_reference_rows())
    summary_rows.sort(key=lambda row: (str(row["instance"]), str(row["method"])))

    raw_path = output_dir / "multi_instance_gx_lk_raw.csv"
    summary_path = output_dir / "multi_instance_gx_lk_summary.csv"
    figure_path = figure_dir / "report_multi_instance_gx_lk_summary.png"
    _write_csv(raw_path, rows)
    _write_csv(summary_path, summary_rows)
    _plot(summary_rows, figure_path)

    print("Wrote:")
    print(f"  {raw_path}")
    print(f"  {summary_path}")
    print(f"  {figure_path}")


def _run_tasks(tasks: list[tuple[object, ...]], workers: int) -> list[dict[str, object]]:
    if workers <= 1:
        return [_solve_task(task) for task in tasks]
    rows: list[dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_solve_task, task) for task in tasks]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(
                f"  {row['instance']:<7} {row['method']:<12} run={row['run_id']:<2} "
                f"gap={row['final_gap_pct']:.3f}% time={row['runtime_s']:.2f}s"
            )
    return rows


def _solve_task(task: tuple[object, ...]) -> dict[str, object]:
    (
        instance_name,
        spec,
        seed,
        run_id,
        generations,
        pop_size,
        two_opt_budget,
    ) = task
    instance = _load_instance(str(instance_name))
    start = perf_counter()
    best, _history, elapsed = _run_solver(
        instance=instance,
        spec=spec,
        seed=int(seed),
        generations=int(generations),
        pop_size=int(pop_size),
        two_opt_budget=int(two_opt_budget),
        lk_budget=LK_MEDIUM,
    )
    del start
    optimal = OPTIMUMS[str(instance_name)]
    return {
        "instance": instance_name,
        "dimension": instance.dimension,
        "method": spec.name,
        "run_id": run_id,
        "seed": seed,
        "runs": "",
        "generations": generations,
        "pop_size": pop_size,
        "lk_strength": "medium",
        "final_gap_pct": _gap(best, optimal),
        "runtime_s": elapsed,
    }


def _summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["instance"]), str(row["method"])), []).append(row)
    summary: list[dict[str, object]] = []
    for (instance, method), group in grouped.items():
        gaps = [float(row["final_gap_pct"]) for row in group]
        times = [float(row["runtime_s"]) for row in group]
        first = group[0]
        summary.append(
            {
                "instance": instance,
                "dimension": first["dimension"],
                "method": method,
                "runs": len(group),
                "generations": first["generations"],
                "pop_size": first["pop_size"],
                "lk_strength": first["lk_strength"],
                "final_gap_mean_pct": mean(gaps),
                "final_gap_sd_pct": stdev(gaps) if len(gaps) > 1 else 0.0,
                "runtime_mean_s": mean(times),
                "source": "new multi-instance medium L-K run",
            }
        )
    return summary


def _d493_reference_rows() -> list[dict[str, object]]:
    path = ROOT / "results" / "paper_tables" / "large_instance_pilot_summary.csv"
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    wanted = {"OX + L-K", "PMX + L-K", "DPX + L-K", "GX + L-K"}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["instance"] == "d493" and row["method"] in wanted:
                rows.append(
                    {
                        "instance": "d493",
                        "dimension": 493,
                        "method": row["method"],
                        "runs": row["runs"],
                        "generations": 8,
                        "pop_size": 6,
                        "lk_strength": "existing_d493_pilot",
                        "final_gap_mean_pct": float(row["final_gap_mean_pct"]),
                        "final_gap_sd_pct": float(row["final_gap_sd_pct"]),
                        "runtime_mean_s": float(row["runtime_mean_s"]),
                        "source": "existing large_instance_pilot_summary.csv",
                    }
                )
    return rows


def _plot(rows: list[dict[str, object]], path: Path) -> None:
    instances = ["eil51", "eil101", "ch130", "d493"]
    methods = ["OX + L-K", "PMX + L-K", "DPX + L-K", "GX + L-K"]
    palette = {
        "OX + L-K": "#4e79a7",
        "PMX + L-K": "#b07aa1",
        "DPX + L-K": "#59a14f",
        "GX + L-K": "#e15759",
    }
    lookup = {(row["instance"], row["method"]): row for row in rows}
    x = np.arange(len(instances))
    width = 0.18
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    for idx, method in enumerate(methods):
        values = [
            float(lookup[(instance, method)]["final_gap_mean_pct"])
            if (instance, method) in lookup
            else float("nan")
            for instance in instances
        ]
        errors = [
            float(lookup[(instance, method)]["final_gap_sd_pct"])
            if (instance, method) in lookup
            else 0.0
            for instance in instances
        ]
        ax.bar(
            x + (idx - 1.5) * width,
            values,
            yerr=errors,
            width=width,
            label=method,
            color=palette[method],
            edgecolor="white",
            linewidth=0.8,
            capsize=3,
        )
    ax.set_title("Multi-map L-K crossover comparison")
    ax.set_ylabel("Final gap (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(instances)
    ax.grid(axis="y", color="#e8e8e8", linewidth=0.8)
    ax.legend(ncol=4, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _resolve_workers(requested: int) -> int:
    if requested > 0:
        return requested
    cpu_count = os.cpu_count() or 1
    return max(1, min(4, cpu_count - 1))


if __name__ == "__main__":
    main()
