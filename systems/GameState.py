from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entities import Disc,DiscSnap
    from entities import Team,TeamSnap
    from config import Constants

@dataclass
class GameState:
    disc: Disc
    team_list: list[Team]
    delta_time: float
    const: Constants
    score: dict[int, int]
    tick: int

    def create_snap(self) -> GameStateSnap:
        return GameStateSnap(self.disc.create_snap(), tuple([team.create_snap() for team in self.team_list]), self.delta_time, self.const, (self.score[self.const.BLUE_TEAM_ID],self.score[self.const.RED_TEAM_ID],), self.tick)
    
@dataclass(frozen = True)
class GameStateSnap:
    disc: DiscSnap
    team_list: tuple[TeamSnap]
    delta_time: float
    const: Constants
    score: tuple
    tick: int