from enum import Enum,auto
from config import *
from entities import *
from events import *
from systems import *
from ui import *


class GameCoordinator(Enum):
    def __init__(self, player_num: int, player_agent_list: list[list], fps: int, *args, **kwargs):
        self.player_num = player_num
        self.player_agent_list = player_agent_list
        self.fps = fps

        self._init_states()
   

    def _init_states(self):
        self.states = {
            "PREPARE": auto(),
            "START": auto(),
            "PLAY": auto(),
            "PAUSE": auto(),
            "RESET": auto(),
            "END": auto()
        }
        self.current_state = self.states["PREPARE"]

    def set_render(self, render: RenderPort):
        self.render = render
        return True

    def _prepare(self) -> None:
        self.event_bus = EventBus()
        self.constants = Constants()
        self.render.init()
        self.disc = Disc(self.event_bus)
        self.blue_team = Team(team_id= self.constants.BLUE_TEAM_ID, event_bus= self.event_bus, player_agent= self.player_agent_list[0])
        self.red_team = Team(team_id= self.constants.RED_TEAM_ID, event_bus= self.event_bus, player_agent= self.player_agent_list[-1])
        self.game_state = GameState(self.disc)

    def _start(self):
        pass

    def _play(self):
        pass

    def _pause(self):
        pass

    def mainloop(self):
        while self.current_state != self.states["END"]:
            if self.current_state == self.states["PREPARE"]:
                self._prepare()
            elif self.current_state == self.states["START"]:
                self._start()
            elif self.current_state == self.states["PLAY"]:
                self._play()
            elif self.current_state == self.states["PAUSE"]:
                self._pause()



        