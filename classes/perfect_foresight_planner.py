"""Perfect-foresight planner: an ANALYSIS TOOL for the report, not an agent. It reads the env's
hidden future (every payout, volume and big-buyer day) to show how much room for skill the
game has. It is never used in training."""

import math

import numpy as np

from custom_types.payout import Payout
from custom_types.step_info import StepInfo
from environment.custom_env import CALL_BIG_BUYER, SELL_BANK_SHARES, SELL_SMALL_CAP_SHARES, WAIT, WARM_UP_DAYS
from classes.thin_book_pension_env import ThinBookPensionEnv
from environment.policy_helpers import LIMIT_MARGIN, due_day_of, planned_cash_action
from custom_types.market_config import MarketConfig


class PerfectForesightPlanner:
    """ANALYSIS TOOL for the report, not an agent; never used in training.

    It reads the env's hidden future (every payout, every day's volume, big-buyer days) to
    measure how much room for skill the game leaves. It replans every day:
    1. Need: small-cap shares to sell so the fund ends inside its 35% limit after every payout.
    2. Deadline: the first day a future payout would push small caps over 35%, plus the 10-day
       grace (or day 60).
    3. Day selection: every small-cap sale is the same fixed slice, so the only choice is which
       days to sell on. Each day until the deadline can fill min(slice, 20% of its volume);
       impact per share grows with the square root of the fill's share of that volume, so days
       are ranked by that cost and the cheapest are picked until they cover the need. It sells
       today only if today was picked.
    4. Shortfall: if even every day until the deadline cannot cover the need, it takes the big
       buyer on an offer day.
    5. Cash: planned backward from every future due date with the real bank slice (cash from
       banks arrives T+1). Cash wins only when a due date forces it.
    """

    name = "perfect_foresight_planner"

    def __init__(self, config: MarketConfig) -> None:
        self.config = config

    def reset(self, env: ThinBookPensionEnv) -> None:
        self.env = env

    def _future_payouts(self) -> list[Payout]:
        future_payouts: list[Payout] = []

        for payout in self.env.payouts:
            if not payout["paid"] and payout["due_day"] > self.env.day:
                future_payouts.append(payout)

        return future_payouts

    def _deadline(self, small_caps_value: float) -> int:
        config = self.config

        value = self.env.book_value()

        deadline = config["horizon_days"]

        payouts_by_due_day = sorted(self._future_payouts(), key=due_day_of)

        for payout in payouts_by_due_day:
            value = value - payout["amount"]

            if small_caps_value / max(value, 1.0) > config["small_caps_max_share"]:
                deadline = min(payout["due_day"] + config["breach_grace_days"] - 1, config["horizon_days"])

                break

        return deadline

    def _future_payouts_total(self) -> float:
        total = 0.0

        for payout in self._future_payouts():
            total = total + payout["amount"]

        return total

    def _shares_to_sell(self) -> float:
        config = self.config

        env = self.env

        value_after = env.book_value() - self._future_payouts_total()

        allowed_value = config["small_caps_max_share"] * (1 - LIMIT_MARGIN) * value_after

        allowed_shares = allowed_value / env.reference_small_caps_price

        return max(env.small_caps_shares - allowed_shares, 0.0)

    def _small_caps_plan(self) -> tuple[bool, bool]:
        config = self.config

        env = self.env

        needed = self._shares_to_sell()

        if needed <= 0:
            return False, False

        today = env.day + 1

        deadline = max(self._deadline(env.small_caps_shares * env.reference_small_caps_price), today)

        slice_shares = config["small_caps_slice"] * config["starting_fund_naira"] / env.small_caps_fair

        options: list[tuple[float, int, float]] = []

        for day in range(today, deadline + 1):
            volume = env.market[WARM_UP_DAYS + day - 1]["small_caps_volume"]

            fill = min(slice_shares, config["participation_limit"] * volume)

            if fill <= 0:
                continue

            cost_per_share = config["small_caps_temporary_impact"] * math.sqrt(fill / volume)

            options.append((cost_per_share, day, fill))

        options.sort()

        covered = 0.0

        sell_today = False

        for _, day, fill in options:
            if covered >= needed:
                break

            covered = covered + fill

            if day == today:
                sell_today = True

        exchange_short = covered < needed

        return sell_today, exchange_short

    def act(self, observation: np.ndarray, info: StepInfo) -> int:
        config = self.config

        env = self.env

        dues: list[tuple[int, float]] = []

        for payout in self._future_payouts():
            dues.append((payout["due_day"], payout["amount"]))

        available = env.cash + env.settling_cash

        cash_action = planned_cash_action(env.day + 1, dues, available, env.tbills, env.banks_shares * env.banks_price, 0.0, config)

        sell_today, exchange_short = self._small_caps_plan()

        offered_today = env.market[WARM_UP_DAYS + env.day]["big_buyer_offered"]

        if cash_action != WAIT:
            return cash_action

        if exchange_short and offered_today:
            return CALL_BIG_BUYER

        if sell_today:
            return SELL_SMALL_CAP_SHARES

        value_after = env.book_value() - self._future_payouts_total()

        banks_heading_over = env.banks_shares * env.reference_banks_price / max(value_after, 1.0) > config["banks_max_share"] - LIMIT_MARGIN

        if banks_heading_over:
            return SELL_BANK_SHARES

        return WAIT
