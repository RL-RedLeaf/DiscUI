from __future__ import annotations
from systems import AgentBase, ThrowIntent, MoveIntent, CatchIntent
from math import sqrt
from abc import ABC
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from systems import GameStateSnap


class emptyPlayerAgent(AgentBase):
    def __init__(self):
        super().__init__()

    def init(self, player_key):
        self.player_key = player_key

    def agent(self, gamestate):
        return []
