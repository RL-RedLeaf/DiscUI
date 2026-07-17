from __future__ import annotations
from dataclasses import dataclass
from .Entity import Entity
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from systems import EventBus
    from events import *

class Disc(Entity):                      #飞盘类，与游戏主线程和队员进行交互
    def __init__(self, pos: list[int]):
        super().__init__()
        self.pos = pos
        pass
    
    def create_snap(self) -> DiscSnap:
        return DiscSnap(tuple(self.pos))

@dataclass(frozen = True)
class DiscSnap:
    pos: tuple[int]
