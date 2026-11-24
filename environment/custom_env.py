"""
ThinBook Pension, the main environment.

The agent is ultimately responsible for one N10m Nigerian pension fund for 60 trading days. Retirees take ownership of their
money at retirement: scheduled retirements are known in advance; early withdrawals and death benefits arrive at short notice.
It should pay out all benefits on time and keep the fund within its
investment limits, while losing as little as possible to selling costs.

Each step is one trading day:

1. The market moves (zero-drift fair values, calm/stormy volatility, small-cap volume with
droughts and day-to-day persistence, big-buyer offers). All of this is drawn at reset.

2. Yesterday's stock sale cash settles (T+1).

3. The agent chooses among 5 actions: wait, sell T-bills, sell bank stocks, sell small-cap stocks
(maximum 20% of the volume of the day), or ring a big buyer when one is available.
Every sale is a fixed slice of the starting fund (configs/market.yaml).

4. Today's payouts are paid from cash. If cash is short the env force-sells: T-bills, then
banks, then small caps at a fire-sale discount.

5. PenCom-style limits (not the exact PenCom numbers): small caps 35% of fund at most, banks 35% to 70%, measured at each asset's
starting price (book weights), so only the fund's sales and payouts move them,
never market direction. A breach can last 10 days of trading; after that, and at day 60,
the env forces trades until the fund is back inside.

6. Points: each sale adds (proceeds - fair value sold - fees) / N10,000, so a sale at fair value with no fees scores 0.
Fair value excludes the fund's own price impact, so the score stays the same even when markets go up or down.

Settings: configs/market.yaml.
"""

from pathlib import Path
from typing import cast

import numpy as np
import yaml

from custom_types.market_config import MarketConfig

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "market.yaml"
HARD_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "market_hard.yaml"

# Action Space
ACTION_NAMES = [
    "Wait",
    "Sell T-bills",
    "Sell bank shares",
    "Sell small-cap shares",
    "Call a big buyer",
]

WAIT = 0

SELL_TBILLS = 1

SELL_BANK_SHARES = 2

SELL_SMALL_CAP_SHARES = 3

CALL_BIG_BUYER = 4

# Observation Space
OBSERVATION_NAMES = [
    "days_left",
    "tbills_share",
    "banks_vs_limits",
    "small_caps_vs_limit",
    "cash_share",
    "settling_cash_share",
    "due_within_5_days",
    "due_within_15_days",
    "days_to_next_due",
    "grace_days_left",
    "small_caps_days_since_board_move",
    "small_caps_volume_yesterday",
    "small_caps_volume_5_days",
    "banks_recent_volatility",
    "big_buyer_offered",
]

OBSERVATION_LOW = np.zeros(len(OBSERVATION_NAMES), dtype=np.float32)

OBSERVATION_HIGH = np.ones(len(OBSERVATION_NAMES), dtype=np.float32)

WARM_UP_DAYS = 20

MINIMUM_TRADE_NAIRA = 1000.0

DUE_SOON_DAYS = 5

DUE_LATER_DAYS = 15

PAYOUT_SCALE = 0.5

MAX_PAYMENT_ATTEMPTS = 5

SUDDEN_KINDS = ["early_withdrawal", "death_benefit"]

PAYMENT_MARGIN = 1.02

VOLATILITY_SCALE = 0.08


def load_config(path: Path = CONFIG_PATH) -> MarketConfig:
    settings = yaml.safe_load(path.read_text(encoding="utf-8"))

    return cast(MarketConfig, settings)


def load_hard_config() -> MarketConfig:
    overrides = yaml.safe_load(HARD_CONFIG_PATH.read_text(encoding="utf-8"))

    settings = load_config()

    settings.update(overrides)

    return settings
