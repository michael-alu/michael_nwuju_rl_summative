"""
Small-cap volume, zero-volume days and drought months.
"""

from typing import TypedDict


class SmallCapsLiquidity(TypedDict):
    stocks_used: int

    symbols: list[str]

    zero_volume_rate_median: float

    median_traded_volume_shares: float

    log_volume_sigma_median: float

    drought_month_share: float

    mean_drought_spell_months: float

    mean_normal_spell_months: float

    normal_to_drought_daily: float

    drought_to_normal_daily: float

    zero_volume_rate_normal_months_median: float

    zero_volume_rate_drought_months_median: float

    drought_volume_vs_normal_median: float
