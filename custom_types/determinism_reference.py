"""The numbers the determinism check saves and compares, with a note on why they were saved."""

from typing import NotRequired, TypedDict

from custom_types.random_play_fingerprint import RandomPlayFingerprint
from custom_types.scorecard import Scorecard


class DeterminismReference(TypedDict):
    note: NotRequired[str]

    ppo_model: Scorecard

    random_play: RandomPlayFingerprint

    block_dealer: Scorecard

    perfect_foresight_planner: Scorecard
