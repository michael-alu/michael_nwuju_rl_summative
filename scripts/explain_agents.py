"""
Explain why the best models score so differently: play each method's best model, the best simple rule
and the perfect-foresight planner on the 500 held-out games and measure how each one behaves.

1. Where the selling cost comes from: sales the player chose (T-bills, banks, small caps on the
exchange), block deals with the big buyer, forced sales to pay a retiree, and forced sales over a limit.

2. How it handles payouts: on days with a payout due within 5 days, how often the cash (plus sale cash
arriving tomorrow) already covers it.

3. How it handles the small-cap limit (days over it per game) and the big buyer (share of offered days
it takes the deal).

4. Its action mix over all days.

Writes report_tables/behaviour.csv and .md and prints the same numbers.

Run from the project root: uv run python scripts/explain_agents.py
"""

import csv
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classes import BlockDealerPolicy, PerfectForesightPlanner, Policy, ThinBookPensionEnv, TorchPolicy  # noqa: E402
from custom_types import BehaviourSummary, MarketConfig, StepInfo  # noqa: E402
from environment.baselines import evaluation_seeds  # noqa: E402
from environment.custom_env import ACTION_NAMES, CALL_BIG_BUYER, load_config  # noqa: E402
from environment.model_registry import agent_entry, load_network  # noqa: E402
from environment.policy_helpers import read_step_info  # noqa: E402
from training.common import PROJECT_ROOT  # noqa: E402

TABLES_DIR = PROJECT_ROOT / "report_tables"

ALGORITHMS = ["ppo", "dqn", "reinforce", "a2c"]

NAMES = {"dqn": "DQN", "reinforce": "REINFORCE", "a2c": "A2C", "ppo": "PPO"}

HEADERS = [
    "Player",
    "Win rate",
    "Forced-sale rate",
    "Total cost (bps)",
    "Chosen sales (bps)",
    "Of which small caps on the exchange (bps)",
    "Big buyer deals (bps)",
    "Forced to pay a retiree (bps)",
    "Forced over a limit (bps)",
    "Cash ready when a payout is near",
    "Days over a limit per game",
    "Big buyer offers taken",
]


def cost_bucket(reason: str) -> str:
    if reason == "big buyer":
        return "big_buyer"

    if reason.startswith("forced: payout"):
        return "forced_payout"

    if reason.startswith("forced"):
        return "forced_limit"

    return "chosen"


