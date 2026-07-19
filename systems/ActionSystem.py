from __future__  import annotations
from dataclasses import dataclass
from entities import PlayerKey
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from systems import GameStateSnap, GameState

class Intent:
    pass

@dataclass(frozen = True)
class Action:
    player_key: PlayerKey
    intent: Intent

@dataclass
class MoveIntent(Intent):
    target_pos: list[int]

@dataclass
class ThrowIntent(Intent):
    disc_id: int
    motion: list[int]

@dataclass
class CatchIntent(Intent):
    disc_id: int

class AgentBase(ABC):
    @abstractmethod
    def init(self, player_key: PlayerKey):
        '''此函数用于设置playerKey'''
        pass

    @abstractmethod
    def agent(self, gamestate: GameStateSnap) -> list:
        '''此处接受游戏快照, 返回 Intent 列表'''
        pass



class ActionSystem:
    def __init__(self):
        pass
    

        

    def _envelope(self, player_key: PlayerKey, intent: Intent) -> Action:
        return Action(player_key, intent)

    def setup(self, register_dict: dict, gamestate: GameState) -> bool:
        '''设置注册表, 此处返回 bool 用以表示注册表是否成功设置'''
        self.register_dict = register_dict
        self.gamestate = gamestate

        try:
            for player_key, agent in register_dict.items():
                agent.init(player_key)
        except Exception as e:
            print(f'ERROR:{e}')

        return True
    
    def agent_loop(self, state: GameStateSnap):
        '''每一帧获取 agent 的决策'''
        self.action_list: list[Action] = []
        for player_ley, agent in self.register_dict.items():
            try:
                intents = agent.agent(state)        #获取决策列表
                if intents:
                    for intent in intents:
                        self.action_list.append(self._envelope(player_ley, intent))   #打包封装为 Action
                        if self._anti_cheat(state, self.action_list[-1]):             #开始神人操作之，神人反作弊
                            pass
                        else:
                            self.action_list.pop()

            except Exception as e:
                print(f'ERROR:{e}')
            
        return True
    
    def _anti_cheat(self, state:GameStateSnap, action: Action) -> bool:
        return True #现在没有任何反作弊措施，以后再写（
        
    def apply(self):
        for action in self.action_list:
            if isinstance(action.intent, MoveIntent):
                self.gamestate.team_list[action.player_key.team_id].player_list[action.player_key.player_id].pos = action.intent.target_pos
            
            elif isinstance(action.intent, ThrowIntent):
                self.gamestate.disc.holder_key = None
                self.gamestate.disc.velocity = action.intent.motion
                self.gamestate.disc.state = "flying"
                self.gamestate.team_list[action.player_key.team_id].player_list[action.player_key.player_id].hold_disc = False

            elif isinstance(action.intent, CatchIntent):
                self.gamestate.disc.sub_holder.append(action.player_key)
                if self.gamestate.disc.competing_ticks <= 0:
                    self.gamestate.disc.competing_ticks = 5
                self.gamestate.disc.state = 'competing'

            

