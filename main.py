from DiscGame import GameCoordinator
from ui import PygameRenderPort
from PlayerAgents import *
from agents.tger_agent import *


#[emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent()]
if __name__ == "__main__":
    game = GameCoordinator(4, player_agent_list=[[TgerAgent(), TgerAgent(), TgerAgent(), TgerAgent()],[TgerAgent(), TgerAgent(), TgerAgent(), TgerAgent()]], fps=60)
    game.set_render(PygameRenderPort(1230, 1200))

    # from EventMonitor import EventMonitor
    # event_monitor = EventMonitor(event_bus=game.event_bus)  #创建事件监控器实例, 不过这玩意就调试用, 不然 play 状态得吵死
    try:
        game.mainloop()
    except KeyboardInterrupt:
        print('游戏已被外部中断(说, 是不是你自己手贱按了ctrl+C!)')