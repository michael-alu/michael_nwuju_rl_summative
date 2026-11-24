"""
What one training run saves in its _summary.json file.
"""

from typing import TypedDict

from custom_types.dqn_settings import DqnSettings
from custom_types.pg_settings import PgSettings
from custom_types.scorecard import Scorecard


class RunSummary(TypedDict):
    name: str

    algorithm: str

    settings: PgSettings | DqnSettings

    frames: int

    episodes: int

    seconds: float

    best_frames: int

    validation_best: Scorecard | None

    held_out: Scorecard
