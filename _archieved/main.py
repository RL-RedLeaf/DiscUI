import _archieved.DiscUI as DiscUI
from _archieved.DiscUI import ControlledPlayerAgent,NoTeamAgent




player_num=2

player_agent_list=[[ControlledPlayerAgent() for i in range(player_num)],[ControlledPlayerAgent() for i in range(player_num)]]
team_agent_list=[NoTeamAgent(),NoTeamAgent()]

DiscUI.game(player_num=player_num,team_agent_list=team_agent_list,player_agent_list=player_agent_list)
