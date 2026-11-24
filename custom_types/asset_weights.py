"""The fund's book weights: cash, T-bills, banks and small caps."""

from typing import TypedDict


class AssetWeights(TypedDict):
    cash: float

    tbills: float

    banks: float

    small_caps: float
