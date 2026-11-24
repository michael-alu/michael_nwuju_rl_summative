"""Volume-aware trimmer baseline: sells small caps only after a busy day (volume at or above
normal) while the fund is projected over its small-cap limit, takes the big buyer when it
helps, keeps cash ready for known payouts from T-bills and banks."""


import numpy as np

from custom_types.step_info import StepInfo
from environment.custom_env import CALL_BIG_BUYER, SELL_SMALL_CAP_SHARES, WAIT
from classes.thin_book_pension_env import ThinBookPensionEnv
from environment.policy_helpers import LIMIT_MARGIN, ladder_cash_action, projected_small_caps_share
from custom_types.market_config import MarketConfig

VOLUME_AWARE_BUFFER = 0.05


class VolumeAwareTrimmerPolicy:
    name = "volume_aware_trimmer"

    def __init__(self, config: MarketConfig) -> None:
        self.config = config

    def reset(self, env: ThinBookPensionEnv) -> None:
        pass

    def act(self, observation: np.ndarray, info: StepInfo) -> int:
        config = self.config

        buffer = VOLUME_AWARE_BUFFER * config["starting_fund_naira"]

        cash_action = ladder_cash_action(info, config, buffer=buffer)

        if cash_action != WAIT:
            return cash_action

        projected = projected_small_caps_share(info)

        over_limit_ahead = projected > config["small_caps_max_share"] - LIMIT_MARGIN

        if over_limit_ahead and info["big_buyer_offered_today"] and (info["in_breach"] or projected > config["small_caps_max_share"] + 0.05):
            return CALL_BIG_BUYER

        busy_yesterday = info["small_caps_volume_yesterday"] >= config["small_caps_median_volume"]

        if over_limit_ahead and busy_yesterday:
            return SELL_SMALL_CAP_SHARES

        if info["in_breach"] and info["grace_days_left"] <= 3 and info["small_caps_volume_yesterday"] > 0:
            return SELL_SMALL_CAP_SHARES

        return WAIT
