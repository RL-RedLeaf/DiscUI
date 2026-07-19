from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from systems import GameStateSnap


class RenderPort(ABC):
    @abstractmethod
    def init(self,game_size, event_bus):
        pass

    @abstractmethod
    def draw(self, state: GameStateSnap):
        pass
