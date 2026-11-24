"""
The rules calibrate.py used, written next to its numbers.
"""

from typing import TypedDict


class CalibrationRules(TypedDict):
    board_minimum_shares: int

    small_caps: str

    drought_month: str

    stormy_month: str

    switch_probability: str
