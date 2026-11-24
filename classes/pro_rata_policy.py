"""Pro-rata baseline: raise cash by selling every asset in proportion to its weight."""


import numpy as np

from custom_types.raised_so_far import RaisedSoFar
from custom_types.step_info import StepInfo
from environment.custom_env import SELL_BANK_SHARES, SELL_SMALL_CAP_SHARES, SELL_TBILLS, WAIT
from classes.thin_book_pension_env import ThinBookPensionEnv
from environment.policy_helpers import cash_shortfall, due_today_shortfall, ladder_cash_action
from custom_types.market_config import MarketConfig


class ProRataPolicy:
    name = "pro_rata"

    def __init__(self, config: MarketConfig) -> None:
        self.config = config

    def reset(self, env: ThinBookPensionEnv) -> None:
        self.raised: RaisedSoFar = {"tbills": 0.0, "banks": 0.0, "small_caps": 0.0}

    def act(self, observation: np.ndarray, info: StepInfo) -> int:
        timing_action = ladder_cash_action(info, self.config)

        shortfall = cash_shortfall(info, self.config["horizon_days"])

        if timing_action == WAIT or shortfall <= 0:
            if shortfall <= 0:
                self.raised = {"tbills": 0.0, "banks": 0.0, "small_caps": 0.0}

            return WAIT

        if timing_action == SELL_TBILLS and due_today_shortfall(info) > 0:
            return SELL_TBILLS

        weights = info["weights"]

        stock_and_bills = weights["tbills"] + weights["banks"] + weights["small_caps"]

        owed = {
            "tbills": shortfall * weights["tbills"] / stock_and_bills - self.raised["tbills"],

            "banks": shortfall * weights["banks"] / stock_and_bills - self.raised["banks"],

            "small_caps": shortfall * weights["small_caps"] / stock_and_bills - self.raised["small_caps"],
        }

        asset = "tbills"

        for name in owed:
            if owed[name] > owed[asset]:
                asset = name

        fund = self.config["starting_fund_naira"]

        if asset == "tbills" and info["tbills_naira"] > 0:
            self.raised["tbills"] = self.raised["tbills"] + self.config["tbill_slice"] * fund

            return SELL_TBILLS

        if asset == "small_caps":
            self.raised["small_caps"] = self.raised["small_caps"] + self.config["small_caps_slice"] * fund

            return SELL_SMALL_CAP_SHARES

        self.raised["banks"] = self.raised["banks"] + self.config["banks_slice"] * fund

        return SELL_BANK_SHARES
