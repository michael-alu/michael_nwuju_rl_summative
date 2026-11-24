"""
One full game, day by day, as returned by POST /episode so another app can replay it.
"""

from typing import TypedDict

from custom_types.day_message import DayMessage
from custom_types.game_meta import GameMeta


class EpisodeLog(TypedDict):
    meta: GameMeta

    days: list[DayMessage]

    outcome: str

    outcome_text: str

    total_points: float

    cost_bps: float

    forced_sales: int

    invalid_actions: int
