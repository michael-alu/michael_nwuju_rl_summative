"""What every policy must have: a name, reset(env) and act(observation, info)."""

from typing import Protocol

import numpy as np

from custom_types.step_info import StepInfo
from classes.thin_book_pension_env import ThinBookPensionEnv


class Policy(Protocol):
    name: str

    def reset(self, env: ThinBookPensionEnv) -> None: ...

    def act(self, observation: np.ndarray, info: StepInfo) -> int: ...
