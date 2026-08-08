from DiscGame import main
from ui import PygameRenderPort
from agents.tger_agent import *




#[emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent(), emptyPlayerAgent()]
#[TgerAgent(), TgerAgent(), TgerAgent(), TgerAgent()]
if __name__ == "__main__":
    main(4, player_agent_list=[[TgerAgent(), TgerAgent(), TgerAgent(), TgerAgent()],[TgerAgent(), TgerAgent(), TgerAgent(), TgerAgent()]], team_agent_list = [TgerTeamAgent(), TgerTeamAgent()], fps=60, record = False)