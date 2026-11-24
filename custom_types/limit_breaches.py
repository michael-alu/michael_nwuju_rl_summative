"""How far (in naira at book prices) the fund is outside each investment limit."""

from typing import TypedDict


class LimitBreaches(TypedDict):
    small_caps_over: float

    banks_over: float

    banks_under: float
