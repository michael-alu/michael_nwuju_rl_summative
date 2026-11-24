"""
Play, score and analyze the baselines and the perfect-foresight planner for ThinBook Pension.

Each policy has its own file in classes/ (e.g. classes/block_dealer_policy.py).

1. simple_baselines: the 7 simple baselines for a config.

2. play and evaluate: play one game or many seeds and return the outcome.

3. win_rate and print_table: what the tables tell you.

Run from the project root: uv run python -m environment.baselines
"""


import numpy as np

from classes.block_dealer_policy import BlockDealerPolicy
from custom_types.game_result import GameResult
from classes.liquidity_ladder_policy import LiquidityLadderPolicy
from classes.perfect_foresight_planner import PerfectForesightPlanner
from classes.policy import Policy
from classes.pro_rata_policy import ProRataPolicy
from classes.random_policy import RandomPolicy
from classes.steady_trimmer_policy import SteadyTrimmerPolicy
from classes.trusts_the_board_policy import TrustsTheBoardPolicy
from classes.volume_aware_trimmer_policy import VolumeAwareTrimmerPolicy
from environment.custom_env import load_config, load_hard_config
from classes import ThinBookPensionEnv
from environment.policy_helpers import read_step_info
from custom_types.market_config import MarketConfig

EVALUATION_SEED_START = 100_000

EVALUATION_EPISODES = 500


def simple_baselines(config: MarketConfig) -> list[Policy]:
    policies: list[Policy] = [
        RandomPolicy(),
        ProRataPolicy(config),
        BlockDealerPolicy(config),
        SteadyTrimmerPolicy(config),
        TrustsTheBoardPolicy(config),
        LiquidityLadderPolicy(config),
        VolumeAwareTrimmerPolicy(config),
    ]

    return policies


def play(env: ThinBookPensionEnv, policy: Policy, seed: int) -> GameResult:
    observation, raw_info = env.reset(seed=seed)

    info = read_step_info(raw_info)

    policy.reset(env)

    finished = False

    while not finished:
        observation, _, finished, _, raw_info = env.step(policy.act(observation, info))

        info = read_step_info(raw_info)

    result: GameResult = {
        "seed": seed,
        "cost_bps": info["cost_bps"],
        "total_points": info["total_points"],
        "forced": len(info["forced_events"]) > 0,
        "invalid_actions": info["invalid_actions"],
        "forced_events": len(info["forced_events"]),
    }

    return result


def evaluate(policy: Policy, config: MarketConfig, seeds: list[int]) -> list[GameResult]:
    env = ThinBookPensionEnv(config)

    results: list[GameResult] = []

    for seed in seeds:
        results.append(play(env, policy, seed))

    return results


def evaluation_seeds(count: int = EVALUATION_EPISODES) -> list[int]:
    return list(range(EVALUATION_SEED_START, EVALUATION_SEED_START + count))


def win_rate(results: list[GameResult], threshold_bps: float) -> float:
    if not results:
        return float("nan")

    wins: list[bool] = []

    for result in results:
        won = not result["forced"] and (result["cost_bps"] < threshold_bps)

        wins.append(won)

    return float(np.mean(wins))


def print_table(title: str, results_by_policy: dict[str, list[GameResult]], threshold_bps: float) -> None:
    print(f"\n{title} (Won = no forced sale and cost below {threshold_bps:.0f} bps)")

    print(f"{'policy':<28}{'won':>7}{'mean points':>13}{'cost bps':>10}{'forced sale':>13}{'invalid/game':>14}")

    for name, results in results_by_policy.items():
        points: list[float] = []

        costs: list[float] = []

        forced_sales: list[bool] = []

        invalid_actions: list[int] = []

        for result in results:
            costs.append(result["cost_bps"])

            forced_sales.append(result["forced"])

            points.append(result["total_points"])

            invalid_actions.append(result["invalid_actions"])

        print(
            f"{name:<28}{win_rate(results, threshold_bps):>7.1%}{np.mean(points):>13.1f}"
            f"{np.mean(costs):>10.1f}{np.mean(forced_sales):>13.1%}"
            f"{np.mean(invalid_actions):>14.1f}"
        )


def main() -> None:
    seeds = evaluation_seeds()

    for label, config in [("Normal market", load_config()), ("Hard market", load_hard_config())]:
        policies = simple_baselines(config) + [PerfectForesightPlanner(config)]

        results: dict[str, list[GameResult]] = {}

        for policy in policies:
            results[policy.name] = evaluate(policy, config, seeds)

        print_table(f"{label}, {len(seeds)} held-out seeds", results, config["won_cost_bps"])


if __name__ == "__main__":
    main()
