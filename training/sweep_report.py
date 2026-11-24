"""
Build the report tables from the sweep summaries (never typed by hand).

For each algorithm: one row per run with the hyperparameters the report template asks for,
then the five held-out numbers (Win rate, mean cost in bps, forced-sale rate, invalid actions
per game, and Mean Reward = mean points per game), written as CSV and Markdown to
report_tables/<algorithm>.csv and report_tables/<algorithm>.md.

Run from the project root: uv run python -m training.sweep_report
"""

import csv
import json
from typing import cast

from custom_types import DqnSettings, PgSettings, RunSummary, Scorecard, TableRow
from training.common import PROJECT_ROOT
from training.sweep import ALGORITHMS, LOGS_ROOT

TABLES_DIR = PROJECT_ROOT / "report_tables"

GAME_LENGTH_DAYS = 60

METRIC_COLUMNS = ["Win rate", "Mean cost (bps)", "Forced-sale rate", "Invalid actions per game", "Mean Reward (points)"]


def dqn_columns(settings: DqnSettings) -> TableRow:
    exploration = f"epsilon-greedy {settings['epsilon_start']} to {settings['epsilon_end']} over {settings['epsilon_decay_frames']:,} frames"

    target = f"soft, tau {settings['tau']}" if settings["target_update"] == "soft" else f"hard, every {settings['hard_update_every']} updates"

    columns: TableRow = {
        "Target Update": target,
        "Gamma": settings["gamma"],
        "Exploration Strategy": exploration,
        "Batch Size": settings["batch_size"],
        "Learning Rate": settings["learning_rate"],
        "Replay Buffer Size": settings["buffer_size"],
        "Network": f"2 x {settings['hidden_size']}",
    }

    return columns


def policy_gradient_columns(algorithm: str, settings: PgSettings) -> TableRow:
    if algorithm == "reinforce":
        return {
            "Gamma": settings["gamma"],
            "Baseline": settings["baseline"],
            "Learning Rate": settings["learning_rate"],
            "Entropy Coefficient": settings["entropy"],
            "Network": f"2 x {settings['hidden_size']}",
            "Games per Update": settings["rollout"] // GAME_LENGTH_DAYS,
        }

    if algorithm == "a2c":
        return {
            "Gamma": settings["gamma"],
            "Rollout Steps": settings["rollout"],
            "GAE Lambda": settings["gae_lambda"],
            "Entropy Coefficient": settings["entropy"],
            "Learning Rate": settings["learning_rate"],
            "Value Coefficient": settings["value_coefficient"],
        }

    return {
        "Gamma": settings["gamma"],
        "Epochs": settings["epochs"],
        "Clip Range": settings["clip"],
        "Minibatch": settings["minibatch"],
        "Rollout Steps": settings["rollout"],
        "GAE Lambda": settings["gae_lambda"],
        "Learning Rate": settings["learning_rate"],
        "Entropy Coefficient": settings["entropy"],
        "Value Coefficient": settings["value_coefficient"],
    }


def metric_columns(card: Scorecard) -> dict[str, str]:
    columns = {
        "Win rate": f"{card['win_rate']:.1%}",
        "Mean cost (bps)": f"{card['mean_cost_bps']:.1f}",
        "Mean Reward (points)": f"{card['mean_points']:.2f}",
        "Forced-sale rate": f"{card['forced_sale_rate']:.1%}",
        "Invalid actions per game": f"{card['invalid_actions_per_game']:.2f}",
    }

    return columns


def table_rows(algorithm: str) -> list[TableRow]:
    rows: list[TableRow] = []

    for summary_path in sorted((LOGS_ROOT / algorithm).glob("*_summary.json")):
        summary: RunSummary = json.loads(summary_path.read_text(encoding="utf-8"))

        if algorithm == "dqn":
            hyperparameters = dqn_columns(cast(DqnSettings, summary["settings"]))

        else:
            hyperparameters = policy_gradient_columns(algorithm, cast(PgSettings, summary["settings"]))

        row: TableRow = {"Run": summary["name"]}

        row.update(hyperparameters)

        row.update(metric_columns(summary["held_out"]))

        rows.append(row)

    return rows


def write_tables(algorithm: str, rows: list[TableRow]) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    columns = list(rows[0].keys())

    csv_file = open(TABLES_DIR / f"{algorithm}.csv", "w", newline="", encoding="utf-8")

    writer = csv.DictWriter(csv_file, fieldnames=columns)

    writer.writeheader()

    writer.writerows(rows)

    csv_file.close()

    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]

    for row in rows:
        cells: list[str] = []

        for column in columns:
            cells.append(str(row[column]))

        lines.append("| " + " | ".join(cells) + " |")

    (TABLES_DIR / f"{algorithm}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    for algorithm in ALGORITHMS:
        rows = table_rows(algorithm)

        if not rows:
            print(f"{algorithm}: no finished runs yet")

            continue

        write_tables(algorithm, rows)

        print(f"{algorithm}: {len(rows)} runs -> {TABLES_DIR / (algorithm + '.md')}")


if __name__ == "__main__":
    main()
