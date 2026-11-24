"""The five numbers every summary and table reports, plus how many games were played."""

from typing import TypedDict


class Scorecard(TypedDict):
    games: int

    win_rate: float

    mean_points: float

    mean_cost_bps: float

    forced_sale_rate: float

    invalid_actions_per_game: float
