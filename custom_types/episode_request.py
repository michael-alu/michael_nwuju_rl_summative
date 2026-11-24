"""
Body of POST /episode: who plays, which game (seed) and which market.
"""

from pydantic import BaseModel, Field


class EpisodeRequest(BaseModel):
    player: str = Field(default="ppo", description="ppo, dqn, a2c, reinforce, block_dealer, perfect_foresight or random.")

    seed: int = Field(default=100_000, description="Which game: the same seed always draws the same market and payouts.")

    market: str = Field(default="normal", description="normal or hard.")
