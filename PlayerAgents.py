from __future__ import annotations
from typing import TYPE_CHECKING


from entities import PlayerKey, PlayerSnap
from systems import AgentBase, CatchIntent, MoveIntent, ThrowIntent, Intent

if TYPE_CHECKING:
    from systems import GameStateSnap



class emptyPlayerAgent(AgentBase):
    player_key: PlayerKey


    def init(self, player_key: PlayerKey) -> None:
        self.player_key = player_key


    def agent(self, gamestate: GameStateSnap) -> list[Intent]:
        return []
