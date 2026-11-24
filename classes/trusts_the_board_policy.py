"""Trusts-the-board baseline: believes the steady board price means small caps are easy to
sell, so it waits until the breach grace is almost over and then sells them hard."""


import numpy as np

from custom_types.step_info import StepInfo
from environment.custom_env import SELL_SMALL_CAP_SHARES, WAIT
from classes.thin_book_pension_env import ThinBookPensionEnv
from environment.policy_helpers import ladder_cash_action, next_day, projected_small_caps_share
from custom_types.market_config import MarketConfig

TRUSTING_GRACE_DAYS = 2


class TrustsTheBoardPolicy:
    name = "trusts_the_board"

    def __init__(self, config: MarketConfig) -> None:
        self.config = config

    def reset(self, env: ThinBookPensionEnv) -> None:
        pass

    def act(self, observation: np.ndarray, info: StepInfo) -> int:
        cash_action = ladder_cash_action(info, self.config)

        if cash_action != WAIT:
            return cash_action

        late_in_grace = info["in_breach"] and info["grace_days_left"] <= TRUSTING_GRACE_DAYS

        last_days = next_day(info) >= self.config["horizon_days"] - TRUSTING_GRACE_DAYS

        if (late_in_grace or last_days) and projected_small_caps_share(info) > self.config["small_caps_max_share"]:
            return SELL_SMALL_CAP_SHARES

        return WAIT
