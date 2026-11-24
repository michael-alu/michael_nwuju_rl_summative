"""
Compare every baseline, the perfect-foresight planner and saved agents on the same seeds.

1. Score each simple baseline and the planner on the 500 held-out seeds (normal + hard market).
2. Score each saved agent checkpoint on the same seeds, then insert one row with the mean of the
checkpoints' numbers (e.g., 3 PPO seeds).
3. Print the five numbers (win rate, mean points, cost in bps, forced-sale rate, invalid actions
per game) and save to report_tables/agents_vs_baselines_<market>.csv and .md.

Run from the project root:

uv run python scripts/compare_agents.py --label "PPO (mean of 3 seeds)" models/pg/pension5_seed0_best.pt models/pg/pension5_seed1_best.pt models/pg/pension5_seed2_best.pt
"""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classes import PerfectForesightPlanner, ThinBookPensionEnv, TorchPolicy  # noqa: E402
from custom_types import MarketConfig, Scorecard  # noqa: E402
from environment.baselines import evaluate, evaluation_seeds, simple_baselines  # noqa: E402
from environment.custom_env import load_config, load_hard_config  # noqa: E402
from training.common import PROJECT_ROOT, make_network, scorecard  # noqa: E402

TABLES_DIR = PROJECT_ROOT / "report_tables"

HIDDEN_SIZE = 128

HEADERS = ["Policy", "Win rate", "Mean points", "Mean cost (bps)", "Forced-sale rate", "Invalid actions per game"]


def load_agent(checkpoint: str, config: MarketConfig) -> TorchPolicy:
    network = make_network(len(ThinBookPensionEnv(config).action_names), HIDDEN_SIZE)

    network.load_state_dict(torch.load(checkpoint))

    return TorchPolicy(network)


def mean_scorecard(cards: list[Scorecard]) -> Scorecard:
    games: list[int] = []

    win_rates: list[float] = []

    points: list[float] = []

    costs: list[float] = []

    forced_sale_rates: list[float] = []

    invalid_actions: list[float] = []

    for card in cards:
        games.append(card["games"])

        win_rates.append(card["win_rate"])

        points.append(card["mean_points"])

        costs.append(card["mean_cost_bps"])

        forced_sale_rates.append(card["forced_sale_rate"])

        invalid_actions.append(card["invalid_actions_per_game"])

    mean_card: Scorecard = {
        "games": round(float(np.mean(games))),
        "win_rate": float(np.mean(win_rates)),
        "mean_points": float(np.mean(points)),
        "mean_cost_bps": float(np.mean(costs)),
        "forced_sale_rate": float(np.mean(forced_sale_rates)),
        "invalid_actions_per_game": float(np.mean(invalid_actions)),
    }

    return mean_card


def format_row(name: str, card: Scorecard) -> list[str]:
    row = [
        name,
        f"{card['win_rate']:.1%}",
        f"{card['mean_points']:.2f}",
        f"{card['mean_cost_bps']:.1f}",
        f"{card['forced_sale_rate']:.1%}",
        f"{card['invalid_actions_per_game']:.2f}",
    ]

    return row


def compare(market: str, config: MarketConfig, checkpoints: list[str], label: str) -> list[list[str]]:
    seeds = evaluation_seeds()

    threshold = config["won_cost_bps"]

    rows: list[list[str]] = []

    for policy in simple_baselines(config) + [PerfectForesightPlanner(config)]:
        rows.append(format_row(policy.name, scorecard(evaluate(policy, config, seeds), threshold)))

    agent_cards: list[Scorecard] = []

    for checkpoint in checkpoints:
        card = scorecard(evaluate(load_agent(checkpoint, config), config, seeds), threshold)

        agent_cards.append(card)

        rows.append(format_row(Path(checkpoint).stem, card))

    if agent_cards:
        rows.append(format_row(label, mean_scorecard(agent_cards)))

    print(f"\n{market} market, {len(seeds)} held-out seeds, X = {threshold:.0f} bps")

    header_line = f"{HEADERS[0]:<30}"

    for header in HEADERS[1:]:
        header_line = header_line + f"{header:>26}"

    print(header_line)

    for row in rows:
        row_line = f"{row[0]:<30}"

        for value in row[1:]:
            row_line = row_line + f"{value:>26}"

        print(row_line)

    return rows


def save(market: str, rows: list[list[str]]) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    csv_file = open(TABLES_DIR / f"agents_vs_baselines_{market}.csv", "w", newline="", encoding="utf-8")

    writer = csv.writer(csv_file)

    writer.writerow(HEADERS)

    writer.writerows(rows)

    csv_file.close()

    lines = ["| " + " | ".join(HEADERS) + " |", "|" + "---|" * len(HEADERS)]

    for row in rows:
        lines.append("| " + " | ".join(row) + " |")

    (TABLES_DIR / f"agents_vs_baselines_{market}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baselines, the planner and saved agents.")

    parser.add_argument("checkpoints", nargs="*")

    parser.add_argument("--label", default="agents (mean)")

    arguments = parser.parse_args()

    for market, config in [("normal", load_config()), ("hard", load_hard_config())]:
        save(market, compare(market, config, arguments.checkpoints, arguments.label))


if __name__ == "__main__":
    main()
