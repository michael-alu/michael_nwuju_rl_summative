"""
One player the game can use: a trained agent, a baseline, the planner or random play. Uses typing_extensions.TypedDict because FastAPI needs it on Python 3.11 to document API answers.
"""

from typing_extensions import TypedDict


class ModelEntry(TypedDict):
    player: str

    label: str

    kind: str

    run_name: str

    source: str

    held_out_win_rate: float | None

    held_out_mean_points: float | None

    hidden_size: int

    available: bool

    note: str
