"""
Shared pieces for every ThinBook Pension trainer (PPO, A2C, REINFORCE, DQN).

1. make_training_env: the frozen env wrapped for TorchRL, with a training-only reward scale
   and the per-episode outcome fields copied out of the info dict.
2. make_network: the two-hidden-layer network used for policies, values and Q-values.
3. scorecard: the five numbers every summary and table reports.
4. score_network and held_out_scorecard: score a network on validation or held-out seeds.
TorchPolicy and EpisodeLogger live in classes/.
"""

from pathlib import Path

import numpy as np
import torch
from torch import nn
from torchrl.envs import GymWrapper, RewardScaling, RewardSum, StepCounter, TransformedEnv
from torchrl.envs.gym_like import default_info_dict_reader

from classes import ThinBookPensionEnv, TorchPolicy
from custom_types import GameResult, MarketConfig, Scorecard
from environment.baselines import evaluate, evaluation_seeds, win_rate
from environment.custom_env import OBSERVATION_NAMES

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEVICE = torch.device("cpu")

VALIDATION_SEED_START = 200_000

VALIDATION_GAMES = 200

HELD_OUT_GAMES = 500

EPISODE_INFO_KEYS = ["cost_bps", "forced_event_count", "invalid_actions", "won_flag"]


def make_training_env(seed: int, reward_scale: float, config: MarketConfig) -> TransformedEnv:
    wrapped_env = GymWrapper(ThinBookPensionEnv(config), categorical_action_encoding=True, device=DEVICE)

    wrapped_env.set_info_dict_reader(default_info_dict_reader(EPISODE_INFO_KEYS))

    training_env = TransformedEnv(wrapped_env)

    training_env.append_transform(StepCounter())

    training_env.append_transform(RewardSum())

    training_env.append_transform(RewardScaling(loc=0.0, scale=reward_scale))

    training_env.set_seed(seed)

    return training_env


def make_network(output_size: int, hidden_size: int) -> nn.Sequential:
    network = nn.Sequential(
        nn.Linear(len(OBSERVATION_NAMES), hidden_size),

        nn.Tanh(),

        nn.Linear(hidden_size, hidden_size),

        nn.Tanh(),

        nn.Linear(hidden_size, output_size),
    )

    return network


def scorecard(results: list[GameResult], threshold: float) -> Scorecard:
    points: list[float] = []

    costs: list[float] = []

    forced_sales: list[bool] = []

    invalid_actions: list[int] = []

    for result in results:
        points.append(result["total_points"])

        costs.append(result["cost_bps"])

        forced_sales.append(result["forced"])

        invalid_actions.append(result["invalid_actions"])

    card: Scorecard = {
        "games": len(results),
        "mean_points": float(np.mean(points)),
        "mean_cost_bps": float(np.mean(costs)),
        "win_rate": win_rate(results, threshold),
        "forced_sale_rate": float(np.mean(forced_sales)),
        "invalid_actions_per_game": float(np.mean(invalid_actions)),
    }

    return card


def validation_seeds() -> list[int]:
    return list(range(VALIDATION_SEED_START, VALIDATION_SEED_START + VALIDATION_GAMES))


def score_network(network: nn.Module, config: MarketConfig, seeds: list[int]) -> Scorecard:
    results = evaluate(TorchPolicy(network), config, seeds)

    return scorecard(results, config["won_cost_bps"])


def is_better(card: Scorecard, best_card: Scorecard | None) -> bool:
    if best_card is None:
        return True

    if card["win_rate"] != best_card["win_rate"]:
        return card["win_rate"] > best_card["win_rate"]

    return card["mean_points"] > best_card["mean_points"]


def held_out_scorecard(network: nn.Module, model_path: Path, config: MarketConfig) -> Scorecard:
    network.load_state_dict(torch.load(model_path))

    return score_network(network, config, evaluation_seeds(HELD_OUT_GAMES))


