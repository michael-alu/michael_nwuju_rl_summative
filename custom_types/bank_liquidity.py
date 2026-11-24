"""
Median daily traded value of the bank used as the liquidity floor.
"""

from typing import TypedDict


class BankLiquidity(TypedDict):
    symbol: str

    median_daily_value_naira: float
