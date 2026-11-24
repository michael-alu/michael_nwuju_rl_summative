"""
The fixed facts about one game that the browser needs before day 1 (limits, fund size, who is playing).
"""

from typing import TypedDict


class GameMeta(TypedDict):
    player: str

    player_label: str

    seed: int

    market: str

    horizon_days: int

    fund_naira: float

    won_cost_bps: float

    small_caps_max_share: float

    banks_min_share: float

    banks_max_share: float

    breach_grace_days: int

    small_caps_median_volume: float

    board_minimum_shares: float
