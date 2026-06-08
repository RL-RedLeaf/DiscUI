# ui/port.py — 抽象接口
from abc import ABC, abstractmethod
from systems import GameState

class RenderPort(ABC):
    @abstractmethod
    def draw(self, state: GameState):
        pass