import random


class DiscGame:
    def __init__(self,screen,clock,player_num,team_agent_list=None,player_agent_list=None):
        self.screen=screen
        self.clock=clock
        self.player_num=player_num
        self.team_agent_list=team_agent_list      #前半部分为1队，后半部分为2队
        self.player_agent_list=player_agent_list  #前半部分为1队，后半部分为2队

        self.event_bus=EventBus()
        self.DiscUI=UI(self.event_bus,self.screen,self.clock)
        self.team1=Team(1,self.event_bus)
        self.team2=Team(2,self.event_bus)
        self.disc=Disc(self.event_bus)

        #创建游戏所需实体
        # print(1)
        self.subscribe_main_event()
        # self.start_game()

    def subscribe_main_event(self):
        pass

    def start_game(self):
        print("game_start")
        self.event_bus.publish(GameStartEvent(
            self,None,
            {self.team1.team_id:self.player_num,self.team2.team_id:self.player_num},
            {self.team1.team_id:(0,0,60,1280),self.team2.team_id:(1860,0,60,1280)}))

    def mainloop(self):
        self.DiscUI.draw_new_state()


class Event:
    def __init__(self,sender,target=None):
        self.sender=sender
        self.target=target



class EventBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self,event_type, callback):
        """订阅事件：当event_type事件发生时，调用callback函数"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def unsubscribe(self, event_type, callback):
        """取消订阅事件：当event_type事件发生时，不再调用callback函数"""

        self.subscribers[event_type].remove(callback)

    def publish(self, event):
        """发布事件：将事件分发给所有订阅者"""
        event_type = type(event)
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                callback(event)


class DiscThrownEvent(Event):
    pass

class DiscCaughtEvent(Event):
    pass

class DiscMovedEvent(Event):
    pass


class PlayerMovedEvent(Event):
    pass

class PlayerActionEvent(Event):
    pass


class ScoreEvent(Event):
    pass

class GameStartEvent(Event):
    def __init__(self,sender,target,team_player_num,score_loc):
        super().__init__(sender,target)
        self.team_player_num=team_player_num
        self.score_loc = score_loc #得分区列表





class Entity:
    def __init__(self,event_bus):
        self.pos=[0,0]
        self.event_bus=event_bus
        pass

    def move(self):
        pass


class Team:
    def __init__(self,team_id,event_bus):
        self.player_list=[]
        self.team_id=team_id
        self.event_bus=event_bus


    def team_agent(self):
        pass

    def create_players(self,event): #num为队员数量，pos_list为包含每位队员坐标的列表
        num=event.team_player_num[self.team_id]
        pos_list=[[0,0]*num]
        for i in range(num):
            self.player_list.append(Player(i,self.team_id,pos_list[i],self.event_bus))

        pass

    def mainloop(self):




        pass


class Player(Entity):
    def __init__(self,id,team_id,pos,event_bus): #id为队员编号，team_id为队伍编号
        super().__init__(event_bus)
        self.id=id
        self.team_id=team_id
        self.pos=pos
        pass

    def agent(self):
        pass


class Disc(Entity):
    def __init__(self,event_bus):
        super().__init__(event_bus)
        pass

    def state_update(self):
        pass

    def mainloop(self):
        pass


class GameState:
    def __init__(self,team1:Team,team2:Team,disc:Disc,screen):
        self.team1=team1
        self.team2=team2
        self.disc=disc
        self.screen=screen

import pygame
class UI:
    def __init__(self,event_bus,screen,clock):
        self.event_bus=event_bus
        self.screen=screen
        self.clock=clock
        # self.event_bus.subscribe(GameState,self.draw_new_state)
        self.event_bus.subscribe(GameStartEvent,self.set_rule)

    def set_rule(self,event):
        self.score_loc=list(event.score_loc.values())
        print("ui")
    def draw_new_state(self):
        for eve in pygame.event.get():
            if eve.type == pygame.QUIT:
                pygame.quit()
        self.screen.fill('green')
        pygame.draw.rect(self.screen,(104,202,255),self.score_loc[0])
        pygame.draw.rect(self.screen,(255,86,86),self.score_loc[1])
        pygame.draw.rect(self.screen, "white", (955, 0, 10, 1280))
        pygame.display.flip()
        self.clock.tick(60)

'''接口'''
def game(player_num,team_agent_list=None,player_agent_list=None):
    pygame.init()
    screen = pygame.display.set_mode((1920, 1280))
    clock = pygame.time.Clock()
    Game=DiscGame(screen,clock,player_num,team_agent_list,player_agent_list)
    Game.start_game()
    while True:
        clock.tick(60)
        Game.mainloop()


