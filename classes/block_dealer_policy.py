"""Block dealer baseline: the same cash handling as the volume-aware trimmer, but small caps
leave only through negotiated block deals with a big buyer, never by trimming on the exchange."""

import numpy as np

from custom_types.step_info import StepInfo
from classes.volume_aware_trimmer_policy import VolumeAwareTrimmerPolicy
from environment.custom_env import CALL_BIG_BUYER, SELL_SMALL_CAP_SHARES, WAIT
from environment.policy_helpers import LIMIT_MARGIN, projected_small_caps_share


class BlockDealerPolicy(VolumeAwareTrimmerPolicy):
    """Same cash handling as the volume-aware trimmer, but small caps leave only through
    negotiated block deals: no exchange trimming, the big buyer whenever the fund is heading
    for its small-cap limit."""

    name = "block_dealer"

    def act(self, observation: np.ndarray, info: StepInfo) -> int:
        action = super().act(observation, info)

        if action == SELL_SMALL_CAP_SHARES:
            action = WAIT

        heading_over = projected_small_caps_share(info) > self.config["small_caps_max_share"] - LIMIT_MARGIN

        if info["big_buyer_offered_today"] and heading_over:
            return CALL_BIG_BUYER

        return action
