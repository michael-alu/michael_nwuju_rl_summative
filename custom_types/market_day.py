"""
One simulated market day, drawn at reset.
"""

from typing import TypedDict


class MarketDay(TypedDict):
    stormy: bool

    drought: bool

    banks_move: float

    small_caps_move: float

    small_caps_volume: float

    banks_daily_value: float

    big_buyer_offered: bool
