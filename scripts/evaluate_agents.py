"""
Score saved agent checkpoints on the held-out seeds and explain what each one does.

For each checkpoint: win rate, forced-sale rate, selling cost, invalid actions, and action
mix overall and in three cases (payout due within 5 days, over the small-cap limit,
big buyer offered). For comparison, random play is scored too.

Run from the project root:

uv run python scripts/evaluate_agents.py models/pg/pension5_seed0_best.pt models/pg/pension5_seed1_best.pt models/pg/pension5_seed2_best.pt
"""

import sys
from collections import Counter
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classes import RandomPolicy, ThinBookPensionEnv, TorchPolicy  # noqa: E402
from custom_types import GameResult, MarketConfig  # noqa: E402
from environment.baselines import evaluate, evaluation_seeds  # noqa: E402
from environment.custom_env import load_config  # noqa: E402
from environment.policy_helpers import read_step_info  # noqa: E402
from training.common import make_network, scorecard  # noqa: E402

HIDDEN_SIZE = 128

BEHAVIOUR_GAMES = 100


def action_mix(policy: TorchPolicy, config: MarketConfig) -> dict[str, Counter[str]]:
    env = ThinBookPensionEnv(config)

    mixes: dict[str, Counter[str]] = {"all days": Counter(), "payout due within 5 days": Counter(), "over the small-cap limit": Counter(), "big buyer offered": Counter()}

    for seed in evaluation_seeds(BEHAVIOUR_GAMES):
        observation, raw_info = env.reset(seed=seed)

        info = read_step_info(raw_info)

        finished = False

        while not finished:
            action = policy.act(observation, info)

            name = env.action_names[action]

            mixes["all days"][name] += 1

            if info["due_within_5_naira"] > 0:
                mixes["payout due within 5 days"][name] += 1

            if info["in_breach"]:
                mixes["over the small-cap limit"][name] += 1

            if info["big_buyer_offered_today"]:
                mixes["big buyer offered"][name] += 1

            observation, _, finished, _, raw_info = env.step(action)

            info = read_step_info(raw_info)

    return mixes


def report(label: str, results: list[GameResult], threshold: float) -> None:
    card = scorecard(results, threshold)

    print(f"{label:<34} won {card['win_rate']:6.1%}  points {card['mean_points']:7.1f}  cost {card['mean_cost_bps']:6.1f} bps  forced {card['forced_sale_rate']:6.1%}  invalid/game {card['invalid_actions_per_game']:.1f}")


def main() -> None:
    config = load_config()

    threshold = config["won_cost_bps"]

    seeds = evaluation_seeds()

    action_count = len(ThinBookPensionEnv(config).action_names)

    print(f"500 held-out seeds, X = {threshold:.0f} bps")

    report("random", evaluate(RandomPolicy(), config, seeds), threshold)

    for checkpoint in sys.argv[1:]:
        network = make_network(action_count, HIDDEN_SIZE)

        network.load_state_dict(torch.load(checkpoint))

        policy = TorchPolicy(network)

        report(Path(checkpoint).stem, evaluate(policy, config, seeds), threshold)

        for situation, counts in action_mix(policy, config).items():
            total = sum(counts.values())

            top_actions: list[str] = []

            for name, count in counts.most_common(3):
                top_actions.append(f"{name} {count / total:.0%}")

            top = ", ".join(top_actions)

            print(f"    {situation:<26} ({total} days): {top}")


if __name__ == "__main__":
    main()
