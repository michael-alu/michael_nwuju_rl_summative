"""The command-line settings of one DQN run, as saved in its summary."""

from typing import TypedDict


class DqnSettings(TypedDict):
    name: str

    frames: int

    learning_rate: float

    gamma: float

    batch_size: int

    buffer_size: int

    frames_per_batch: int

    updates_per_batch: int

    warmup_frames: int

    epsilon_start: float

    epsilon_end: float

    epsilon_decay_frames: int

    target_update: str

    tau: float

    hard_update_every: int

    hidden_size: int

    reward_scale: float

    seed: int

    threads: int
