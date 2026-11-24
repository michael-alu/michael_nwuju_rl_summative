"""
Totals from random play on fixed seeds; any change to the game's rules changes them.
"""

from typing import TypedDict


class RandomPlayFingerprint(TypedDict):
    total_reward: float

    observation_sum: float

    total_cost_bps: float
