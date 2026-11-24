"""
How much small-cap volume persists from one day to the next.
"""

from typing import TypedDict


class VolumePersistence(TypedDict):
    stocks: int

    zero_after_zero_median: float

    window: str

    zero_after_traded_median: float

    log_volume_lag1_autocorrelation_median: float

    method: str

    log_volume_lag1_autocorrelation_quartiles: list[float]
