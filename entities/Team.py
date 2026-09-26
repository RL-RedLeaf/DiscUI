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
    player_list: tuple[PlayerSnap]


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
        self.player_list = []
        self.agent_register_dict = {}   #Team.player_list 是唯一所有者；后续其实也不需要"同步维护"，只需要在结构性变更时走单一入口（就是一起改）
        self.register_dict = {}         #Gamestate里的注册表只是一个map，方便读取


        for i in range(self.player_num):        #这里不再使用列表魔法语句，是为了保证PlayerKey可以不和索引耦合，同时也更方便维护
            player_key = PlayerKey(self.team_id,i)  #暂时使用的还是索引ID，但是后续很方便更换成哈希等
            player = Player(player_key, 
                            (Constants.BLUE_TEAM_PULL[0] if self.team_id == Constants.BLUE_TEAM_ID else Constants.RED_TEAM_PULL[0],
                            (Constants.GAME_SIZE[1] / (self.player_num + 1)) * (i + 1) ))   #这一行和上面一行是用于计算初始坐标的
            self.player_list.append(player)
            self.register_dict[player_key] = player
            self.agent_register_dict[player_key] = self.player_agent_list[i]    

        print(f'队伍 {self.team_id} 已创建, 队员列表: {[str(player) for player in self.player_list]}')

    def get_register_dict(self) -> dict:
        return self.register_dict

    def get_agent_register_dict(self) -> dict:
        return self.agent_register_dict
    

    def reset(self) -> bool:    #TODO（待定）: 将此处访问改为使用注册表访问
        for i in range(self.player_num):
            self.player_list[i].pos = (Constants.BLUE_TEAM_PULL[0] if self.team_id == Constants.BLUE_TEAM_ID else Constants.RED_TEAM_PULL[0], 
                                       (Constants.GAME_SIZE[1] / (self.player_num + 1)) * (i + 1) )
            self.player_list[i].hold_disc = False
        return True

    def create_snap(self) -> TeamSnap:
        return TeamSnap(self.team_id, self.player_num, tuple([player.create_snap() for player in self.player_list]))


