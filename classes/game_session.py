"""
One game of ThinBook Pension played one trading day at a time, for the browser view and the API.

It only reads the env (to_json_state and the info dict); it never changes the game.
"""

import numpy as np

from classes.policy import Policy
from classes.thin_book_pension_env import ThinBookPensionEnv
from custom_types.json_state import JsonState
from custom_types.market_config import MarketConfig
from custom_types.step_info import StepInfo
from environment.policy_helpers import read_step_info


class GameSession:
    def __init__(self, policy: Policy, config: MarketConfig, seed: int) -> None:
        self.policy = policy

        self.config = config

        self.seed = seed

        self.env = ThinBookPensionEnv(config)

        self.observation = np.zeros(0, dtype=np.float32)

        self.info: StepInfo | None = None

        self.last_reward = 0.0

        self.finished = False

    def start(self) -> JsonState:
        observation, raw_info = self.env.reset(seed=self.seed)

        self.observation = observation

        self.info = read_step_info(raw_info)

        self.policy.reset(self.env)

        self.last_reward = 0.0

        self.finished = False

        return self.env.to_json_state()

    def step(self) -> JsonState:
        if self.info is None:
            raise RuntimeError("Call start() before step().")

        action = self.policy.act(self.observation, self.info)

        observation, reward, finished, _, raw_info = self.env.step(action)

        self.observation = observation

        self.last_reward = float(reward)

        self.info = read_step_info(raw_info)

        self.finished = finished

        return self.env.to_json_state()
