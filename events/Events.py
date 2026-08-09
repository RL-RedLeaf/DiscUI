from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from systems import GameStateSnap
    from entities import PlayerKey

class Event:
    def __init__(self):
        pass

class GameStartEvent(Event):
    def __init__(self, game_state: GameStateSnap):
        super().__init__()
        self.game_state = game_state
        
    def __str__(self):
        return f"GameStartEvent: GameStateSnap: {self.game_state}"

class GamePlayEvent(Event):
    def __init__(self, game_state: GameStateSnap):
        super().__init__()
        self.game_state = game_state
        
    def __str__(self):
        return f"GamePlayEvent: GameStateSnap: {self.game_state}"

@dataclass(frozen= True)
class FoulEvent(Event):
    reason: str 
    foul_team_id: int
    foul_player_key: PlayerKey

        
    def __str__(self):
        return f"FoulEvent, reason:{self.reason}"

@dataclass(frozen= True)
class DiscCatchEvent(Event):
    hold_player_key: PlayerKey

@dataclass(frozen = True)
class ScoreEvent(Event):
    score_team_id: int

@dataclass(frozen = True)
class ResetEvent(Event):
    pull_team_id: int
    gamestate: GameStateSnap

@dataclass(frozen = True)
class EndEvent(Event):
    end_type: str
    success_team_id: int | None