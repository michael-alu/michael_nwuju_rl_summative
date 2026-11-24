"""
Checks that ThinBook Pension behaves the way the docs say.

Run from the project root: uv run pytest
"""

import copy
import math

import numpy as np
from gymnasium.utils.env_checker import check_env

from classes import ThinBookPensionEnv
from custom_types import StepInfo
from environment.custom_env import ACTION_NAMES, SELL_BANK_SHARES, SELL_SMALL_CAP_SHARES, SELL_TBILLS, WAIT
from environment.policy_helpers import read_step_info

TEST_SEED = 11

GAMES = 40

STATE_DAY = 15


def random_actions(seed: int, count: int = 60) -> list[int]:
    random_generator = np.random.default_rng(seed)

    actions: list[int] = []

    for action in random_generator.integers(len(ACTION_NAMES), size=count):
        actions.append(int(action))

    return actions


def play(env: ThinBookPensionEnv, seed: int, actions: list[int]) -> list[tuple[np.ndarray, float, StepInfo]]:
    observation, raw_info = env.reset(seed=seed)

    steps = [(observation, 0.0, read_step_info(raw_info))]

    for action in actions:
        observation, reward, terminated, _, raw_info = env.step(action)

        steps.append((observation, reward, read_step_info(raw_info)))

        if terminated:
            break

    return steps


def env_mid_game() -> ThinBookPensionEnv:
    env = ThinBookPensionEnv()

    env.reset(seed=TEST_SEED)

    for _ in range(STATE_DAY):
        env.step(WAIT)

    return env


def test_frozen_game_uses_five_actions() -> None:
    env = ThinBookPensionEnv()

    assert env.action_names == ACTION_NAMES

    assert len(env.action_names) == 5


def test_volume_observations_are_log_scaled_and_clipped() -> None:
    env = env_mid_game()

    observation = env._observation()

    expected = min(math.log1p(env.volume_history[-1] / env.config["small_caps_median_volume"]) / math.log1p(env.config["volume_ratio_cap"]), 1.0)

    assert abs(observation[11] - expected) < 1e-6

    env.volume_history[-1] = env.config["small_caps_median_volume"] * 1e6

    assert env._observation()[11] == 1.0


def test_gymnasium_env_checker_passes() -> None:
    check_env(ThinBookPensionEnv(), skip_render_check=True)


def test_same_seed_gives_same_game() -> None:
    first_game = play(ThinBookPensionEnv(), TEST_SEED, random_actions(TEST_SEED))

    second_game = play(ThinBookPensionEnv(), TEST_SEED, random_actions(TEST_SEED))

    for (first_observation, first_reward, _), (second_observation, second_reward, _) in zip(first_game, second_game):
        assert np.array_equal(first_observation, second_observation)

        assert first_reward == second_reward


def test_observations_in_bounds_and_rewards_finite() -> None:
    env = ThinBookPensionEnv()

    for seed in range(GAMES):
        for observation, reward, _ in play(env, seed, random_actions(seed)):
            assert env.observation_space.contains(observation)

            assert math.isfinite(reward)


def test_every_action_is_reachable() -> None:
    env = ThinBookPensionEnv()

    executed: set[int] = set()

    for seed in range(GAMES * 3):
        for _, _, info in play(env, seed, random_actions(seed))[1:]:
            agent_traded = False

            for trade in info["trades"]:
                if trade["reason"] in ("agent", "big buyer"):
                    agent_traded = True

            if not info["invalid_action"] and (agent_traded or info["action_name"] == "Wait"):
                executed.add(ACTION_NAMES.index(info["action_name"]))

    assert executed == set(range(len(ACTION_NAMES)))


