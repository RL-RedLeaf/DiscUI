from DiscGame import main
from ui import PygameRenderPort
from agents.tger_agent import *

player_num = 7


#[emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent()]
#[TgerAgent(), TgerAgent(), TgerAgent(), TgerAgent()]
if __name__ == "__main__":
    main(player_num, player_agent_list=[[TgerAgent() for i in range(player_num)], [TgerAgent() for i in range(player_num)]], team_agent_list = [TgerTeamAgent() for i in range(2)], fps=60, record = False)