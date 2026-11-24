"""
Answer of GET /health: the server is up and which trained agents it loaded. Uses typing_extensions.TypedDict because FastAPI needs it on Python 3.11 to document API answers.
"""

from typing_extensions import TypedDict


class HealthResponse(TypedDict):
    status: str

    models: dict[str, str]
