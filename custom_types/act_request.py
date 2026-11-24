"""
Body of POST /act: one observation and the player that should choose an action (a pydantic model, so FastAPI validates and documents it).
"""

from pydantic import BaseModel, Field


class ActRequest(BaseModel):
    observation: list[float] = Field(description="The 15 observation numbers in the order GET /models lists, each between 0 and 1.")

    player: str = Field(default="ppo", description="ppo, dqn, a2c, reinforce or random.")
