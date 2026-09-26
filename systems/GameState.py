from __future__ import annotations
from dataclasses import dataclass,replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entities import Disc,DiscSnap,Team,TeamSnap,PlayerKey,Player,PlayerSnap
    from config import Constants

@dataclass
class GameState:
    #已更新: 增加注册表持有及相关处理（创建快照等）
    disc: Disc
    team_list: list[Team]
    delta_time: float
    const: Constants
    score: dict[int, int]
    tick: int
    register_dict: dict[PlayerKey, Player]

    def create_snap(self) -> GameStateSnap:
        return GameStateSnap(self.disc.create_snap(), tuple([team.create_snap() for team in self.team_list]), self.delta_time, self.const, (self.score[self.const.BLUE_TEAM_ID],self.score[self.const.RED_TEAM_ID],), self.tick, {player_key: player.create_snap() for player_key, player in self.register_dict.items()})
    
@dataclass(frozen = True)
class GameStateSnap:
    #已更新: 增加注册表持有
    disc: DiscSnap
    team_list: tuple[TeamSnap]
    delta_time: float
    const: Constants
    score: tuple
    tick: int
    register_dict: dict[PlayerKey, PlayerSnap]

    def fork(self) -> GameStateSnap:
        return replace(self, register_dict = self.register_dict.copy()) #用于创造一个新的字典，防止被篡改后污染到其他使用者