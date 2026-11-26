"""
Measure how greedy the best DQN model is: how far apart its estimates for the best and second-best
moves are, and how often it calls a big buyer when none is offering.

1. Load the best DQN run (environment/model_registry.py) and play it on the 500 held-out games.

2. Every day, read the Q-values it acts on and record the gap between the highest and the second highest
(in points: 1 point = ₦10,000).

3. Print the median gap, the share of days the gap is under 0.05 and 0.01 points, and the number of calls
to a big buyer who was not offering, and save the same lines to logs/history/19_dqn_value_gaps.txt.

Run from the project root: uv run python scripts/dqn_value_gaps.py
"""

import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classes import ThinBookPensionEnv  # noqa: E402
from environment.baselines import evaluation_seeds  # noqa: E402
from environment.custom_env import ACTION_NAMES, CALL_BIG_BUYER, load_config  # noqa: E402
from environment.model_registry import agent_entry, load_network  # noqa: E402
from environment.policy_helpers import read_step_info  # noqa: E402
from training.common import PROJECT_ROOT  # noqa: E402

OUTPUT = PROJECT_ROOT / "logs" / "history" / "19_dqn_value_gaps.txt"

NEAR_TIE_POINTS = 0.05

TIE_POINTS = 0.01


def top_two_gap(values: np.ndarray) -> float:
    ordered = np.sort(values)

    return float(ordered[-1] - ordered[-2])


def main() -> None:
    torch.set_num_threads(1)

    entry = agent_entry("dqn")

    network = load_network(entry)

    config = load_config()

    env = ThinBookPensionEnv(config)

    gaps: list[float] = []

    call_gaps: list[float] = []

    calls_without_buyer = 0

    games = 0

    for seed in evaluation_seeds():
        observation, raw_info = env.reset(seed=seed)

        info = read_step_info(raw_info)

        finished = False

        while not finished:
            with torch.no_grad():
                values = network(torch.as_tensor(observation, dtype=torch.float32)).numpy()

            gap = top_two_gap(values)

            gaps.append(gap)

            action = int(np.argmax(values))

            if action == CALL_BIG_BUYER and not info["big_buyer_offered_today"]:
                calls_without_buyer = calls_without_buyer + 1

                call_gaps.append(gap)

            observation, _, finished, _, raw_info = env.step(action)

            info = read_step_info(raw_info)

        games = games + 1

    all_gaps = np.array(gaps)

    lines = [
        f"Best DQN run: {entry['run_name']}, {games} held-out games, {len(gaps)} days, actions {', '.join(ACTION_NAMES)}",
        f"Median gap between the best and second-best move: {float(np.median(all_gaps)):.4f} points",
        f"Days with a gap under {NEAR_TIE_POINTS} points (₦{NEAR_TIE_POINTS * 10_000:.0f}): {float(np.mean(all_gaps < NEAR_TIE_POINTS)):.1%}",
        f"Days with a gap under {TIE_POINTS} points (₦{TIE_POINTS * 10_000:.0f}): {float(np.mean(all_gaps < TIE_POINTS)):.1%}",
        f"Calls to a big buyer who was not offering: {calls_without_buyer} ({calls_without_buyer / games:.1f} a game), median gap on those days {float(np.median(call_gaps)):.4f} points",
    ]

    for line in lines:
        print(line)

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUTPUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
