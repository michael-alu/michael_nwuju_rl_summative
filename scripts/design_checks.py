"""
Design checks for ThinBook Pension, conducted BEFORE any baseline work and BEFORE the pass mark.

Only the drawn world (market and payouts) is used. A policy is never played.
A. Payouts: at least 95% of games have 2+; average/game between 3 and 8.
B. Band binds: in at least 70% of the games, if the payouts were paid only from T-bills and banks,
small caps would break out of their 35% cap.
C. Tight but feasible: the small-cap shares to dispose of to comply with the limit are
30% to 60% of what the volume cap allows the fund to sell over the game (median game).

Run from the project root: uv run python scripts/design_checks.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from environment.custom_env import WARM_UP_DAYS, load_config  # noqa: E402
from classes import ThinBookPensionEnv  # noqa: E402

GAMES = 2000

SEED_START = 500_000


def main() -> None:
    config = load_config()

    env = ThinBookPensionEnv(config)

    fund = config["starting_fund_naira"]

    small_caps_value = config["start_small_caps"] * fund

    small_caps_shares = config["small_caps_position_days"] * config["small_caps_median_volume"]

    payout_counts = []

    band_binds = []

    ratios = []

    for seed in range(SEED_START, SEED_START + GAMES):
        env.reset(seed=seed)

        total_payouts = 0.0

        for payout in env.payouts:
            total_payouts = total_payouts + payout["amount"]

        payout_counts.append(len(env.payouts))

        fund_after = fund - total_payouts

        band_binds.append(small_caps_value / fund_after > config["small_caps_max_share"])

        must_sell_share = max(1 - config["small_caps_max_share"] * fund_after / small_caps_value, 0.0)

        must_sell = must_sell_share * small_caps_shares

        game_volumes: list[float] = []

        for day in env.market[WARM_UP_DAYS:]:
            game_volumes.append(day["small_caps_volume"])

        capacity = config["participation_limit"] * sum(game_volumes)

        ratios.append(must_sell / capacity if capacity > 0 else float("inf"))

    counts = np.array(payout_counts)

    ratios_array = np.array(ratios)

    median_ratio = float(np.median(ratios_array))

    check_a = (counts >= 2).mean() >= 0.95 and 3 <= counts.mean() <= 8

    check_b = float(np.mean(band_binds)) >= 0.70

    check_c = 0.30 <= median_ratio <= 0.60

    print(f"Knobs: start mix T-bills {config['start_tbills']:.0%} / banks {config['start_banks']:.0%} / small caps {config['start_small_caps']:.0%}, "
          f"small-cap position {config['small_caps_position_days']} days of median volume, payouts total {config['payouts_total_min']:.0%}-{config['payouts_total_max']:.0%}")

    print(f"a. games with 2+ payouts {(counts >= 2).mean():.1%}, mean payouts {counts.mean():.2f}: {'PASS' if check_a else 'FAIL'}")

    print(f"b. band binds if paid from T-bills and banks only: {np.mean(band_binds):.1%} of games: {'PASS' if check_b else 'FAIL'}")

    print(f"c. small caps to sell / sellable at the volume cap: median {median_ratio:.2f} "
          f"(p10 {np.percentile(ratios_array, 10):.2f}, p90 {np.percentile(ratios_array, 90):.2f}; over 1 in {np.mean(ratios_array > 1):.1%} of games): {'PASS' if check_c else 'FAIL'}")


if __name__ == "__main__":
    main()
