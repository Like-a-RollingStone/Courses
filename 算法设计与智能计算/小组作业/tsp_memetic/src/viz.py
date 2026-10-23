from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

try:
    from .baselines import nearest_neighbor
    from .instance import TSPInstance
    from .memetic import MemeticAlgorithm
    from .tour import Tour
except ImportError:
    from baselines import nearest_neighbor  # type: ignore
    from instance import TSPInstance  # type: ignore
    from memetic import MemeticAlgorithm  # type: ignore
    from tour import Tour  # type: ignore


plt.rcParams["font.family"] = "DejaVu Sans"


def plot_tour(
    tour: Tour,
    instance: TSPInstance,
    title: str = "",
    save_path: str | None = None,
) -> None:
    """Plot city coordinates, closed tour edges, and highlight the start city."""

    if not tour.is_valid(instance.dimension):
        raise ValueError("tour must be a valid city permutation")

    coords = instance.coords
    order = np.array(tour.cities + [tour.cities[0]], dtype=int)
    ordered_coords = coords[order]
    length = tour.length(instance)
    full_title = f"{title} | length={length:.0f}" if title else f"length={length:.0f}"

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(
        ordered_coords[:, 0],
        ordered_coords[:, 1],
        color="#3b6ea8",
        linewidth=1.3,
        alpha=0.85,
    )
    ax.scatter(coords[:, 0], coords[:, 1], s=22, color="#222222", zorder=3)
    start_city = tour.cities[0]
    ax.scatter(
        coords[start_city, 0],
        coords[start_city, 1],
        s=70,
        color="red",
        edgecolors="white",
        linewidths=1.0,
        zorder=4,
        label="Start",
    )
    ax.set_title(full_title)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.axis("equal")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    _save_or_show(fig, save_path)


def plot_convergence(
    histories: dict[str, list[float]],
    optimal: float | None = None,
    save_path: str | None = None,
) -> None:
    """Plot one or more best-so-far convergence histories."""

    if not histories:
        raise ValueError("histories must not be empty")

    fig, ax = plt.subplots(figsize=(8, 5))
    for name, history in histories.items():
        if not history:
            continue
        generations = np.arange(1, len(history) + 1)
        ax.plot(generations, history, label=name, linewidth=1.8)

    if optimal is not None:
        ax.axhline(
            optimal,
            color="black",
            linestyle="--",
            linewidth=1.2,
            label=f"Optimal ({optimal:.0f})",
        )

    ax.set_xlabel("Generation")
    ax.set_ylabel("Best-so-far length")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    _save_or_show(fig, save_path)


def animate_evolution(
    tour_history: list[Tour],
    instance: TSPInstance,
    save_path: str,
) -> None:
    """Create a GIF or MP4 animation from saved best tours."""

    if not tour_history:
        raise ValueError("tour_history must not be empty")
    for tour in tour_history:
        if not tour.is_valid(instance.dimension):
            raise ValueError("every tour in tour_history must be valid")

    coords = instance.coords
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(coords[:, 0], coords[:, 1], s=22, color="#222222", zorder=3)
    line, = ax.plot([], [], color="#3b6ea8", linewidth=1.3, alpha=0.85)
    start_scatter = ax.scatter([], [], s=70, color="red", zorder=4)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.axis("equal")
    ax.grid(alpha=0.25)

    def update(frame: int) -> tuple:
        tour = tour_history[frame]
        order = np.array(tour.cities + [tour.cities[0]], dtype=int)
        ordered_coords = coords[order]
        line.set_data(ordered_coords[:, 0], ordered_coords[:, 1])
        start_city = tour.cities[0]
        start_scatter.set_offsets([coords[start_city]])
        ax.set_title(
            f"generation={frame}, length={tour.length(instance):.0f}"
        )
        return line, start_scatter

    animation = FuncAnimation(
        fig,
        update,
        frames=len(tour_history),
        interval=200,
        blit=False,
    )
    output_path = Path(save_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()
    if suffix == ".gif":
        animation.save(output_path, writer="pillow", fps=5)
    elif suffix == ".mp4":
        animation.save(output_path, writer="ffmpeg", fps=5)
    else:
        raise ValueError("save_path must end with .gif or .mp4")
    plt.close(fig)


def _save_or_show(fig: plt.Figure, save_path: str | None) -> None:
    if save_path:
        output_path = Path(save_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
    else:
        plt.show()


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
    initial = nearest_neighbor(instance, start=0)
    ma = MemeticAlgorithm(seed=0)
    final, history = ma.solve(instance)

    plot_tour(initial, instance, "Initial NN tour", _results_path("initial_tour.png"))
    plot_tour(final, instance, "Final MA tour", _results_path("final_tour.png"))
    plot_convergence(
        {"MA": history},
        optimal=7542.0,
        save_path=str(_results_path("ma_convergence.png")),
    )
    print("saved visualizations under results/")


if __name__ == "__main__":
    _run_demo()
