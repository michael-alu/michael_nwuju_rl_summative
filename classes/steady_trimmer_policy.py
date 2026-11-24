"""Steady trimmer baseline: from day 1 sells small caps every few days, paced to the expected
limit need; payouts from T-bills, then banks."""


import numpy as np

from custom_types.step_info import StepInfo
from environment.custom_env import SELL_SMALL_CAP_SHARES, WAIT
from classes.thin_book_pension_env import ThinBookPensionEnv
from environment.policy_helpers import ladder_cash_action, next_day
from custom_types.market_config import MarketConfig


class SteadyTrimmerPolicy:
    name = "steady_trimmer"

    def __init__(self, config: MarketConfig) -> None:
        self.config = config

        expected_payouts = (self.config["payouts_total_min"] + self.config["payouts_total_max"]) / 2

        expected_need = self.config["start_small_caps"] - self.config["small_caps_max_share"] * (1 - expected_payouts)

        daily_need = max(expected_need, 0.0) / self.config["horizon_days"]

        self.trim_every = max(int(round(self.config["small_caps_slice"] / max(daily_need, 1e-9))), 1)

    def reset(self, env: ThinBookPensionEnv) -> None:
        pass

    def act(self, observation: np.ndarray, info: StepInfo) -> int:
        cash_action = ladder_cash_action(info, self.config)

        if cash_action != WAIT:
            return cash_action

        trim_day = next_day(info) % self.trim_every == 0

        if trim_day and info["small_caps_naira_board"] > 0:
            return SELL_SMALL_CAP_SHARES

        return WAIT
