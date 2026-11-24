"""A value network that always says 0: REINFORCE without a baseline."""

import torch
from torch import nn


class ZeroValue(nn.Module):
    """A value 'network' that always says 0: REINFORCE without a baseline."""

    def forward(self, observation: torch.Tensor) -> torch.Tensor:
        return torch.zeros(observation.shape[:-1] + (1,))
