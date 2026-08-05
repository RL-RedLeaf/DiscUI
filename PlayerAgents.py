from __future__ import annotations

from math import sqrt
from typing import TYPE_CHECKING

from entities import PlayerKey
from systems import AgentBase, CatchIntent, Intent, MoveIntent, ThrowIntent

if TYPE_CHECKING:
    from systems import GameStateSnap


class emptyPlayerAgent(AgentBase):
    player_key: PlayerKey

    def init(self, player_key: PlayerKey) -> None:
        self.player_key = player_key

    def agent(self, gamestate: GameStateSnap) -> list[Intent]:
        return []

class LeafPlayerAgent(AgentBase):
    player_key: PlayerKey