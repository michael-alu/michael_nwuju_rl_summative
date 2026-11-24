"""One stock in the NGX universe file of the capstone data."""

from typing import TypedDict


class NgxStock(TypedDict):
    symbol: str

    market: str

    market_cap: float | None
