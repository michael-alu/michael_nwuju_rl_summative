"""
Everything in configs/calibration.yaml.
"""

from typing import NotRequired, TypedDict

from custom_types.bank_liquidity import BankLiquidity
from custom_types.basket_statistics import BasketStatistics
from custom_types.calibration_rules import CalibrationRules
from custom_types.market_statistics import MarketStatistics
from custom_types.small_caps_liquidity import SmallCapsLiquidity
from custom_types.volume_persistence import VolumePersistence


class Calibration(TypedDict):
    generated_on: str

    source: str

    date_range: str

    sessions: int

    rules: CalibrationRules

    market_asi: MarketStatistics

    big_banks_basket: BasketStatistics

    bank_liquidity: BankLiquidity

    small_caps_basket: BasketStatistics

    small_caps_liquidity: SmallCapsLiquidity

    small_caps_volume_persistence: NotRequired[VolumePersistence]