def summarise(player: str, policy: Policy, config: MarketConfig, seeds: list[int]) -> BehaviourSummary:
    env = ThinBookPensionEnv(config)

    fund = config["starting_fund_naira"]

    costs = {"chosen": 0.0, "big_buyer": 0.0, "forced_payout": 0.0, "forced_limit": 0.0}

    small_caps_on_exchange = 0.0

    action_counts: dict[str, int] = {}

    for name in ACTION_NAMES:
        action_counts[name] = 0

    wins = 0

    forced_games = 0

    total_cost_bps = 0.0

    payout_near_days = 0

    cash_ready_days = 0

    breach_days = 0

    offered_days = 0

    taken_days = 0

    total_days = 0

    for seed in seeds:
        observation, raw_info = env.reset(seed=seed)

        info: StepInfo = read_step_info(raw_info)

        policy.reset(env)

        finished = False

        while not finished:
            if info["due_within_5_naira"] > 0:
                payout_near_days = payout_near_days + 1

                if info["cash_naira"] + info["settling_naira"] >= info["due_within_5_naira"]:
                    cash_ready_days = cash_ready_days + 1

            if info["in_breach"]:
                breach_days = breach_days + 1

            action = policy.act(observation, info)

            if info["big_buyer_offered_today"]:
                offered_days = offered_days + 1

                if action == CALL_BIG_BUYER:
                    taken_days = taken_days + 1

            action_counts[ACTION_NAMES[action]] = action_counts[ACTION_NAMES[action]] + 1

            total_days = total_days + 1

            observation, _, finished, _, raw_info = env.step(action)

            info = read_step_info(raw_info)

            for trade in info["trades"]:
                bucket = cost_bucket(trade["reason"])

                costs[bucket] = costs[bucket] + trade["cost"]

                if bucket == "chosen" and trade["asset"] == "small_caps":
                    small_caps_on_exchange = small_caps_on_exchange + trade["cost"]

        if info["outcome"] == "won":
            wins = wins + 1

        if info["forced_event_count"] > 0:
            forced_games = forced_games + 1

        total_cost_bps = total_cost_bps + info["cost_bps"]

    games = len(seeds)

    to_bps = 10000 / (fund * games)

    action_shares: dict[str, float] = {}

    for name in ACTION_NAMES:
        action_shares[name] = action_counts[name] / total_days

    summary: BehaviourSummary = {
        "player": player,
        "games": games,
        "win_rate": wins / games,
        "forced_sale_rate": forced_games / games,
        "cost_bps": total_cost_bps / games,
        "chosen_sales_bps": costs["chosen"] * to_bps,
        "big_buyer_bps": costs["big_buyer"] * to_bps,
        "forced_payout_bps": costs["forced_payout"] * to_bps,
        "forced_limit_bps": costs["forced_limit"] * to_bps,
        "cash_ready_share": cash_ready_days / max(payout_near_days, 1),
        "breach_days_per_game": breach_days / games,
        "big_buyer_taken_share": taken_days / max(offered_days, 1),
        "small_caps_on_exchange_bps": small_caps_on_exchange * to_bps,
        "action_shares": action_shares,
    }

    return summary


def table_row(summary: BehaviourSummary) -> list[str]:
    row = [
        summary["player"],
        f"{summary['win_rate']:.1%}",
        f"{summary['forced_sale_rate']:.1%}",
        f"{summary['cost_bps']:.1f}",
        f"{summary['chosen_sales_bps']:.1f}",
        f"{summary['small_caps_on_exchange_bps']:.1f}",
        f"{summary['big_buyer_bps']:.1f}",
        f"{summary['forced_payout_bps']:.1f}",
        f"{summary['forced_limit_bps']:.1f}",
        f"{summary['cash_ready_share']:.1%}",
        f"{summary['breach_days_per_game']:.1f}",
        f"{summary['big_buyer_taken_share']:.1%}",
    ]

    return row


def action_mix_line(summary: BehaviourSummary) -> str:
    parts: list[str] = []

    for name in ACTION_NAMES:
        parts.append(f"{name} {summary['action_shares'][name]:.0%}")

    return f"{summary['player']:<32} " + ", ".join(parts)


def write_table(rows: list[list[str]]) -> None:
    csv_file = open(TABLES_DIR / "behaviour.csv", "w", newline="", encoding="utf-8")

    csv.writer(csv_file).writerows(rows)

    csv_file.close()

    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]

    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    (TABLES_DIR / "behaviour.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    torch.set_num_threads(1)

    config = load_config()

    seeds = evaluation_seeds()

    players: list[tuple[str, Policy]] = []

    for algorithm in ALGORITHMS:
        entry = agent_entry(algorithm)

        players.append((f"{NAMES[algorithm]} ({entry['run_name']})", TorchPolicy(load_network(entry))))

    players.append(("Best simple rule (block_dealer)", BlockDealerPolicy(config)))

    players.append(("Perfect foresight (cheats)", PerfectForesightPlanner(config)))

    rows: list[list[str]] = [HEADERS]

    mix_lines: list[str] = []

    for player, policy in players:
        summary = summarise(player, policy, config, seeds)

        rows.append(table_row(summary))

        mix_lines.append(action_mix_line(summary))

        print(" | ".join(table_row(summary)), flush=True)

    print()

    print("Action mix over all days:")

    for line in mix_lines:
        print(line)

    write_table(rows)

    print("Wrote report_tables/behaviour.csv and .md")


if __name__ == "__main__":
    main()
