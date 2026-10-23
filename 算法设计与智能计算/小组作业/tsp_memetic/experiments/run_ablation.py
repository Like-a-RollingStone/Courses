from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from time import perf_counter

import matplotlib.pyplot as plt
import numpy as np
from tqdm.auto import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.instance import TSPInstance
from src.memetic import MemeticAlgorithm
from src.viz import plot_convergence


INSTANCE_NAME = "berlin52"
OPTIMAL = 7542.0
N_RUNS = 20
BASE_SEED = 20260525
TSPLIB_HINT_URL = "https://www.math.uwaterloo.ca/tsp/world/countries.html"
RAW_FIELDS = ["config", "run_id", "seed", "final", "time", "history"]

plt.rcParams["font.family"] = "DejaVu Sans"


def main() -> None:
    instance = _load_berlin52()
    if instance is None:
        return

    tables_dir = ROOT / "results" / "ablation_tables"
    figures_dir = ROOT / "results" / "ablation_figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    _experiment_crossover(instance, tables_dir, figures_dir)
    _experiment_local_search(instance, tables_dir, figures_dir)
    _experiment_local_search_operator(instance, tables_dir, figures_dir)
    _experiment_paradigm(instance, tables_dir, figures_dir)
    print(f"ablation tables saved to {tables_dir}")
    print(f"ablation figures saved to {figures_dir}")


def _experiment_crossover(
    instance: TSPInstance,
    tables_dir: Path,
    figures_dir: Path,
) -> None:
    raw_path = tables_dir / "crossover_raw.csv"
    configs = ["ox", "pmx", "erx"]
    _run_ma_grid(
        instance=instance,
        raw_path=raw_path,
        configs=configs,
        desc="ablation crossover",
        make_algorithm=lambda config, seed: MemeticAlgorithm(
            crossover=config,
            seed=seed,
            show_progress=False,
            verbose=False,
        ),
    )
    rows = _read_rows(raw_path)
    _write_crossover_summary(rows, tables_dir / "crossover_summary.csv")
    _plot_crossover_boxplot(rows, figures_dir / "crossover_boxplot.png")


def _experiment_local_search(
    instance: TSPInstance,
    tables_dir: Path,
    figures_dir: Path,
) -> None:
    raw_path = tables_dir / "local_search_raw.csv"
    configs = ["full", "partial", "bounded"]
    _run_ma_grid(
        instance=instance,
        raw_path=raw_path,
        configs=configs,
        desc="ablation local search",
        make_algorithm=lambda config, seed: MemeticAlgorithm(
            ls_strategy=config,
            seed=seed,
            show_progress=False,
            verbose=False,
        ),
    )
    rows = _read_rows(raw_path)
    _write_local_search_summary(rows, tables_dir / "local_search_summary.csv")
    _plot_average_convergence(
        rows,
        figures_dir / "local_search_convergence.png",
        labels=["full", "partial", "bounded"],
    )


def _experiment_local_search_operator(
    instance: TSPInstance,
    tables_dir: Path,
    figures_dir: Path,
) -> None:
    raw_path = tables_dir / "local_search_operator_raw.csv"
    configs = ["2-opt", "or-opt", "both"]
    _run_ma_grid(
        instance=instance,
        raw_path=raw_path,
        configs=configs,
        desc="ablation local-search operator",
        make_algorithm=lambda config, seed: MemeticAlgorithm(
            local_search=config,
            seed=seed,
            show_progress=False,
            verbose=False,
        ),
    )
    rows = _read_rows(raw_path)
    _write_local_search_operator_summary(
        rows,
        tables_dir / "local_search_operator_summary.csv",
    )
    _plot_average_convergence(
        rows,
        figures_dir / "local_search_operator_convergence.png",
        labels=configs,
    )


def _experiment_paradigm(
    instance: TSPInstance,
    tables_dir: Path,
    figures_dir: Path,
) -> None:
    raw_path = tables_dir / "paradigm_raw.csv"
    configs = ["lamarckian", "baldwinian"]
    _run_ma_grid(
        instance=instance,
        raw_path=raw_path,
        configs=configs,
        desc="ablation paradigm",
        make_algorithm=lambda config, seed: MemeticAlgorithm(
            paradigm=config,
            seed=seed,
            show_progress=False,
            verbose=False,
        ),
    )
    rows = _read_rows(raw_path)
    _write_paradigm_tables(
        rows,
        tables_dir / "paradigm_summary.csv",
        tables_dir / "paradigm_ttest.csv",
    )
    _plot_average_convergence(
        rows,
        figures_dir / "paradigm_convergence.png",
        labels=["lamarckian", "baldwinian"],
    )


