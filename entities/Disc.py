from __future__ import annotations
from dataclasses import dataclass
from .Entity import Entity
from .Team import PlayerKey
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from systems import EventBus
    from events import *
    

class Disc(Entity):                      #飞盘类，与游戏主线程和队员进行交互
    def __init__(self, pos: list[int]):
        super().__init__()
        self.pos = pos
        self.holder_key: PlayerKey | None = None
        self.velocity = [0, 0, 0]
        self.state = "waiting"   #简易状态机：waiting(只在开盘时出现，表示落地但不犯规) ,ground, flying, competing, catched
        self.sub_holder: list[PlayerKey] = []
        self.competing_ticks = 0
    
    def create_snap(self) -> DiscSnap:
        return DiscSnap(tuple(self.pos), self.holder_key, tuple(self.velocity), self.state)

@dataclass(frozen = True)
class DiscSnap:
    pos: tuple[float, float, float]
    holder_key: PlayerKey
    velocity: tuple[float, float, float]
    state: str

