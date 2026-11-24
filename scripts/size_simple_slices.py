"""
Size the bank and small-cap sale slices from the game's structure, not the results.

1. Small-cap slice: the median game's required small-cap sale (to satisfy the 35% cap
after all payouts) divided equally over the 60 days, capped by what the 20% volume cap
allows on an average traded day.
2. Bank slice: half the median single payout; so two bank sales (cash arrives T+1) cover a
typical early withdrawal or death benefit, which is payable 2 to 3 days after the claim date.
3. Write both into configs/market.yaml.

Run from the project root: uv run python scripts/size_simple_slices.py
"""

import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from environment.custom_env import CONFIG_PATH, load_config  # noqa: E402
from classes import ThinBookPensionEnv  # noqa: E402

GAMES = 2000

SEED_START = 500_000


def main() -> None:
    config = load_config()

    env = ThinBookPensionEnv(config)

    fund = config["starting_fund_naira"]

    small_caps_value = config["start_small_caps"] * fund

    needs = []

    payout_sizes: list[float] = []

    for seed in range(SEED_START, SEED_START + GAMES):
        env.reset(seed=seed)

        total_payouts = 0.0

        for payout in env.payouts:
            total_payouts = total_payouts + payout["amount"]

            payout_sizes.append(payout["amount"])

        needs.append(max(small_caps_value - config["small_caps_max_share"] * (fund - total_payouts), 0.0))

    pace_share = float(np.median(needs)) / config["horizon_days"] / fund

    mean_traded_volume = config["small_caps_median_volume"] * math.exp(config["small_caps_volume_log_sigma"] ** 2 / 2)

    start_price = small_caps_value / (config["small_caps_position_days"] * config["small_caps_median_volume"])

    volume_cap_share = config["participation_limit"] * mean_traded_volume * start_price / fund

    small_caps_slice = min(pace_share, volume_cap_share)

    banks_slice = float(np.median(payout_sizes)) / 2 / fund

    print(f"small caps: median game needs {np.median(needs) / fund:.4f} of the fund -> {pace_share:.5f} per day; cap on an average traded day {volume_cap_share:.5f} -> slice {small_caps_slice:.5f}")

    print(f"banks: median single payout {np.median(payout_sizes) / fund:.4f} of the fund -> slice {banks_slice:.5f}")

    text = CONFIG_PATH.read_text(encoding="utf-8")

    text = re.sub(r"\nbanks_slice:.*", "", text)

    text = re.sub(r"\nsmall_caps_slice:.*", "", text)

    marker = "big_buyer_slice:"

    lines = [
        f"banks_slice: {banks_slice:.5f}                   # DESIGN KNOB (structural): half the median single payout (scripts/size_simple_slices.py)",
        f"small_caps_slice: {small_caps_slice:.5f}              # DESIGN KNOB (structural): the median game's required small-cap sale / 60 days, capped by the volume limit on an average traded day (scripts/size_simple_slices.py)",
    ]

    text = text.replace(marker, "\n".join(lines) + "\n" + marker, 1)

    CONFIG_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
