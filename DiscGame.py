from enum import Enum,auto
from config import *
from entities import *
from events import *
from systems import *
from ui import *
from random import choice as randchoice
import time
from datetime import datetime
from pathlib import Path

def make_record_path() -> Path:
    record_dir = Path(__file__).resolve().parent / "records"
    record_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return record_dir / f"game_{timestamp}.jsonl"

class State(Enum):
    PREPARE = auto()
    START = auto()
    PLAY = auto()
    PAUSE = auto()
    RESET = auto()
    HALT = auto()

class GameCoordinator():
    def __init__(self, player_num: int, player_agent_list: list[list], team_agent_list: list[TeamAgentBase], fps: int, record = False, *args, **kwargs):
        self.player_num = player_num
        self.player_agent_list = player_agent_list
        self.team_agent_list = team_agent_list
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
        self.event_bus.subscribe(EndEvent, self.on_end_event)   
        #时间管理类
        self.target_frame_time = 1 / fps
        self.frame_start = 0.0
        self.frame_elapsed = 0.0
        self.sleep_time = 0.0
        self.frame_overrun = 0.0
        self.sum_elapsed = 0.0

        self.record = record

        self.end_type = None
        self.winner_team_id = None


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

        if self.record:
            self.recorder = Recorder()
            self.recorder.setup(make_record_path(), self.event_bus)

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
        self.team_register_dict:dict[int, TeamAgentBase] = {}


        for team in self.teams:
            self.register_dict.update(team.get_register_dict())     #获取并合并两队队员注册表
            self.team_register_dict[team.team_id] = self.team_agent_list[team.team_id]


        print(f'注册表已生成, 注册表内容: {self.register_dict}')

        


        self.first_pull = randchoice([Constants.BLUE_TEAM_ID, Constants.RED_TEAM_ID])
        print(f'抽签选择选择  {'BLUE' if self.first_pull == Constants.BLUE_TEAM_ID else 'RED'}  队先发盘')

        self.disc = Disc(list(Constants.BLUE_TEAM_PULL) if self.first_pull == Constants.BLUE_TEAM_ID else list(Constants.RED_TEAM_PULL))

        self.gamestate = GameState(self.disc, self.teams, 1 / self.fps, self.constants, {Constants.BLUE_TEAM_ID: 0, Constants.RED_TEAM_ID: 0}, 0)
        self.actions.setup(self.register_dict, self.team_register_dict, self.gamestate)                      #将注册表传入动作系统
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
        #先发布快照，渲染或者记录
        pending = self.rules.apply()        
        if pending:
            self.pending_state.append(pending)
        #这里把规则判定提到最前面，保证只判定到已发布的内容，防止各系统实施更改以后还没有创建快照就发布
        self.actions.agent_loop(self.gamestate_snap)
        self.actions.apply()

        self.physics.apply()
        self.gamestate.tick += 1
        


        

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
                    team.reset()

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
                    team.reset()

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
                    team.reset()

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
                    team.reset()
                    
                self.pull_team = self.constants.BLUE_TEAM_ID
                self.score_team_id = None

        else:
            raise RuntimeError("reset triggered without foul or score source")

        self.gamestate_snap = self.gamestate.create_snap()
            
        self.event_bus.publish(ResetEvent(self.pull_team, self.gamestate_snap))

        self.foul_team_id = None
        self.score_team_id = None

        self.pending_state.append(self.states['PLAY'])

    def _halt(self, interrupt: bool = False):
        if self.record:
            self.recorder.record_end(end_type = 'interrupt' if interrupt else self.end_type)
            self.recorder.close()

        if not hasattr(self, 'gamestate'):
            return None

        blue, red = self.gamestate.score[Constants.BLUE_TEAM_ID], self.gamestate.score[Constants.RED_TEAM_ID]

        if interrupt:
            print(f'游戏中断, 当前比分{blue}:{red}')
            return None, (blue, red), 'interrupt'

        if self.winner_team_id is None:
            print(f"终局: 平局! 比分 {blue}:{red}")
        else:
            winner = "蓝队" if self.winner_team_id == Constants.BLUE_TEAM_ID else "红队"
            print(f"终局: {winner}队伍获胜! (原因: {self.end_type}) 比分 {blue}:{red}")
        return self.get_result()   

    def get_result(self):

        return self.winner_team_id, (self.gamestate.score[Constants.BLUE_TEAM_ID],
                                    self.gamestate.score[Constants.RED_TEAM_ID]), self.end_type

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
        self._halt()
        

    def on_foul_event(self, event: FoulEvent):
        self.foul_team_id = event.foul_team_id
        
    def on_score_event(self, event: ScoreEvent):
        self.score_team_id = event.score_team_id

    def on_end_event(self, event: EndEvent):
        self.end_type = event.end_type
        self.winner_team_id = event.success_team_id


class Replayer():
    def __init__(self, start: int, render: RenderPort, path, fps = 60):
        self.recorder = Recorder()
        self.index = start
        self.render = render
        self.event_bus = EventBus()
        self.constants = Constants()
        self.dt = 1 / fps
        self.frame_start = 0
        self.frame_elapsed = 0
        self.sleep_time = 0

        self.render.init(self.constants.GAME_SIZE, self.event_bus)
        self.recorder.open_read(path)

    def replay_loop(self):
        self.frame_start = time.perf_counter()

        self.snap = self.recorder.read(self.index)
        if self.snap is None:
            pass
        elif self.snap is False:
            return False
        else:
            self.event_bus.publish(GamePlayEvent(self.snap))

        self.index += 1

        self.frame_elapsed = time.perf_counter() - self.frame_start
        self.sleep_time = self.dt - self.frame_elapsed

        time.sleep(max(self.sleep_time, 0))

        return True
    

from ui import PygameRenderPort
from PlayerAgents import *
from EventMonitor import EventMonitor

def main(player_num: int = 4, player_agent_list: list[AgentBase] = [[emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent()],[emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent()]], team_agent_list: list[AgentBase] = [emptyTeamAgent(), emptyTeamAgent()], fps: int = 60, render: RenderPort = PygameRenderPort(1230, 1200),monitor: bool = False, record: bool = False):
    game = GameCoordinator(player_num = player_num, 
                           player_agent_list = player_agent_list, 
                           team_agent_list = team_agent_list, 
                           fps = fps, 
                           record = record)
    game.set_render(render = render)
    if monitor:
        event_monitor = EventMonitor(event_bus=game.event_bus)  #创建事件监控器实例, 不过这玩意就调试用, 不然 play 状态得吵死
    try:
        game.mainloop()
    except KeyboardInterrupt:
        game._halt(interrupt = True)

def replay(path, start: int = 0, render:RenderPort = PygameRenderPort(1230, 1200), fps: int = 60):
    running = True
    game_replay = Replayer(start = start, 
                           render = render, 
                           path = path,
                           fps = fps)
    while running:
        running = game_replay.replay_loop()

#[emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent()]
if __name__ == "__main__":
    replay('records/game_20260809_180333.jsonl', fps = 240)

