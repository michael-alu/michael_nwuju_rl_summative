"""
Check how much small-cap volume carries over from one day to the next.

1. For every small cap picked in calibrate.py, take the consecutive sessions where both
days traded, and then measure to what extent yesterday's log volume correlates with today's log volume.

2. Track how often a zero volume day is followed by another zero volume day, and how often a traded day is.

3. Write the medians across stocks to the small_caps_volume_persistence section of
configs/calibration.yaml (summary numbers only).

It only works with our capstone NGX data (licensed Kobo Terminal exports), which cannot be shared publicly,
so the data folder is not in this repository.

Run from the project root:

uv run python scripts/calibrate_volume_persistence.py --data-dir <path to the capstone NGX data>
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calibrate import load_asi, pick_small_caps, rounded  # noqa: E402
from custom_types import Calibration, VolumePersistence  # noqa: E402

CALIBRATION_PATH = Path(__file__).resolve().parent.parent / "configs" / "calibration.yaml"

MINIMUM_PAIRS = 50

MINIMUM_ZERO_DAYS = 20


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure small-cap volume persistence.")

    parser.add_argument("--data-dir", type=Path, required=True)

    arguments = parser.parse_args()

    data_dir = arguments.data_dir.expanduser()

    asi = load_asi(data_dir)

    small_caps = pick_small_caps(data_dir, pd.DatetimeIndex(asi.index))

    log_autocorrelations: list[float] = []

    zero_after_zero: list[float] = []

    zero_after_traded: list[float] = []

    for prices in small_caps.values():
        volume = prices["volume"].to_numpy()

        traded = volume > 0

        both_traded = traded[1:] & traded[:-1]

        if both_traded.sum() > MINIMUM_PAIRS:
            today = np.log(volume[1:][both_traded])

            yesterday = np.log(volume[:-1][both_traded])

            log_autocorrelations.append(float(np.corrcoef(today, yesterday)[0, 1]))

        not_traded = np.logical_not(traded)

        enough_days = not_traded[:-1].sum() > MINIMUM_ZERO_DAYS and traded[:-1].sum() > MINIMUM_ZERO_DAYS

        if enough_days:
            zero_after_zero.append(float(not_traded[1:][not_traded[:-1]].mean()))

            zero_after_traded.append(float(not_traded[1:][traded[:-1]].mean()))

    persistence: VolumePersistence = {
        "stocks": len(small_caps),
        "zero_after_zero_median": float(np.median(zero_after_zero)),
        "window": f"{asi.index[0].date()} to {asi.index[-1].date()}",
        "zero_after_traded_median": float(np.median(zero_after_traded)),
        "log_volume_lag1_autocorrelation_median": float(np.median(log_autocorrelations)),
        "method": "per stock: correlation of log volume on consecutive traded sessions; zero-volume transition frequencies; medians across stocks",
        "log_volume_lag1_autocorrelation_quartiles": [float(np.percentile(log_autocorrelations, 25)), float(np.percentile(log_autocorrelations, 75))],
    }

    calibration: Calibration = yaml.safe_load(CALIBRATION_PATH.read_text(encoding="utf-8"))

    calibration["small_caps_volume_persistence"] = persistence

    CALIBRATION_PATH.write_text(yaml.safe_dump(rounded(calibration), sort_keys=False, width=200), encoding="utf-8")

    print(yaml.safe_dump(rounded(persistence), sort_keys=False))


if __name__ == "__main__":
    main()
