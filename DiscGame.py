from enum import Enum,auto



class GameCoordinator(Enum):
    def __init__(self, player_num: int, player_agent_list: list[list], tps: int, *args, **kwargs):
        self.player_num = player_num
        self.player_agent_list = player_agent_list
        self.tps = tps
        self._init_states()

    def _init_states(self):
        self.states = {
            "prepare": auto(),
            "start": auto(),
            "play": auto(),
            "pause": auto(),
            "end": auto()
        }
        self.current_state = self.states["prepare"]

    def _prepare(self):
        pass

    def _start(self):
        pass

    def _play(self):
        pass

    def _pause(self):
        pass

    def mainloop(self):
        while self.current_state != self.states["end"]:
            if self.current_state == self.states["prepare"]:
                self._prepare()
            elif self.current_state == self.states["start"]:
                self._start()
            elif self.current_state == self.states["play"]:
                self._play()
            elif self.current_state == self.states["pause"]:
                self._pause()



        