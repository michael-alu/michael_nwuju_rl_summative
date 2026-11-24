"""
The body FastAPI sends with a 422 error from this API: a plain-words explanation.
"""

from typing import TypedDict


class ErrorResponse(TypedDict):
    detail: str
