"""
Draw the report figures from the saved sweep logs (no training, no numbers typed by hand).

1. Cumulative rewards: total points per training game for each method's best run, with a rolling average.

2. Training stability: DQN's TD loss over training, and policy entropy for REINFORCE, A2C and PPO.

3. Convergence: validation win rate over training for each best run, and how many training games each
needed to converge: the first game at which its 200-game average of points has covered 90% of its total
improvement, from its level over the first 200 games to its final level (the mean of the last 1,000
games). Written to report_tables/convergence.csv and .md.

4. Sweep overview: held-out win rate of all 40 runs against the best simple rule and the planner.

The best run of each method is the one with the highest held-out win rate (mean points break ties).
Figures are written to figures/fig_*.png.

Run from the project root: uv run python scripts/make_figures.py
"""

import csv
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_types import RunSummary  # noqa: E402
from environment.model_registry import best_sweep_run, read_summary  # noqa: E402
from training.common import PROJECT_ROOT  # noqa: E402

FIGURES_DIR = PROJECT_ROOT / "figures"

TABLES_DIR = PROJECT_ROOT / "report_tables"

SWEEP_LOGS = PROJECT_ROOT / "logs" / "sweep"

ALGORITHMS = ["dqn", "reinforce", "a2c", "ppo"]

NAMES = {"dqn": "DQN", "reinforce": "REINFORCE", "a2c": "A2C", "ppo": "PPO"}

COLOURS = {"dqn": "#7b4fb8", "reinforce": "#e07a1f", "a2c": "#2a9d8f", "ppo": "#3b6fb6"}

GAME_LENGTH_DAYS = 60

ROLLING_GAMES = 200

ROLLING_BATCHES = 50

IMPROVEMENT_SHARE = 0.9

FINAL_GAMES = 1000

BLOCK_DEALER_ROW = "block_dealer"

PLANNER_ROW = "perfect_foresight_planner"

DPI = 160


def read_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    csv_file = open(path, encoding="utf-8")

    for row in csv.DictReader(csv_file):
        rows.append(row)

    csv_file.close()

    return rows


def numbers(rows: list[dict[str, str]], column: str) -> np.ndarray:
    values: list[float] = []

    for row in rows:
        values.append(float(row[column]))

    return np.array(values)


def rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    if len(values) < window:
        return values

    kernel = np.ones(window) / window

    return np.convolve(values, kernel, mode="valid")


def baseline_numbers(row_name: str) -> tuple[float, float]:
    for row in read_rows(TABLES_DIR / "agents_vs_baselines_normal.csv"):
        if row["Policy"] == row_name:
            return float(row["Win rate"].rstrip("%")) / 100, float(row["Mean points"])

    raise SystemExit(f"{row_name} is missing from report_tables/agents_vs_baselines_normal.csv")


def best_runs() -> dict[str, RunSummary]:
    runs: dict[str, RunSummary] = {}

    for algorithm in ALGORITHMS:
        summary = best_sweep_run(algorithm)

        if summary is None:
            raise SystemExit(f"No finished {algorithm} run in logs/sweep/{algorithm}")

        runs[algorithm] = summary

    return runs


def save(figure: plt.Figure, name: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    figure.tight_layout()

    figure.savefig(FIGURES_DIR / name, dpi=DPI)

    plt.close(figure)

    print(f"Wrote figures/{name}")


def plot_cumulative_rewards(runs: dict[str, RunSummary], block_dealer_points: float) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(11, 7), sharey=True)

    for axis, algorithm in zip(axes.flatten(), ALGORITHMS):
        run_name = runs[algorithm]["name"]

        episodes = read_rows(SWEEP_LOGS / algorithm / f"{run_name}_episodes.csv")

        points = numbers(episodes, "points")

        games = np.arange(1, len(points) + 1)

        smooth = rolling_mean(points, ROLLING_GAMES)

        axis.plot(games, points, color=COLOURS[algorithm], alpha=0.12, linewidth=0.6)

        axis.plot(games[len(games) - len(smooth):], smooth, color=COLOURS[algorithm], linewidth=2, label=f"{ROLLING_GAMES}-game average")

        axis.axhline(block_dealer_points, color="#444444", linestyle="--", linewidth=1, label="best simple rule (held-out mean)")

        axis.set_title(f"{NAMES[algorithm]} ({run_name})")

        axis.set_xlabel("training game")

        axis.set_ylabel("total points per game")

        axis.set_ylim(-90, 15)

        axis.legend(loc="lower right", fontsize=8)

    figure.suptitle("Total points per training game, best run of each method (training games include exploration)")

    save(figure, "fig_cumulative_rewards.png")