def _run_ma_grid(
    instance: TSPInstance,
    raw_path: Path,
    configs: list[str],
    desc: str,
    make_algorithm,
) -> None:
    completed = _load_completed(raw_path)
    total = len(configs) * N_RUNS
    with tqdm(total=total, desc=desc, unit="run") as progress:
        for config in configs:
            for run_id in range(N_RUNS):
                key = (config, run_id)
                if key in completed:
                    progress.update(1)
                    continue

                seed = BASE_SEED + run_id
                algorithm = make_algorithm(config, seed)
                start = perf_counter()
                best_tour, history = algorithm.solve(instance)
                elapsed = perf_counter() - start
                _append_row(
                    raw_path,
                    {
                        "config": config,
                        "run_id": run_id,
                        "seed": seed,
                        "final": f"{best_tour.length(instance):.10f}",
                        "time": f"{elapsed:.10f}",
                        "history": _format_history(history),
                    },
                )
                completed.add(key)
                progress.update(1)


def _write_crossover_summary(rows: list[dict[str, str]], path: Path) -> None:
    grouped = _group_by_config(rows)
    fields = ["operator", "mean ± std", "gap%", "best", "time"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for config in ["ox", "pmx", "erx"]:
            values = _final_values(grouped.get(config, []))
            times = _time_values(grouped.get(config, []))
            if not values:
                continue
            avg = mean(values)
            std = stdev(values) if len(values) > 1 else 0.0
            gap = (avg - OPTIMAL) / OPTIMAL * 100.0
            writer.writerow(
                {
                    "operator": config.upper(),
                    "mean ± std": f"{avg:.3f} ± {std:.3f}",
                    "gap%": f"{gap:.3f}",
                    "best": f"{min(values):.3f}",
                    "time": f"{mean(times):.3f}",
                }
            )


def _write_local_search_summary(rows: list[dict[str, str]], path: Path) -> None:
    grouped = _group_by_config(rows)
    fields = ["strategy", "final length", "total time", "time/gen"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for config in ["full", "partial", "bounded"]:
            group = grouped.get(config, [])
            values = _final_values(group)
            times = _time_values(group)
            histories = [_parse_history(row["history"]) for row in group]
            histories = [history for history in histories if history]
            if not values:
                continue
            avg = mean(values)
            std = stdev(values) if len(values) > 1 else 0.0
            avg_time = mean(times)
            generations = max(len(history) for history in histories) if histories else 1
            writer.writerow(
                {
                    "strategy": config,
                    "final length": f"{avg:.3f} ± {std:.3f}",
                    "total time": f"{avg_time:.3f}",
                    "time/gen": f"{avg_time / generations:.6f}",
                }
            )


def _write_local_search_operator_summary(
    rows: list[dict[str, str]],
    path: Path,
) -> None:
    grouped = _group_by_config(rows)
    fields = ["local_search", "mean 卤 std", "gap%", "best", "time"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for config in ["2-opt", "or-opt", "both"]:
            values = _final_values(grouped.get(config, []))
            times = _time_values(grouped.get(config, []))
            if not values:
                continue
            avg = mean(values)
            std = stdev(values) if len(values) > 1 else 0.0
            writer.writerow(
                {
                    "local_search": config,
                    "mean 卤 std": f"{avg:.3f} 卤 {std:.3f}",
                    "gap%": f"{(avg - OPTIMAL) / OPTIMAL * 100.0:.3f}",
                    "best": f"{min(values):.3f}",
                    "time": f"{mean(times):.3f}",
                }
            )


def _write_paradigm_tables(
    rows: list[dict[str, str]],
    summary_path: Path,
    ttest_path: Path,
) -> None:
    grouped = _group_by_config(rows)
    with summary_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["paradigm", "mean ± std", "gap%", "best", "time"],
        )
        writer.writeheader()
        for config in ["lamarckian", "baldwinian"]:
            values = _final_values(grouped.get(config, []))
            times = _time_values(grouped.get(config, []))
            if not values:
                continue
            avg = mean(values)
            std = stdev(values) if len(values) > 1 else 0.0
            writer.writerow(
                {
                    "paradigm": config,
                    "mean ± std": f"{avg:.3f} ± {std:.3f}",
                    "gap%": f"{(avg - OPTIMAL) / OPTIMAL * 100.0:.3f}",
                    "best": f"{min(values):.3f}",
                    "time": f"{mean(times):.3f}",
                }
            )

    lamarckian = _final_values(grouped.get("lamarckian", []))
    baldwinian = _final_values(grouped.get("baldwinian", []))
    t_value, df, p_value = _welch_t_test(lamarckian, baldwinian)
    with ttest_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "comparison",
                "mean_lamarckian",
                "mean_baldwinian",
                "t",
                "df",
                "p_value",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "comparison": "lamarckian vs baldwinian",
                "mean_lamarckian": f"{mean(lamarckian):.3f}" if lamarckian else "",
                "mean_baldwinian": f"{mean(baldwinian):.3f}" if baldwinian else "",
                "t": f"{t_value:.6f}",
                "df": f"{df:.6f}",
                "p_value": f"{p_value:.6f}",
            }
        )


