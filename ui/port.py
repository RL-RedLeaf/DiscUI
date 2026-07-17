from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from systems import GameState


class RenderPort(ABC):
    @abstractmethod
    def init(self):
        pass

    @abstractmethod
    def draw(self, state: GameState):
        pass
