"""Plays a saved network greedily, so it can be scored like any baseline."""

import numpy as np
import torch
from torch import nn

from custom_types.step_info import StepInfo
from classes.thin_book_pension_env import ThinBookPensionEnv


class TorchPolicy:
    name = "trained_agent"

    def __init__(self, network: nn.Module) -> None:
        self.network = network

    def reset(self, env: ThinBookPensionEnv) -> None:
        pass

    def act(self, observation: np.ndarray, info: StepInfo) -> int:
        with torch.no_grad():
            scores = self.network(torch.as_tensor(observation, dtype=torch.float32))

        return int(torch.argmax(scores).item())
