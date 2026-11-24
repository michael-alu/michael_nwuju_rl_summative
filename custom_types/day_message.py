"""
What the server streams to the browser after every trading day (also one entry of POST /episode).
"""

from typing import TypedDict

from custom_types.json_state import JsonState


class DayMessage(TypedDict):
    type: str

    state: JsonState

    action_text: str

    reward: float

    finished: bool

    outcome_text: str
