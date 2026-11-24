"""
Everything the env reports after a day: the info dict of reset() and step().
"""

from typing import TypedDict

from custom_types.asset_weights import AssetWeights
from custom_types.payout import Payout
from custom_types.trade import Trade


class StepInfo(TypedDict):
    day: int

    action_name: str

    invalid_action: bool

    invalid_actions: int

    trades: list[Trade]

    weights: AssetWeights

    cash_naira: float

    settling_naira: float

    tbills_naira: float

    banks_naira: float

    small_caps_naira_board: float

    small_caps_shares: float

    observed_value_naira: float

    book_value_naira: float

    small_caps_naira_book: float

    banks_naira_book: float

    known_payouts: list[Payout]

    due_within_5_naira: float

    due_within_15_naira: float

    due_tomorrow_naira: float

    in_breach: bool

    grace_days_left: int

    small_caps_board_price: float

    small_caps_fair_price: float

    small_caps_real_price: float

    small_caps_days_since_board_move: int

    small_caps_volume_yesterday: float

    banks_price: float

    big_buyer_offered_today: bool

    stormy: bool

    drought: bool

    points_today: float

    total_points: float

    cost_bps: float

    fees_naira: float

    paid_out_naira: float

    forced_events: list[str]

    forced_event_count: int

    won_flag: float

    outcome: str

    outcome_reason: str
