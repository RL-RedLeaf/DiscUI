from __future__ import annotations
from random import choice
from events import *
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .GameState import GameState
    from .EventBus import EventBus

    from DiscGame import State

class RuleSystem:
    def __init__(self):
        pass

    def setup(self, gamestate: GameState, states: State, event_bus: EventBus):
        self.gamestate = gamestate
        self.states = states
        self.event_bus = event_bus
        self.hold_time = 0.0

    def _distance(self, pos1: list[int], pos2: list[int]) -> float:
        return ((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2) ** 0.5
    
    def _inner(self, pos: list[int], area: tuple[int]):
        return pos[0] >= area[0] and pos[1] >= area[1] and pos[0] <= area[0] + area[2] and pos[1] <= area[1] + area[3]

    def apply(self):
        '''依次判定所有规则事件'''
        return_state = None #预留变量，看看后续要不要加入规则事件缓存和仲裁机制
        #v1.1尝试吧抢夺提到最前面，处理飞盘抢夺
        if self.gamestate.disc.state == 'competing':
            if self.gamestate.disc.competing_ticks > 0:
                self.gamestate.disc.competing_ticks -= 1
            
            elif self.gamestate.disc.competing_ticks <= 0:
                self.gamestate.disc.holder_key = choice(self.gamestate.disc.sub_holder)
                holder = self.gamestate.team_list[self.gamestate.disc.holder_key.team_id].player_list[self.gamestate.disc.holder_key.player_id]
                holder.hold_disc = True
                self.hold_time = 0.0
                self.gamestate.disc.sub_holder = []
                self.gamestate.disc.pos[0] = self.gamestate.team_list[self.gamestate.disc.holder_key.team_id].player_list[self.gamestate.disc.holder_key.player_id].pos[0]
                self.gamestate.disc.pos[1] = self.gamestate.team_list[self.gamestate.disc.holder_key.team_id].player_list[self.gamestate.disc.holder_key.player_id].pos[1]
                self.gamestate.disc.pos[2] = 0
                self.gamestate.disc.velocity = [0, 0, 0]     
                self.gamestate.disc.state = 'catched'
                self.event_bus.publish(DiscCatchEvent(self.gamestate.disc.holder_key))
                self.gamestate.disc.competing_ticks = 0
                self.last_holder_key = self.gamestate.disc.holder_key

        #这里把得分事件提前了, 以防止冲撞导致得分没有判定成功
        if self.gamestate.disc.state == 'catched':
            if self._inner(self.gamestate.disc.pos, self.gamestate.const.BLUE_SCORE_AREA) and self.gamestate.disc.holder_key.team_id == self.gamestate.const.BLUE_TEAM_ID:                
                self.event_bus.publish(ScoreEvent(self.gamestate.const.BLUE_TEAM_ID))
                self.gamestate.score[self.gamestate.const.BLUE_TEAM_ID] += 1
                self.hold_time = 0.0
                return self.states['RESET']

            elif self._inner(self.gamestate.disc.pos, self.gamestate.const.RED_SCORE_AREA) and self.gamestate.disc.holder_key.team_id == self.gamestate.const.RED_TEAM_ID:                
                self.event_bus.publish(ScoreEvent(self.gamestate.const.RED_TEAM_ID))
                self.gamestate.score[self.gamestate.const.RED_TEAM_ID] += 1
                self.hold_time = 0.0
                return self.states['RESET']


        #检测持盘手是否被冲撞
        if self.gamestate.disc.state == 'catched':
            team = self.gamestate.team_list[self.gamestate.disc.holder_key.team_id]
            player = self.gamestate.team_list[self.gamestate.disc.holder_key.team_id].player_list[self.gamestate.disc.holder_key.player_id]

            for op_team in self.gamestate.team_list:
                if op_team.team_id == player.player_key.team_id:
                    pass    #跳过己方队员
                else:
                    for op_player in op_team.player_list:
                        if self._distance(player.pos, op_player.pos) < self.gamestate.const.PLAYER_SIZE * 2:
                            self.event_bus.publish(FoulEvent('touch', op_team.team_id, op_player.player_key))
                            self.hold_time = 0.0
                            return self.states['RESET']
        
        #检测飞盘持有超时的事情暂时不处理
        if self.gamestate.disc.state == 'catched':
            self.hold_time += self.gamestate.delta_time

            if self.hold_time > self.gamestate.const.MAX_HOLD_TIME:
                self.event_bus.publish(FoulEvent('timeout', self.gamestate.disc.holder_key.team_id, self.gamestate.disc.holder_key))
                self.hold_time = 0.0
                return self.states['RESET']



        #检测盘落地
        if self.gamestate.disc.state == 'ground':
            self.hold_time = 0.0
            self.event_bus.publish(FoulEvent('stall', self.last_holder_key.team_id, self.last_holder_key))
            return self.states['RESET']
        #检测盘出界
        if self.gamestate.disc.pos[0] < 0 or self.gamestate.disc.pos[1] < 0 or self.gamestate.disc.pos[0] > self.gamestate.const.GAME_SIZE[0] or self.gamestate.disc.pos[1] > self.gamestate.const.GAME_SIZE[1]:
            self.event_bus.publish(FoulEvent('out', self.last_holder_key.team_id, self.last_holder_key))
            self.hold_time = 0.0
            return self.states['RESET']
        

        


            
        

