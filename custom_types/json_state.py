"""
The info dict plus the named observation, as sent to a frontend.
"""

from custom_types.step_info import StepInfo


class JsonState(StepInfo):
    observation: dict[str, float]
