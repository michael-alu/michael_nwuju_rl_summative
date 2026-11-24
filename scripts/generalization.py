"""
Test how well each method's best model generalises: the 500 held-out games of the normal market (never
used for any choice) and 500 games of a hard market it never trained on (more and longer dry spells,
more stormy days, bigger payouts: configs/market_hard.yaml).

1. Pick each method's best sweep run (highest held-out win rate, mean points break ties).

2. Score its saved best checkpoint on both markets with the same seeds the baselines used.

3. Add the best simple rule and the perfect-foresight planner from report_tables/agents_vs_baselines_*.csv.

4. Write report_tables/generalization.csv and .md.

Run from the project root: uv run python scripts/generalization.py
"""

import csv
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classes import TorchPolicy  # noqa: E402
from custom_types import MarketConfig, Scorecard  # noqa: E402
from environment.baselines import evaluate, evaluation_seeds  # noqa: E402
from environment.custom_env import ACTION_NAMES, load_config, load_hard_config  # noqa: E402
from environment.model_registry import best_sweep_run, model_path  # noqa: E402
from training.common import PROJECT_ROOT, make_network, scorecard  # noqa: E402

TABLES_DIR = PROJECT_ROOT / "report_tables"

ALGORITHMS = ["dqn", "reinforce", "a2c", "ppo"]

NAMES = {"dqn": "DQN", "reinforce": "REINFORCE", "a2c": "A2C", "ppo": "PPO"}

BASELINE_ROWS = {"block_dealer": "Best simple rule (block_dealer)", "perfect_foresight_planner": "Perfect foresight (cheats)"}

HEADERS = ["Player", "Normal: win rate", "Normal: mean points", "Normal: cost (bps)", "Hard: win rate", "Hard: mean points", "Hard: cost (bps)", "Hard: forced-sale rate", "Change in win rate"]


def score_model(path: Path, hidden_size: int, config: MarketConfig) -> Scorecard:
    network = make_network(len(ACTION_NAMES), hidden_size)

    network.load_state_dict(torch.load(path))

    results = evaluate(TorchPolicy(network), config, evaluation_seeds())

    return scorecard(results, config["won_cost_bps"])


def baseline_row(policy: str, market: str) -> dict[str, str]:
    csv_file = open(TABLES_DIR / f"agents_vs_baselines_{market}.csv", encoding="utf-8")

    for row in csv.DictReader(csv_file):
        if row["Policy"] == policy:
            csv_file.close()

            return row

    csv_file.close()

    raise SystemExit(f"{policy} is missing from report_tables/agents_vs_baselines_{market}.csv")


def table_row(name: str, normal: Scorecard, hard: Scorecard) -> list[str]:
    change = (hard["win_rate"] - normal["win_rate"]) * 100

    row = [
        name,
        f"{normal['win_rate']:.1%}",
        f"{normal['mean_points']:.2f}",
        f"{normal['mean_cost_bps']:.1f}",
        f"{hard['win_rate']:.1%}",
        f"{hard['mean_points']:.2f}",
        f"{hard['mean_cost_bps']:.1f}",
        f"{hard['forced_sale_rate']:.1%}",
        f"{change:+.1f} points",
    ]

    return row


def card_from_table(row: dict[str, str]) -> Scorecard:
    card: Scorecard = {
        "games": 500,
        "win_rate": float(row["Win rate"].rstrip("%")) / 100,
        "mean_points": float(row["Mean points"]),
        "mean_cost_bps": float(row["Mean cost (bps)"]),
        "forced_sale_rate": float(row["Forced-sale rate"].rstrip("%")) / 100,
        "invalid_actions_per_game": float(row["Invalid actions per game"]),
    }

    return card


def write_table(rows: list[list[str]]) -> None:
    csv_file = open(TABLES_DIR / "generalization.csv", "w", newline="", encoding="utf-8")

    csv.writer(csv_file).writerows(rows)

    csv_file.close()

    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]

    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    (TABLES_DIR / "generalization.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    torch.set_num_threads(1)

    normal_config = load_config()

    hard_config = load_hard_config()

    rows: list[list[str]] = [HEADERS]

    for algorithm in ALGORITHMS:
        summary = best_sweep_run(algorithm)

        if summary is None:
            raise SystemExit(f"No finished {algorithm} run")

        path = model_path(algorithm, summary["name"])

        hidden_size = summary["settings"]["hidden_size"]

        normal = score_model(path, hidden_size, normal_config)

        hard = score_model(path, hidden_size, hard_config)

        rows.append(table_row(f"{NAMES[algorithm]} ({summary['name']})", normal, hard))

        print(f"{NAMES[algorithm]:<10} normal {normal['win_rate']:.1%}  hard {hard['win_rate']:.1%}", flush=True)

    for policy, name in BASELINE_ROWS.items():
        normal = card_from_table(baseline_row(policy, "normal"))

        hard = card_from_table(baseline_row(policy, "hard"))

        rows.append(table_row(name, normal, hard))

    write_table(rows)

    print("Wrote report_tables/generalization.csv and .md")


if __name__ == "__main__":
    main()
