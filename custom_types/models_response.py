"""
Answer of GET /models: every player, plus the observation order and action names an outside app needs. Uses typing_extensions.TypedDict because FastAPI needs it on Python 3.11 to document API answers.
"""

from typing_extensions import TypedDict

from custom_types.model_entry import ModelEntry


class ModelsResponse(TypedDict):
    players: list[ModelEntry]

    observation_names: list[str]

    action_names: list[str]
