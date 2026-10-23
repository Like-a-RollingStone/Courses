from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from time import perf_counter
from typing import Callable

import numpy as np
from tqdm.auto import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baselines import nearest_neighbor
from src.ga import GeneticAlgorithm
from src.instance import TSPInstance
from src.memetic import MemeticAlgorithm
from src.tour import Tour
from src.two_opt import two_opt_dlb
from src.viz import plot_convergence


INSTANCES = [
    "burma14",
    "berlin52",
    "eil51",
    "eil101",
    "ch130",
    "kroA200",
    "pcb442",
    "rat575",
]
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
N_RUNS = 10
BASE_SEED = 20260525
TSPLIB_HINT_URL = "https://www.math.uwaterloo.ca/tsp/world/countries.html"
RAW_FIELDS = [
    "instance",
    "algorithm",
    "run_id",
    "seed",
    "best",
    "time",
    "history",
]


AlgorithmRunner = Callable[[TSPInstance, int], tuple[Tour, list[float]]]


def _run_nearest_neighbor(
    instance: TSPInstance, seed: int
) -> tuple[Tour, list[float]]:
    tour = nearest_neighbor(instance, seed=seed)
    length = tour.length(instance)
    return tour, [length]


def _run_two_opt_from_nn(
    instance: TSPInstance, seed: int
) -> tuple[Tour, list[float]]:
    initial = nearest_neighbor(instance, seed=seed)
    improved, _ = two_opt_dlb(initial, instance)
    return improved, [initial.length(instance), improved.length(instance)]


def _algorithm_specs() -> list[tuple[str, AlgorithmRunner]]:
    return [
        ("Nearest Neighbor", _run_nearest_neighbor),
        ("2-opt (from NN)", _run_two_opt_from_nn),
        (
            "Pure GA",
            lambda inst, seed: GeneticAlgorithm(
                seed=seed,
                show_progress=False,
            ).solve(inst),
        ),
        (
            "MA (full)",
            lambda inst, seed: MemeticAlgorithm(
                ls_strategy="full",
                seed=seed,
                show_progress=False,
                verbose=False,
            ).solve(inst),
        ),
        (
            "MA (partial)",
            lambda inst, seed: MemeticAlgorithm(
                ls_strategy="partial",
                seed=seed,
                show_progress=False,
                verbose=False,
            ).solve(inst),
        ),
    ]


def main() -> None:
    np.random.seed(BASE_SEED)
    results_dir = ROOT / "results"
    figures_dir = results_dir / "figures"
    algorithms = _algorithm_specs()
    available_instances = _load_available_instances()
    if not available_instances:
        print("No TSPLIB instances are available; no experiments were run.")
        return

    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    raw_path = results_dir / "compare_raw.csv"
    summary_path = results_dir / "compare_summary.csv"
    completed = _load_completed(raw_path)
    total = len(available_instances) * len(algorithms) * N_RUNS

    with tqdm(total=total, desc="compare", unit="run") as progress:
        for instance_name, instance in available_instances:
            for algorithm_name, runner in algorithms:
                for run_id in range(N_RUNS):
                    key = (instance_name, algorithm_name, run_id)
                    if key in completed:
                        progress.update(1)
                        continue

                    seed = BASE_SEED + run_id
                    start_time = perf_counter()
                    best_tour, history = runner(instance, seed)
                    elapsed = perf_counter() - start_time
                    best = best_tour.length(instance)
                    _append_raw_row(
                        raw_path,
                        {
                            "instance": instance_name,
                            "algorithm": algorithm_name,
                            "run_id": run_id,
                            "seed": seed,
                            "best": f"{best:.10f}",
                            "time": f"{elapsed:.10f}",
                            "history": _format_history(history),
                        },
                    )
                    completed.add(key)
                    progress.update(1)

    rows = _read_raw_rows(raw_path)
    _write_summary(rows, summary_path)
    _plot_all_convergence(rows, figures_dir)
    print(f"raw results saved to {raw_path}")
    print(f"summary saved to {summary_path}")
    print(f"figures saved to {figures_dir}")


