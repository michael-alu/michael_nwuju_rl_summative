"""
Calm and stormy months of the NGX All Share Index.
"""

from typing import TypedDict


class MarketStatistics(TypedDict):
    asi_daily_volatility_calm: float

    asi_daily_volatility_stormy: float

    stormy_volatility_multiplier: float

    stormy_month_share: float

    mean_stormy_spell_months: float

    mean_calm_spell_months: float

    calm_to_stormy_daily: float

    stormy_to_calm_daily: float
