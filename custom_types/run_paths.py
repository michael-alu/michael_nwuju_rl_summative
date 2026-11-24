"""
Where one sweep run keeps its logs, summary and models.
"""

from pathlib import Path
from typing import TypedDict


class RunPaths(TypedDict):
    log_dir: Path

    summary: Path

    training: Path

    console: Path

    model_dir: Path
