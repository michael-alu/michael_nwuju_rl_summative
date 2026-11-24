"""
Small shared helpers for the baseline policies and the perfect-foresight planner.

1. read_step_info: returns the info dict from env.reset() and env.step() as a typed StepInfo.

2. Payout arithmetic: what's payable by a day, the cash deficit, the small-cap expected share.

3. planned_cash_action: plans cash backwards from all known due dates with the actual slices.
"""

import math
from typing import Any, cast

from custom_types.market_config import MarketConfig
from custom_types.payout import Payout
from custom_types.step_info import StepInfo
from environment.custom_env import SELL_BANK_SHARES, SELL_TBILLS, WAIT

CASH_SAFETY_DAYS = 1

LIMIT_MARGIN = 0.02


def read_step_info(info: dict[str, Any]) -> StepInfo:
    return cast(StepInfo, info)


def due_day_of(payout: Payout) -> int:
    return payout["due_day"]


def next_day(info: StepInfo) -> int:
    return info["day"] + 1


def due_by(info: StepInfo, last_day: int) -> float:
    total = 0.0

    for payout in info["known_payouts"]:
        if payout["due_day"] <= last_day:
            total = total + payout["amount"]

    return total


def cash_shortfall(info: StepInfo, lookahead_days: int) -> float:
    return due_by(info, next_day(info) + lookahead_days - 1) - info["cash_naira"] - info["settling_naira"]


def due_today_shortfall(info: StepInfo) -> float:
    return due_by(info, next_day(info)) - info["cash_naira"] - info["settling_naira"]


def projected_small_caps_share(info: StepInfo) -> float:
    known_total = 0.0

    for payout in info["known_payouts"]:
        known_total = known_total + payout["amount"]

    value_after = info["book_value_naira"] - known_total

    return info["small_caps_naira_book"] / max(value_after, 1.0)


# Walk the payouts in due-date order and start selling
# (banks first, since they take a day to settle, then T-bills)
# as soon as the sales still needed would no longer fit in the days left.
def planned_cash_action(today: int, dues: list[tuple[int, float]], available: float, tbills: float, banks: float, buffer: float, config: MarketConfig) -> int:
    fund = config["starting_fund_naira"]

    tbill_sale = config["tbill_slice"] * fund

    banks_sale = config["banks_slice"] * fund

    owed_so_far = 0.0

    for due_day, amount in sorted(dues):
        owed_so_far = owed_so_far + amount

        shortfall = owed_so_far + buffer - available

        if shortfall <= 0:
            continue

        days_left = due_day - today

        tbill_actions = math.ceil(min(shortfall, tbills) / tbill_sale) if tbills > 0 else 0

        banks_actions = math.ceil(max(shortfall - tbills, 0.0) / banks_sale)

        actions_needed = tbill_actions + banks_actions

        must_start = days_left <= actions_needed + CASH_SAFETY_DAYS

        if not must_start:
            continue

        banks_still_settle = days_left >= 1

        if banks_actions > 0 and banks_still_settle and banks > 0:
            return SELL_BANK_SHARES

        if tbills > 0:
            return SELL_TBILLS

        if banks_still_settle and banks > 0:
            return SELL_BANK_SHARES

    if buffer > 0 and available < buffer:
        if banks > 0:
            return SELL_BANK_SHARES

        if tbills > 0:
            return SELL_TBILLS

    return WAIT


def known_dues(info: StepInfo) -> list[tuple[int, float]]:
    dues: list[tuple[int, float]] = []

    for payout in info["known_payouts"]:
        dues.append((payout["due_day"], payout["amount"]))

    return dues


def ladder_cash_action(info: StepInfo, config: MarketConfig, buffer: float = 0.0) -> int:
    available = info["cash_naira"] + info["settling_naira"]

    return planned_cash_action(next_day(info), known_dues(info), available, info["tbills_naira"], info["banks_naira"], buffer, config)
