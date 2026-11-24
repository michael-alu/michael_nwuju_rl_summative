"""One sale (or forced bank purchase) made during a day, with its cost."""

from typing import TypedDict


class Trade(TypedDict):
    asset: str

    shares: float

    proceeds: float

    fee: float

    cost: float

    reason: str
