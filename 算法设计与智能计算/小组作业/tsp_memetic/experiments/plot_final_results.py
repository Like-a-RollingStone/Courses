from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.run_conclusion_exploration import _plot_lk_strength, _plot_population
from experiments.run_large_instance_pilot import _plot_convergence, _plot_summary
from experiments.run_multi_instance_gx_lk_summary import _plot as _plot_multi_instance


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _plot_robustness(rows: list[dict[str, str]], path: Path) -> None:
    methods = ["PMX + L-K", "DPX + L-K", "GX + L-K", "GX + 2-opt"]
    selected = {
        row["method"]: row
        for row in rows
        if row["experiment"] == "multi_seed" and row["instance"] == "ch130"
    }
    values = [float(selected[method]["final_gap_mean_pct"]) for method in methods]
    errors = [float(selected[method]["final_gap_sd_pct"]) for method in methods]
    counts = {int(selected[method]["runs"]) for method in methods}
    if len(counts) != 1:
        raise ValueError("Expected equal run counts for the robustness comparison")
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.bar(
        methods,
        values,
        yerr=errors,
        capsize=5,
        color=["#b07aa1", "#59a14f", "#e15759", "#f28e2b"],
        edgecolor="white",
    )
    ax.set_title(f"ch130 multi-seed comparison (N={counts.pop()})")
    ax.set_ylabel("Final gap (%), mean +/- sample SD")
    ax.set_ylim(bottom=0)
    ax.tick_params(axis="x", labelrotation=20)
    ax.grid(axis="y", color="#e8e8e8", linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Redraw final slide plots from saved CSVs.")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "report" / "figures" / "reproduced"
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    tables = ROOT / "results" / "paper_tables"
    exploration = ROOT / "results" / "conclusion_exploration"
    raw = _read_csv(tables / "large_instance_pilot_raw.csv")
    summary = _read_csv(tables / "large_instance_pilot_summary.csv")
    report = _read_csv(exploration / "report_summary.csv")
    maps = _read_csv(exploration / "multi_instance_gx_lk_summary.csv")
    _plot_convergence(raw, ["d493"], output / "6_3_large_instance_pilot.png")
    _plot_summary(summary, ["d493"], output / "6_4_large_instance_pilot_summary.png")
    _plot_multi_instance(maps, output / "report_multi_instance_gx_lk_summary.png")
    _plot_lk_strength(report, output / "report_lk_strength.png")
    _plot_population(report, output / "report_population_size.png")
    _plot_robustness(report, output / "report_multiseed_robustness.png")
    print(f"Wrote 6 figures to {output}")


if __name__ == "__main__":
    main()
