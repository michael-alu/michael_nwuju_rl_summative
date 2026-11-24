"""Liquidity ladder baseline: raise cash from T-bills, then banks; small caps only when forced."""


import numpy as np

from custom_types.step_info import StepInfo
from classes.thin_book_pension_env import ThinBookPensionEnv
from environment.policy_helpers import ladder_cash_action
from custom_types.market_config import MarketConfig


class LiquidityLadderPolicy:
    name = "liquidity_ladder"

    def __init__(self, config: MarketConfig) -> None:
        self.config = config

    def reset(self, env: ThinBookPensionEnv) -> None:
        pass

    def act(self, observation: np.ndarray, info: StepInfo) -> int:
        return ladder_cash_action(info, self.config)
