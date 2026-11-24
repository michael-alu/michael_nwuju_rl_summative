"""
The first message of a streamed game: the fixed facts about the game (limits, fund size, player).
"""

from typing import TypedDict

from custom_types.game_meta import GameMeta


class MetaMessage(TypedDict):
    type: str

    meta: GameMeta
