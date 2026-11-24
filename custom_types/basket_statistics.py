"""
Beta to the ASI and daily idiosyncratic volatility of an equal-weight basket.
"""

from typing import NotRequired, TypedDict


class BasketStatistics(TypedDict):
    members: int

    symbols: NotRequired[list[str]]

    weighting: str

    beta_to_asi: float

    daily_idiosyncratic_volatility: float

    measured_on: str
