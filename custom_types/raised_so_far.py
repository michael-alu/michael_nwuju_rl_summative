"""
How much cash the pro-rata baseline has raised from each asset so far.
"""

from typing import TypedDict


class RaisedSoFar(TypedDict):
    tbills: float

    banks: float

    small_caps: float
