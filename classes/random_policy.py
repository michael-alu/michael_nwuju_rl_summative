"""Random baseline: any of the 5 actions, uniformly."""

import numpy as np

from custom_types.step_info import StepInfo
from environment.custom_env import ACTION_NAMES
from classes.thin_book_pension_env import ThinBookPensionEnv

RANDOM_SEED = 7


class RandomPolicy:
    name = "random"

    def __init__(self, seed: int = RANDOM_SEED) -> None:
        self.random_generator = np.random.default_rng(seed)

    def reset(self, env: ThinBookPensionEnv) -> None:
        pass

    def act(self, observation: np.ndarray, info: StepInfo) -> int:
        return int(self.random_generator.integers(len(ACTION_NAMES)))