def plot_training_stability(runs: dict[str, RunSummary]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(11, 7))

    for axis, algorithm in zip(axes.flatten(), ALGORITHMS):
        run_name = runs[algorithm]["name"]

        training = read_rows(SWEEP_LOGS / algorithm / f"{run_name}_training.csv")

        frames = numbers(training, "frames")

        column = "td_loss" if algorithm == "dqn" else "entropy"

        values = numbers(training, column)

        keep = np.isfinite(values)

        frames = frames[keep]

        values = values[keep]

        window = ROLLING_BATCHES if algorithm == "dqn" else max(len(values) // 40, 1)

        smooth = rolling_mean(values, window)

        axis.plot(frames / GAME_LENGTH_DAYS, values, color=COLOURS[algorithm], alpha=0.2, linewidth=0.6)

        axis.plot(frames[len(frames) - len(smooth):] / GAME_LENGTH_DAYS, smooth, color=COLOURS[algorithm], linewidth=2)

        axis.set_title(f"{NAMES[algorithm]} ({run_name}): {'TD loss (objective)' if algorithm == 'dqn' else 'policy entropy'}")

        axis.set_xlabel("training games")

        axis.set_ylabel("smooth L1 TD loss" if algorithm == "dqn" else "entropy (nats)")

        if algorithm != "dqn":
            axis.axhline(math.log(5), color="#999999", linestyle=":", linewidth=1, label="uniform over 5 actions")

            axis.legend(loc="upper right", fontsize=8)

    figure.suptitle("Training stability: DQN objective and policy entropy of the policy-gradient methods")

    save(figure, "fig_training_stability.png")


def games_to_converge(points: np.ndarray) -> tuple[int, float, float]:
    start_level = float(np.mean(points[:ROLLING_GAMES]))

    final_level = float(np.mean(points[-FINAL_GAMES:]))

    target = start_level + IMPROVEMENT_SHARE * (final_level - start_level)

    smooth = rolling_mean(points, ROLLING_GAMES)

    for index in range(len(smooth)):
        if smooth[index] >= target:
            return index + ROLLING_GAMES, start_level, final_level

    return len(points), start_level, final_level


def plot_convergence(runs: dict[str, RunSummary]) -> None:
    figure, axis = plt.subplots(figsize=(10, 5))

    table: list[list[str]] = [["Method", "Best run", "First 200 games (points per game)", "Last 1,000 games (points per game)", "Training games to converge", "Best validation win rate", "Held-out win rate"]]

    for algorithm in ALGORITHMS:
        summary = runs[algorithm]

        training = read_rows(SWEEP_LOGS / algorithm / f"{summary['name']}_training.csv")

        frames = numbers(training, "frames")

        win_rates = numbers(training, "validation_win_rate")

        keep = np.isfinite(win_rates)

        frames = frames[keep]

        win_rates = win_rates[keep]

        axis.plot(frames / GAME_LENGTH_DAYS, win_rates * 100, color=COLOURS[algorithm], linewidth=2, marker="o", markersize=2.5, label=f"{NAMES[algorithm]} ({summary['name']})")

        episodes = read_rows(SWEEP_LOGS / algorithm / f"{summary['name']}_episodes.csv")

        games, start_level, final_level = games_to_converge(numbers(episodes, "points"))

        table.append([NAMES[algorithm], summary["name"], f"{start_level:.1f}", f"{final_level:.1f}", f"{games:,}", f"{np.max(win_rates):.1%}", f"{summary['held_out']['win_rate']:.1%}"])

    axis.set_xlabel("training games")

    axis.set_ylabel("validation win rate (%)")

    axis.set_title("Validation win rate during training (200 validation games every 24,000 frames)")

    axis.set_ylim(-2, 65)

    axis.legend(loc="upper left", fontsize=9)

    axis.grid(alpha=0.3)

    save(figure, "fig_convergence.png")

    write_table("convergence", table)


def plot_sweep_overview(block_dealer_win_rate: float, planner_win_rate: float) -> None:
    figure, axis = plt.subplots(figsize=(11, 4.5))

    position = 0

    ticks: list[float] = []

    for algorithm in ALGORITHMS:
        names: list[str] = []

        win_rates: list[float] = []

        for summary_path in sorted((SWEEP_LOGS / algorithm).glob("*_summary.json")):
            summary = read_summary(summary_path)

            names.append(summary["name"])

            win_rates.append(summary["held_out"]["win_rate"] * 100)

        positions = np.arange(position, position + len(win_rates))

        axis.bar(positions, win_rates, color=COLOURS[algorithm], label=NAMES[algorithm])

        if max(win_rates) <= 0:
            axis.text(float(np.mean(positions)), 1.5, "all 10 runs: 0%", ha="center", fontsize=9, color=COLOURS[algorithm])

        ticks.append(float(np.mean(positions)))

        position = position + len(win_rates) + 2

    axis.axhline(block_dealer_win_rate * 100, color="#444444", linestyle="--", linewidth=1.2, label=f"best simple rule {block_dealer_win_rate:.1%}")

    axis.axhline(planner_win_rate * 100, color="#b03a3a", linestyle=":", linewidth=1.2, label=f"perfect foresight (cheats) {planner_win_rate:.1%}")

    labels: list[str] = []

    for algorithm in ALGORITHMS:
        labels.append(NAMES[algorithm])

    axis.set_xticks(ticks)

    axis.set_xticklabels(labels)

    axis.set_ylabel("held-out win rate (%)")

    axis.set_title("All 40 sweep runs on the 500 held-out games (10 settings per method)")

    axis.legend(loc="upper left", fontsize=8, ncol=3)

    save(figure, "fig_sweep_overview.png")


def write_table(name: str, rows: list[list[str]]) -> None:
    csv_file = open(TABLES_DIR / f"{name}.csv", "w", newline="", encoding="utf-8")

    csv.writer(csv_file).writerows(rows)

    csv_file.close()

    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]

    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    (TABLES_DIR / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote report_tables/{name}.csv and .md")


def main() -> None:
    runs = best_runs()

    block_dealer_win_rate, block_dealer_points = baseline_numbers(BLOCK_DEALER_ROW)

    planner_win_rate, _ = baseline_numbers(PLANNER_ROW)

    plot_cumulative_rewards(runs, block_dealer_points)

    plot_training_stability(runs)

    plot_convergence(runs)

    plot_sweep_overview(block_dealer_win_rate, planner_win_rate)


if __name__ == "__main__":
    main()