def test_invalid_action_acts_as_wait_costs_a_point_and_is_counted() -> None:
    wait_env = ThinBookPensionEnv()

    invalid_env = ThinBookPensionEnv()

    wait_env.reset(seed=TEST_SEED)

    invalid_env.reset(seed=TEST_SEED)

    invalid_env.tbills = 0.0

    wait_env.tbills = 0.0

    wait_observation, wait_reward, _, _, _ = wait_env.step(WAIT)

    invalid_observation, invalid_reward, _, _, info = invalid_env.step(SELL_TBILLS)

    assert info["invalid_action"]

    assert info["invalid_actions"] == 1

    assert np.array_equal(wait_observation, invalid_observation)

    assert abs(invalid_reward - (wait_reward - invalid_env.config["invalid_action_penalty"])) < 1e-9


def test_observation_does_not_leak_hidden_state() -> None:
    env = env_mid_game()

    changed_env = copy.deepcopy(env)

    changed_env.small_caps_fair = changed_env.small_caps_fair * 1.5

    changed_env.small_caps_impact = changed_env.small_caps_impact - 0.3

    for day in changed_env.market:
        day["stormy"] = not day["stormy"]

        day["drought"] = not day["drought"]

    for payout in changed_env.payouts:
        if payout["arrival_day"] > env.day + 1:
            payout["amount"] = payout["amount"] * 3

    assert np.array_equal(env._observation(), changed_env._observation())


def test_market_direction_does_not_change_the_score() -> None:
    env = env_mid_game()

    richer_env = copy.deepcopy(env)

    richer_env.banks_price = richer_env.banks_price * 2

    richer_env.banks_shares = richer_env.banks_shares / 2

    env.cash = 0.0

    richer_env.cash = 0.0

    env._sell_banks(1_000_000, "agent", discount=0.0, settle_now=False)

    richer_env._sell_banks(1_000_000, "agent", discount=0.0, settle_now=False)

    assert abs(env.cost_naira - richer_env.cost_naira) < 1e-6

    waiting_env = ThinBookPensionEnv()

    waiting_env.reset(seed=TEST_SEED)

    waiting_env.payouts = []

    for _ in range(waiting_env.config["horizon_days"]):
        waiting_env.step(WAIT)

    assert waiting_env.cost_naira == 0.0


def test_tbill_sale_costs_only_its_fee() -> None:
    env = env_mid_game()

    env._sell_tbills(500_000, "agent")

    assert abs(env.cost_naira - 500_000 * env.config["tbill_fee"]) < 1e-6


def test_every_payout_gets_paid() -> None:
    env = ThinBookPensionEnv()

    for seed in range(GAMES):
        env.reset(seed=seed)

        for action in random_actions(seed):
            env.step(action)

        total_payouts = 0.0

        for payout in env.payouts:
            assert payout["paid"]

            total_payouts = total_payouts + payout["amount"]

        assert abs(env.paid_out - total_payouts) < 1.0


def test_limits_hold_at_the_end_and_forced_sales_lose() -> None:
    env = ThinBookPensionEnv()

    config = env.config

    for seed in range(GAMES):
        steps = play(env, seed, [WAIT] * config["horizon_days"])

        info = steps[-1][2]

        weights = env.weights()

        assert weights["small_caps"] <= config["small_caps_max_share"] + 1e-6

        assert weights["banks"] <= config["banks_max_share"] + 1e-6

        if info["forced_events"]:
            assert info["outcome"] == "lost"

            assert info["outcome_reason"] == "forced sale"


def test_small_cap_sales_respect_the_volume_cap() -> None:
    env = ThinBookPensionEnv()

    for seed in range(GAMES):
        env.reset(seed=seed)

        for _ in range(env.config["horizon_days"]):
            env.step(SELL_SMALL_CAP_SHARES)

            cap = env.config["participation_limit"] * env._today()["small_caps_volume"]

            assert env.small_caps_sold_today <= cap + 1e-6


def test_bank_sales_settle_next_day() -> None:
    env = env_mid_game()

    cash_before = env.cash

    env.step(SELL_BANK_SHARES)

    assert env.settling_cash > 0

    assert env.cash <= cash_before + 1e-6 or env.due_today() > 0