def _plot_crossover_boxplot(rows: list[dict[str, str]], path: Path) -> None:
    grouped = _group_by_config(rows)
    labels = ["ox", "pmx", "erx"]
    data = [_final_values(grouped.get(label, [])) for label in labels]
    data = [values for values in data if values]
    used_labels = [label.upper() for label in labels if _final_values(grouped.get(label, []))]
    if not data:
        return

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.boxplot(data, labels=used_labels, showmeans=True)
    ax.axhline(OPTIMAL, color="black", linestyle="--", linewidth=1.2, label="Optimal")
    ax.set_xlabel("Crossover operator")
    ax.set_ylabel("Final length")
    ax.set_title("Crossover operator ablation on berlin52")
    ax.grid(axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_average_convergence(
    rows: list[dict[str, str]],
    path: Path,
    labels: list[str],
) -> None:
    grouped = _group_by_config(rows)
    histories: dict[str, list[float]] = {}
    for label in labels:
        parsed = [_parse_history(row["history"]) for row in grouped.get(label, [])]
        parsed = [history for history in parsed if history]
        if parsed:
            histories[label] = _average_histories(parsed)
    if histories:
        plot_convergence(histories, optimal=OPTIMAL, save_path=str(path))


def _load_berlin52() -> TSPInstance | None:
    path = ROOT / "data" / "tsplib" / "berlin52.tsp"
    if not path.exists():
        print(
            f"{path} not found. Please download berlin52.tsp and place it under "
            f"data/tsplib/. Reference: {TSPLIB_HINT_URL}"
        )
        return None
    return TSPInstance.load_tsplib(path)


def _load_completed(raw_path: Path) -> set[tuple[str, int]]:
    completed: set[tuple[str, int]] = set()
    if not raw_path.exists():
        return completed
    with raw_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            completed.add((row["config"], int(row["run_id"])))
    return completed


def _append_row(raw_path: Path, row: dict[str, object]) -> None:
    write_header = not raw_path.exists()
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RAW_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _group_by_config(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["config"]].append(row)
    return grouped


def _final_values(rows: list[dict[str, str]]) -> list[float]:
    return [float(row["final"]) for row in rows]


def _time_values(rows: list[dict[str, str]]) -> list[float]:
    return [float(row["time"]) for row in rows]


def _format_history(history: list[float]) -> str:
    return ";".join(f"{value:.10f}" for value in history)


def _parse_history(value: str) -> list[float]:
    if not value:
        return []
    return [float(item) for item in value.split(";") if item]


def _average_histories(histories: list[list[float]]) -> list[float]:
    max_len = max(len(history) for history in histories)
    padded = []
    for history in histories:
        if len(history) < max_len:
            history = history + [history[-1]] * (max_len - len(history))
        padded.append(history)
    return np.mean(np.array(padded, dtype=np.float64), axis=0).tolist()


def _welch_t_test(a: list[float], b: list[float]) -> tuple[float, float, float]:
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan"), float("nan")

    mean_a = mean(a)
    mean_b = mean(b)
    var_a = stdev(a) ** 2
    var_b = stdev(b) ** 2
    n_a = len(a)
    n_b = len(b)
    se2 = var_a / n_a + var_b / n_b
    if se2 == 0:
        return 0.0, float("inf"), 1.0

    t_value = (mean_a - mean_b) / math.sqrt(se2)
    numerator = se2**2
    denominator = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
    df = numerator / denominator
    p_value = 2.0 * (1.0 - _student_t_cdf(abs(t_value), df))
    return t_value, df, max(0.0, min(1.0, p_value))


def _student_t_cdf(t_value: float, df: float) -> float:
    if math.isinf(df):
        return 0.5 * (1.0 + math.erf(t_value / math.sqrt(2.0)))
    x = df / (df + t_value * t_value)
    ibeta = _regularized_beta(x, df / 2.0, 0.5)
    return 1.0 - 0.5 * ibeta


def _regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _beta_continued_fraction(a, b, x) / a
    return 1.0 - bt * _beta_continued_fraction(b, a, 1.0 - x) / b


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    max_iter = 200
    eps = 3e-14
    fpmin = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d

    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


if __name__ == "__main__":
    main()
