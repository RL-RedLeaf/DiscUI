from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .GameState import GameState


class PhysicSystem:
    def __init__(self):
        pass

    def setup(self, gamestate: GameState):
        self.gamestate = gamestate


    def apply(self):
        if self.gamestate.disc.state == 'flying':
            if self.gamestate.disc.pos[2] <= 0 and self.gamestate.disc.velocity[2] <= 0:
                self.gamestate.disc.pos[2] = 0
                self.gamestate.disc.velocity[2] = 0
                self.gamestate.disc.state = 'ground'
            else:
                v = self.gamestate.disc.velocity
                g = self.gamestate.const.GRAVITY
                dt = self.gamestate.delta_time
                v[2] += g * dt

                for i in range(len(v)):
                    self.gamestate.disc.pos[i] += v[i] * dt
        elif self.gamestate.disc.state == 'catched':
            for i in range(len(self.gamestate.disc.pos) - 1):   #玩家没有z轴
                self.gamestate.disc.pos[i] = self.gamestate.team_list[self.gamestate.disc.holder_key.team_id].player_list[self.gamestate.disc.holder_key.player_id].pos[i]

        else:
            pass