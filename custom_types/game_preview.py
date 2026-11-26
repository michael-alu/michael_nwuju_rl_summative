"""
What to expect from one game, counted from the market and payouts the env drew at reset. Shown to the
viewer before day 1; the agent never sees it (it only finds things out day by day).
"""

from typing import TypedDict


class GamePreview(TypedDict):
    payouts: int

    surprise_payouts: int

    payout_total_naira: float

    no_trade_days: int

    dry_spell_days: int

    stormy_days: int

    big_buyer_days: int
