"""
Ensure the game and a trained agent still output exactly the same numbers.

Use it before and after you rewrite code (like into your own style):
1. uv run python scripts/check_determinism.py --save --note "why" (records the reference numbers)
2. Rewrite the code
3. uv run python scripts/check_determinism.py (compares, prints MATCH or DIFFERENT)

What it measures, all on fixed seeds:

- A saved PPO model (models/pg/pension5_seed0_best.pt) re-scored on 100 held-out seeds;
- Random play throughout the env (every rule affects these numbers);
- The block_dealer baseline, and the perfect-foresight planner.

Reference file: logs/determinism_reference.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classes import BlockDealerPolicy, PerfectForesightPlanner, ThinBookPensionEnv, TorchPolicy  # noqa: E402
from custom_types import DeterminismReference, MarketConfig, RandomPlayFingerprint, Scorecard  # noqa: E402
from environment.baselines import evaluate, evaluation_seeds  # noqa: E402
from environment.custom_env import load_config  # noqa: E402
from training.common import PROJECT_ROOT, make_network, scorecard  # noqa: E402

MODEL_PATH = PROJECT_ROOT / "models" / "pg" / "pension5_seed0_best.pt"

REFERENCE_PATH = PROJECT_ROOT / "logs" / "determinism_reference.json"

CHECK_GAMES = 100

RANDOM_PLAY_GAMES = 50

RANDOM_PLAY_SEED = 12345

HIDDEN_SIZE = 128

TOLERANCE = 1e-9


def random_play_fingerprint(config: MarketConfig) -> RandomPlayFingerprint:
    env = ThinBookPensionEnv(config)

    action_generator = np.random.default_rng(RANDOM_PLAY_SEED)

    total_reward = 0.0

    observation_sum = 0.0

    total_cost = 0.0

    for seed in range(RANDOM_PLAY_GAMES):
        observation, info = env.reset(seed=seed)

        finished = False

        while not finished:
            action = int(action_generator.integers(len(env.action_names)))

            observation, reward, finished, _, info = env.step(action)

            total_reward = total_reward + reward

            observation_sum = observation_sum + float(observation.sum())

        total_cost = total_cost + info["cost_bps"]

    fingerprint: RandomPlayFingerprint = {"total_reward": total_reward, "observation_sum": observation_sum, "total_cost_bps": total_cost}

    return fingerprint


def measure() -> DeterminismReference:
    config = load_config()

    threshold = config["won_cost_bps"]

    seeds = evaluation_seeds(CHECK_GAMES)

    network = make_network(len(ThinBookPensionEnv(config).action_names), HIDDEN_SIZE)

    network.load_state_dict(torch.load(MODEL_PATH))

    measurements: DeterminismReference = {
        "random_play": random_play_fingerprint(config),
        "ppo_model": scorecard(evaluate(TorchPolicy(network), config, seeds), threshold),
        "block_dealer": scorecard(evaluate(BlockDealerPolicy(config), config, seeds), threshold),
        "perfect_foresight_planner": scorecard(evaluate(PerfectForesightPlanner(config), config, seeds), threshold),
    }

    return measurements


def check_number(group: str, key: str, value: float, expected: float) -> bool:
    matches = abs(value - expected) <= TOLERANCE

    print(f"{group:<28}{key:<26}{value:>18.6f}  reference {expected:>18.6f}  {'MATCH' if matches else 'DIFFERENT'}")

    return matches


def check_scorecard(group: str, card: Scorecard, saved: Scorecard) -> bool:
    results = [
        check_number(group, "games", card["games"], saved["games"]),

        check_number(group, "win_rate", card["win_rate"], saved["win_rate"]),

        check_number(group, "mean_points", card["mean_points"], saved["mean_points"]),

        check_number(group, "mean_cost_bps", card["mean_cost_bps"], saved["mean_cost_bps"]),

        check_number(group, "forced_sale_rate", card["forced_sale_rate"], saved["forced_sale_rate"]),

        check_number(group, "invalid_actions_per_game", card["invalid_actions_per_game"], saved["invalid_actions_per_game"]),
    ]

    return all(results)


def check_fingerprint(group: str, fingerprint: RandomPlayFingerprint, saved: RandomPlayFingerprint) -> bool:
    results = [
        check_number(group, "total_reward", fingerprint["total_reward"], saved["total_reward"]),

        check_number(group, "observation_sum", fingerprint["observation_sum"], saved["observation_sum"]),

        check_number(group, "total_cost_bps", fingerprint["total_cost_bps"], saved["total_cost_bps"]),
    ]

    return all(results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check that results are unchanged after a code rewrite.")

    parser.add_argument("--save", action="store_true", help="record the current numbers as the reference")

    parser.add_argument("--note", default="", help="with --save: why the reference was (re)saved")

    arguments = parser.parse_args()

    measurements = measure()

    if arguments.save:
        REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)

        reference_to_save: DeterminismReference = {
            "note": arguments.note,
            "ppo_model": measurements["ppo_model"],
            "random_play": measurements["random_play"],
            "block_dealer": measurements["block_dealer"],
            "perfect_foresight_planner": measurements["perfect_foresight_planner"],
        }

        REFERENCE_PATH.write_text(json.dumps(reference_to_save, indent=2), encoding="utf-8")

        print(f"Saved reference to {REFERENCE_PATH}")

    reference: DeterminismReference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))

    ppo_matches = check_scorecard("ppo_model", measurements["ppo_model"], reference["ppo_model"])

    random_play_matches = check_fingerprint("random_play", measurements["random_play"], reference["random_play"])

    block_dealer_matches = check_scorecard("block_dealer", measurements["block_dealer"], reference["block_dealer"])

    planner_matches = check_scorecard("perfect_foresight_planner", measurements["perfect_foresight_planner"], reference["perfect_foresight_planner"])

    all_match = ppo_matches and random_play_matches and block_dealer_matches and planner_matches

    print("\nALL MATCH: nothing changed." if all_match else "\nSOMETHING CHANGED: check the DIFFERENT lines.")


if __name__ == "__main__":
    main()
