"""
Answer of POST /act: the chosen action and, for policy-gradient agents, the probability of each action.
"""

from pydantic import BaseModel


class ActResponse(BaseModel):
    action_id: int

    action_name: str

    probabilities: list[float] | None