def _load_available_instances() -> list[tuple[str, TSPInstance]]:
    available: list[tuple[str, TSPInstance]] = []
    data_dir = ROOT / "data" / "tsplib"
    for name in INSTANCES:
        path = data_dir / f"{name}.tsp"
        if not path.exists():
            print(
                f"{path} not found. Please download {name}.tsp and place it under "
                f"data/tsplib/. Reference: {TSPLIB_HINT_URL}"
            )
            continue
        available.append((name, TSPInstance.load_tsplib(path)))
    return available


def _load_completed(raw_path: Path) -> set[tuple[str, str, int]]:
    completed: set[tuple[str, str, int]] = set()
    if not raw_path.exists():
        return completed
    with raw_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            completed.add((row["instance"], row["algorithm"], int(row["run_id"])))
    return completed


def _append_raw_row(raw_path: Path, row: dict[str, object]) -> None:
    write_header = not raw_path.exists()
    with raw_path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RAW_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _read_raw_rows(raw_path: Path) -> list[dict[str, str]]:
    if not raw_path.exists():
        return []
    with raw_path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _write_summary(rows: list[dict[str, str]], summary_path: Path) -> None:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["instance"], row["algorithm"])].append(row)

    fields = [
        "instance",
        "algorithm",
        "runs",
        "best",
        "mean",
        "std",
        "mean ± std",
        "gap%",
        "time",
    ]
    with summary_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for (instance_name, algorithm_name), group in sorted(grouped.items()):
            best_values = [float(row["best"]) for row in group]
            time_values = [float(row["time"]) for row in group]
            avg = mean(best_values)
            std = stdev(best_values) if len(best_values) > 1 else 0.0
            optimal = OPTIMAL.get(instance_name)
            gap = ((avg - optimal) / optimal * 100.0) if optimal else float("nan")
            writer.writerow(
                {
                    "instance": instance_name,
                    "algorithm": algorithm_name,
                    "runs": len(group),
                    "best": f"{min(best_values):.3f}",
                    "mean": f"{avg:.3f}",
                    "std": f"{std:.3f}",
                    "mean ± std": f"{avg:.3f} ± {std:.3f}",
                    "gap%": f"{gap:.3f}",
                    "time": f"{mean(time_values):.3f}",
                }
            )


def _plot_all_convergence(rows: list[dict[str, str]], figures_dir: Path) -> None:
    by_instance_algorithm: dict[tuple[str, str], list[list[float]]] = defaultdict(list)
    for row in rows:
        history = _parse_history(row["history"])
        if history:
            by_instance_algorithm[(row["instance"], row["algorithm"])].append(history)

    for instance_name in sorted({row["instance"] for row in rows}):
        histories: dict[str, list[float]] = {}
        for algorithm_name, _ in _algorithm_specs():
            runs = by_instance_algorithm.get((instance_name, algorithm_name), [])
            if runs:
                histories[algorithm_name] = _average_histories(runs)
        if histories:
            plot_convergence(
                histories,
                optimal=OPTIMAL.get(instance_name),
                save_path=str(figures_dir / f"{instance_name}_convergence.png"),
            )


def _average_histories(histories: list[list[float]]) -> list[float]:
    max_len = max(len(history) for history in histories)
    padded = []
    for history in histories:
        if len(history) < max_len:
            history = history + [history[-1]] * (max_len - len(history))
        padded.append(history)
    return np.mean(np.array(padded, dtype=np.float64), axis=0).tolist()


def _format_history(history: list[float]) -> str:
    return ";".join(f"{value:.10f}" for value in history)


def _parse_history(value: str) -> list[float]:
    if not value:
        return []
    return [float(item) for item in value.split(";") if item]


if __name__ == "__main__":
    main()
