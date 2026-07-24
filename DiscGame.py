from enum import Enum,auto
from config import *
from entities import *
from events import *
from systems import *
from ui import *
from random import choice as randchoice
import time

class State(Enum):
    PREPARE = auto()
    START = auto()
    PLAY = auto()
    PAUSE = auto()
    RESET = auto()
    HALT = auto()

class GameCoordinator():
    def __init__(self, player_num: int, player_agent_list: list[list], fps: int, *args, **kwargs):
        self.player_num = player_num
        self.player_agent_list = player_agent_list
        self.fps = fps
        self.event_bus = EventBus()     #由于外部可能需要使用EventBus, 因此提前创建
        self.pending_state = []
        self.render = None
        self.foul_team_id = None
        self.score_team_id = None
        #若要转换状态直接将状态添置到该栈末尾即可
        self._init_states()
        self.event_bus.subscribe(FoulEvent, self.on_foul_event)
        self.event_bus.subscribe(ScoreEvent, self.on_score_event)
        #时间管理类
        self.target_frame_time = 1 / fps
        self.frame_start = 0.0
        self.frame_elapsed = 0.0
        self.sleep_time = 0.0
        self.frame_overrun = 0.0
        self.sum_elapsed = 0.0

    def _init_states(self):
        self.states = State
        self.current_state = self.states["PREPARE"]

    def set_render(self, render: RenderPort):
        self.render = render
        return True

    def _prepare(self) -> None:
        '''这一步只执行系统工具的初始化'''
        print('Prepare: 初始化系统工具')
        
        self.constants = Constants()
        self.physics = PhysicSystem()
        self.rules = RuleSystem()
        self.actions = ActionSystem()

        try:
            self.render.init(self.constants.GAME_SIZE, self.event_bus)
        except Exception as e:
            print(f'渲染器初始化失败, 错误信息: {e}')

        self.pending_state.append(self.states["START"])
        print(f'准备完成, 计划进入 {self.pending_state} 状态')

    def _start(self):
        print('Start: 场地就绪中')
        self.teams = [Team(Constants.BLUE_TEAM_ID, self.player_num, self.player_agent_list[0]), Team(Constants.RED_TEAM_ID, self.player_num, self.player_agent_list[-1])]

        self.register_dict: dict[PlayerKey, Player] = {}
        for team in self.teams:
            self.register_dict.update(team.get_register_dict())     #获取并合并两队队员注册表
        print(f'注册表已生成, 注册表内容: {self.register_dict}')


        self.first_pull = randchoice([Constants.BLUE_TEAM_ID, Constants.RED_TEAM_ID])
        print(f'抽签选择选择  {'BLUE' if self.first_pull == Constants.BLUE_TEAM_ID else 'RED'}  队先发盘')

        self.disc = Disc(list(Constants.BLUE_TEAM_PULL) if self.first_pull == Constants.BLUE_TEAM_ID else list(Constants.RED_TEAM_PULL))

        self.gamestate = GameState(self.disc, self.teams, 1 / self.fps, self.constants, {Constants.BLUE_TEAM_ID: 0, Constants.RED_TEAM_ID: 0}, 0)
        self.actions.setup(self.register_dict, self.gamestate)                      #将注册表传入动作系统
        self.physics.setup(self.gamestate)
        self.rules.setup(self.gamestate, self.states, self.event_bus)

        self.gamestate_snap = self.gamestate.create_snap()
        self.event_bus.publish(GameStartEvent(self.gamestate_snap))  #发布游戏状态快照事件
        
        print(f'场地就绪完成, 计划进入 PLAY 状态')
        self.pending_state.append(self.states["PLAY"])
        pass

    def _play(self):
        self.gamestate_snap = self.gamestate.create_snap()
        self.event_bus.publish(GamePlayEvent(self.gamestate_snap))

        self.actions.agent_loop(self.gamestate_snap)
        self.actions.apply()

        self.physics.apply()
        self.gamestate.tick += 1
        pending = self.rules.apply()

        if pending:
            self.pending_state.append(pending)
        

    def _pause(self):
        pass

    def _reset(self):
        if self.foul_team_id is not None:
            if self.foul_team_id == self.constants.BLUE_TEAM_ID:
                self.gamestate.disc.pos = list(self.constants.RED_TEAM_PULL)
                self.gamestate.disc.velocity = [0, 0, 0]
                self.gamestate.disc.state = 'waiting'
                self.gamestate.disc.holder_key = None
                self.gamestate.disc.sub_holder = []
                self.gamestate.disc.competing_ticks = 0
                for team in self.teams:
                    for player in team.player_list:
                        player.hold_disc = False

                self.pull_team = self.constants.RED_TEAM_ID
                self.foul_team_id = None

            elif self.foul_team_id == self.constants.RED_TEAM_ID:
                self.gamestate.disc.pos = list(self.constants.BLUE_TEAM_PULL)
                self.gamestate.disc.velocity = [0, 0, 0]
                self.gamestate.disc.state = 'waiting'
                self.gamestate.disc.holder_key = None
                self.gamestate.disc.sub_holder = []
                self.gamestate.disc.competing_ticks = 0
                for team in self.teams:
                    for player in team.player_list:
                        player.hold_disc = False
                self.pull_team = self.constants.BLUE_TEAM_ID
                self.foul_team_id = None
            
        elif self.score_team_id is not None:
            if self.score_team_id == self.constants.BLUE_TEAM_ID:
                self.gamestate.disc.pos = list(self.constants.RED_TEAM_PULL)
                self.gamestate.disc.velocity = [0, 0, 0]
                self.gamestate.disc.state = 'waiting'
                self.gamestate.disc.holder_key = None
                self.gamestate.disc.sub_holder = []
                self.gamestate.disc.competing_ticks = 0
                for team in self.teams:
                    for player in team.player_list:
                        player.hold_disc = False
                self.pull_team = self.constants.RED_TEAM_ID
                self.score_team_id = None

            elif self.score_team_id == self.constants.RED_TEAM_ID:
                self.gamestate.disc.pos = list(self.constants.BLUE_TEAM_PULL)
                self.gamestate.disc.velocity = [0, 0, 0]
                self.gamestate.disc.state = 'waiting'
                self.gamestate.disc.holder_key = None
                self.gamestate.disc.sub_holder = []
                self.gamestate.disc.competing_ticks = 0
                for team in self.teams:
                    for player in team.player_list:
                        player.hold_disc = False
                self.pull_team = self.constants.BLUE_TEAM_ID
                self.score_team_id = None

        else:
            raise RuntimeError("reset triggered without foul or score source")

        self.gamestate_snap = self.gamestate.create_snap()
            
        self.event_bus.publish(ResetEvent(self.pull_team, self.gamestate_snap))

        self.foul_team_id = None
        self.score_team_id = None

        self.pending_state.append(self.states['PLAY'])

    def _trans(self, from_state, to_state) -> bool:
        return True

    def mainloop(self):
        while self.current_state != self.states["HALT"]:
            self.frame_start = time.perf_counter()

            if self.current_state == self.states["PREPARE"]:
                self._prepare()
            elif self.current_state == self.states["START"]:
                self._start()
            elif self.current_state == self.states["PLAY"]:
                self._play()
            elif self.current_state == self.states["PAUSE"]:
                self._pause()
            elif self.current_state == self.states["RESET"]:
                self._reset()


            if self.pending_state:      
                #处理状态转换（其实我并没有想好如何实现退出和进入，但是目前问题不大
                print(f'当前状态: {self.current_state}, 待转换状态: {self.pending_state}')
                if self._trans(self.current_state, self.pending_state[-1]):
                    self.current_state = self.pending_state.pop()
                    print(f'状态转换成功, 当前状态: {self.current_state}')
                    
                else:
                    print(f'状态转换失败, from {self.current_state} to {self.pending_state}')


            self.frame_elapsed = time.perf_counter() - self.frame_start
            self.sum_elapsed += self.frame_elapsed
            self.sleep_time = self.target_frame_time - self.frame_elapsed
            if self.sleep_time > 0:
                time.sleep(self.sleep_time)
                self.frame_overrun = 0.0
            else:
                self.frame_overrun = -self.sleep_time

            try:
                if self.gamestate.tick % self.fps == 0:
                    print(
                        f"===60-ticks-sum==="
                        f"work={self.frame_elapsed * 1000:.2f}ms, "
                        f"avg_work={self.sum_elapsed / self.fps * 1000:.2f}ms, "
                        f"sleep={max(self.sleep_time, 0) * 1000:.2f}ms, "
                        f"overrun={self.frame_overrun * 1000:.2f}ms"
                    )
                    self.sum_elapsed = 0.0
            except Exception as e:
                pass


        print("游戏结束, 进入 HALT 状态")


    def on_foul_event(self, event: FoulEvent):
        self.foul_team_id = event.foul_team_id
        
    def on_score_event(self, event: ScoreEvent):
        self.score_team_id = event.score_team_id

from ui import PygameRenderPort
from PlayerAgents import emptyPlayerAgent


if __name__ == "__main__":
    game = GameCoordinator(2, player_agent_list=[[emptyPlayerAgent(), emptyPlayerAgent()], [emptyPlayerAgent(), emptyPlayerAgent()]], fps=60)
    game.set_render(PygameRenderPort(1230, 1200))

    # from EventMonitor import EventMonitor
    # event_monitor = EventMonitor(event_bus=game.event_bus)  #创建事件监控器实例, 不过这玩意就调试用, 不然 play 状态得吵死

    game.mainloop()