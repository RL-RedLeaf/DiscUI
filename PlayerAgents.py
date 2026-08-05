from __future__ import annotations

from math import sqrt
from typing import TYPE_CHECKING

from entities import PlayerKey
from systems import AgentBase, TeamAgentBase, CatchIntent, Intent, MoveIntent, ThrowIntent

if TYPE_CHECKING:
    from systems import GameStateSnap


class emptyPlayerAgent(AgentBase):
    def init(self, player_key: PlayerKey) -> None:
        self.player_key = player_key

    def agent(self, gamestate: GameStateSnap, plan = None) -> list[Intent]:
        return []

class emptyTeamAgent(TeamAgentBase):
    def init(self, team_id, player_list: list[PlayerKey]):
        '''此函数接受teamID和所在队伍playerKey的列表'''
        self.team_id = team_id
        self.player_list = player_list

    def agent(self, gamestate: GameStateSnap):
        '''此函数接受游戏快照，返还下一帧的作战计划'''
        return None

