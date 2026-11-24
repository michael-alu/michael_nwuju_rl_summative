"""The command-line settings of one PPO, A2C or REINFORCE run, as saved in its summary."""

from typing import TypedDict


class PgSettings(TypedDict):
    name: str

    algorithm: str

    frames: int

    learning_rate: float

    rollout: int

    minibatch: int

    epochs: int

    entropy: float

    gae_lambda: float

    clip: float

    gamma: float

    value_coefficient: float

    baseline: str

    hidden_size: int

    reward_scale: float

    seed: int

    threads: int
