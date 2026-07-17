from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from systems import GameStateSnap

class Event:
    def __init__(self):
        pass

class GameStartEvent(Event):
    def __init__(self, game_state: GameStateSnap):
        super().__init__()
        self.game_state = game_state
        
    def __str__(self):
        return f"GameStartEvent: GameStateSnap {self.game_state}"

