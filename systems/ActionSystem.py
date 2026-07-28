from __future__  import annotations
from concurrent.futures import ThreadPoolExecutor, TimeoutError,wait
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
    target_pos: tuple[int]

@dataclass
class ThrowIntent(Intent):
    disc_id: int
    motion: tuple[int]

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
        self.executor = ThreadPoolExecutor(max_workers=8)
        self.agent_time_limit = 0.01

    def _distance2d(self, pos1: list[float], pos2: list[float]):
        return ((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2) ** 0.5
        

    def _envelope(self, player_key: PlayerKey, intent: Intent) -> Action:
        return Action(player_key, intent)
    
    def _bigger_speed(self, velocity: tuple[float, float, float], limit: tuple[float, float, float]) -> bool:
        return all(abs(v) >= l for v, l in zip(velocity, limit))

    def setup(self, register_dict: dict, gamestate: GameState) -> bool:
        '''设置注册表, 此处返回 bool 用以表示注册表是否成功设置'''
        self.register_dict = register_dict
        self.gamestate = gamestate
        self.running_futures = {}

        try:
            for player_key, agent in register_dict.items():
                agent.init(player_key)
        except Exception as e:
            # print(f'ERROR:{e}')
            pass

        return True
    
    def agent_loop(self, state: GameStateSnap):
        '''每一帧获取 agent 的决策'''
        self.action_list: list[Action] = []

        for player_key, future in list(self.running_futures.items()):
            if future.done():
                # 旧结果过期，不使用，只清掉
                del self.running_futures[player_key]


        future_to_player = {}
        for player_key, agent in self.register_dict.items():
            if player_key in self.running_futures:
                # 上一次还没跑完，本帧不再提交
                print(f"Agent {player_key} still running, skip")
                continue

            future = self.executor.submit(agent.agent, state)
            future_to_player[future] = player_key
            self.running_futures[player_key] = future

        done, not_done = wait(
        future_to_player.keys(),
        timeout=self.agent_time_limit)

        for future in done:
            player_key = future_to_player[future]

            if self.running_futures.get(player_key) is future:
                del self.running_futures[player_key]


            try:
                intents = future.result()
            except Exception as e:
                print(f"Agent {player_key} error: {e}")
                continue

            if not intents:
                continue

            for intent in intents:
                action = self._envelope(player_key, intent)
                if self._anti_cheat(state, action):
                    self.action_list.append(action)

        return True
    
    def _anti_cheat(self, state:GameStateSnap, action: Action) -> bool:
        #0 验证Intent合法性
        if isinstance(action.intent, (ThrowIntent, CatchIntent, MoveIntent)):
            pass
        else:
            print(f'未知动作{type(action.intent)}')
            return False

        
        #1 MoveIntent检测
        if isinstance(action.intent, MoveIntent):
            #1.0 确认 player
            player = state.team_list[action.player_key.team_id].player_list[action.player_key.player_id]
            disc = state.disc

            #1.1 确认目标合法
            if type(action.intent.target_pos) == tuple and len(action.intent.target_pos) == 2:
                pass
            else:
                return False
            
            #1.2 确认未持盘
            if player.hold_disc == False and disc.holder_key != action.player_key:
                pass
            else:
                return False
            
            #1.3 确认移速
            if self._distance2d(list(player.pos), list(action.intent.target_pos)) <= state.const.PLAYER_SPEED * state.delta_time:
                pass
            else:
                return False
            
        #2 ThrowIntent检测
        elif isinstance(action.intent, ThrowIntent):
            #2.0 确认player
            player = state.team_list[action.player_key.team_id].player_list[action.player_key.player_id]
            disc = state.disc

            #2.1 确认目标合法
            if type(action.intent.motion) == tuple and len(action.intent.motion) == 3:
                if self._bigger_speed(action.intent.motion, state.const.MIN_THROW_SPEED):
                    pass
                else:
                    return False
            else: 
                return False
            
            #2.2 确认持盘人
            if disc.holder_key == action.player_key and player.hold_disc == True:
                pass
            else:
                return False
            
            #2.3 确认飞盘状态
            if disc.state == 'catched':
                pass
            else:
                return False
            

        #3 CatchIntent检测
        elif isinstance(action.intent, CatchIntent):
            #3.0 确认player
            player = state.team_list[action.player_key.team_id].player_list[action.player_key.player_id]
            disc = state.disc

            #3.1 确认飞盘状态
            if disc.state == 'flying' or disc.state == 'competing' or disc.state == 'waiting':
                pass
            else:
                return False
            
            #3.2 确认玩家状态
            if player.hold_disc == False and disc.holder_key == None:
                pass
            else:
                return False
            
            #3.3 确认接盘（不是这个词好喜感啊（））状态
            if self._distance2d(list(player.pos), (disc.pos[0], disc.pos[1])) <= state.const.CATCH_DISTANCE and disc.pos[2] <= state.const.CATCH_HIGHT:                
                pass
            else:
                return False

            #3.4 确保不在sub中以防止刷爆率
            if action.player_key not in self.gamestate.disc.sub_holder:
                pass
            else:
                return False
            
        #恭喜你经过不知道多少劫，活到了最后，堪称耐活王，成功证明自己没有作弊
        #你过关！
        return True


        
    def apply(self):
        for action in self.action_list:
            if isinstance(action.intent, MoveIntent):
                self.gamestate.team_list[action.player_key.team_id].player_list[action.player_key.player_id].pos = list(action.intent.target_pos)
            
            elif isinstance(action.intent, ThrowIntent):
                self.gamestate.disc.holder_key = None
                self.gamestate.disc.velocity = list(action.intent.motion)
                self.gamestate.disc.pos[2] += 2
                self.gamestate.disc.state = "flying"
                self.gamestate.team_list[action.player_key.team_id].player_list[action.player_key.player_id].hold_disc = False

            elif isinstance(action.intent, CatchIntent):
                self.gamestate.disc.sub_holder.append(action.player_key)
                if self.gamestate.disc.competing_ticks <= 0:
                    self.gamestate.disc.competing_ticks = 3
                self.gamestate.disc.state = 'competing'

            

