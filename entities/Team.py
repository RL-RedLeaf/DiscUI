from events import *
from systems import *
from Entity import Entity

class Team:                             #队伍类，与队员和游戏主进程交互
    def __init__(self,team_id,event_bus,agent,player_agent:list):
        pass

    
    def reset(self,event):
        pass

    def team_agent(self,event):               #进行队伍决策,这里接受的是gamestate的event
        pass

    def create_players(self,event):     #num为队员数量，pos_list为包含每位队员坐标的列表。应订阅GameStartEvent
        pass



    def mainloop(self,event):                 #团队主进程，包括更新队伍状态，进行计算/决策等
        pass


class Player(Entity):                   #队员类，不与游戏主进程进行直接交互，将信息传达至自己的team类
    def __init__(self,id,team_id,pos,event_bus,team,agent=None): #id为队员编号，team_id为队伍编号
        pass

    def __str__(self):
        pass
    
    def _move(self,pos,tg_pos):                     #内置函数，用于进行移动检测
        pass              

    def set_disc(self,event:DiscCaughtSuccessEvent):
        pass

    def fetch(self,disc):
        pass

    def move(self,tg_pos):
        pass

    def throw(self,disc,power):
        pass