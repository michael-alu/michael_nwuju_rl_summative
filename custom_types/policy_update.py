"""The losses and entropy after one PPO, A2C or REINFORCE update."""

from typing import TypedDict


class PolicyUpdate(TypedDict):
    policy_loss: float

    value_loss: float

    entropy: float
