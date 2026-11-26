"""
How one player behaved over the held-out games: where its selling cost came from and how it handled
payouts, the small-cap limit and the big buyer. Written by scripts/explain_agents.py.
"""

from typing import TypedDict


class BehaviourSummary(TypedDict):
    player: str

    games: int

    win_rate: float

    forced_sale_rate: float

    cost_bps: float

    chosen_sales_bps: float

    big_buyer_bps: float

    forced_payout_bps: float

    forced_limit_bps: float

    cash_ready_share: float

    breach_days_per_game: float

    big_buyer_taken_share: float

    small_caps_on_exchange_bps: float

    action_shares: dict[str, float]
