"""The result of one played game."""

from typing import TypedDict


class GameResult(TypedDict):
    seed: int

    cost_bps: float

    forced: bool

    forced_events: int

    invalid_actions: int

    total_points: float
