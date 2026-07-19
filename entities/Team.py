from __future__ import annotations

from .Entity import Entity
from dataclasses import dataclass
from config import Constants

@dataclass(frozen = True)
class PlayerKey:
    team_id: int
    player_id: int
    
@dataclass(frozen = True)
class PlayerSnap:
    player_key: PlayerKey
    pos: tuple[int, int]
    hold_disc: bool

@dataclass(frozen = True)
class TeamSnap:
    team_id: int
    player_num: int
    player_list: tuple


class Player(Entity):                   #队员类，不与游戏主进程进行直接交互，将信息传达至自己的team类
    def __init__(self,player_key: PlayerKey, pos: list[int]): #id为队员编号，team_id为队伍编号
        super().__init__()
        self.player_key = player_key
        self.pos = pos
        self.hold_disc = False

    def __str__(self):
        return f'Player: {self.player_key}, pos: {self.pos}, hold_disc: {self.hold_disc}'

    def create_snap(self) -> PlayerSnap:
        return PlayerSnap(self.player_key, tuple(self.pos), self.hold_disc)


class Team:                             #队伍类，与队员和游戏主进程交互
    def __init__(self,team_id,player_num,player_agent:list):
        self.team_id = team_id
        self.player_num = player_num
        self.player_agent_list = player_agent
        self.create_players()

    def create_players(self):
        self.player_peys = [PlayerKey(self.team_id,i) for i in range(self.player_num)]          #先创建身份标识
        self.player_list = [Player(self.player_peys[i], 
                            (Constants.BLUE_TEAM_PULL[0] if self.team_id == Constants.BLUE_TEAM_ID else Constants.RED_TEAM_PULL[0],
                             (Constants.GAME_SIZE[1] / (self.player_num + 1)) * (i + 1) )) for i in range(self.player_num)]  #然后身份标识导入 Player
        print(f'队伍 {self.team_id} 已创建, 队员列表: {[str(player) for player in self.player_list]}')
        self.register_dict = {self.player_peys[i]:self.player_agent_list[i] for i in range(self.player_num)}    #最后生成 Agent 注册表

    def get_register_dict(self) -> dict:
        return self.register_dict

    def create_snap(self) -> TeamSnap:
        return TeamSnap(self.team_id, self.player_num, tuple([player.create_snap() for player in self.player_list]))

