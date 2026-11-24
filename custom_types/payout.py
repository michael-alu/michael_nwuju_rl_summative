"""One pension payout: when it was claimed, when it is due, how much, and whether it is paid."""

from typing import TypedDict


class Payout(TypedDict):
    arrival_day: int

    due_day: int

    amount: float

    announced: bool

    kind: str

    paid: bool
