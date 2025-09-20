import time


class DiscGame:
    def __init__(self,screen,clock,player_num,team_agent_list=None,player_agent_list=None):
        self.screen=screen
        self.clock=clock
        self.player_num=player_num
        self.team_agent_list=team_agent_list      #前半部分为1队，后半部分为2队
        self.player_agent_list=player_agent_list  #前半部分为1队，后半部分为2队


        self.running =True

        self.event_bus=EventBus()                 #事件总线，通过DiscGame类将事件总线分发给各类
        self.DiscUI=UI(self.event_bus,self.screen,self.clock)
        self.team1=Team(1,self.event_bus)
        self.team2=Team(2,self.event_bus)
        self.disc=Disc(self.event_bus)
        #创建游戏所需实体
        self.game_state=GameState({1:self.team1,2:self.team2},self.disc,self.screen)


        self.updated=[]#用于存放当前帧已经更新的实体 判断所有实体更新后再绘制
        self.update_timeout = 1000  # 更新超时时间（毫秒）
        self.last_update_time = 0  # 上次开始更新的时间

        self.subscribe_main_event() #订阅所需事件

    '''change系列函数会订阅对应的事件，接收游戏内实体的状态，以便汇总传入GameState'''
    def change_disc_state(self,event):
        print("disc update")
        self.game_state.disc= event.disc
        self.updated.append(event.disc)
    def change_team_state(self,event):
        print("team update")
        self.game_state.teams[event.team.team_id]=event.team

        self.updated.append(event.team)

    def change_score(self,event):
        pass

    def subscribe_main_event(self):
        self.event_bus.subscribe(TeamStateEvent,self.change_team_state)
        self.event_bus.subscribe(DiscStateEvent,self.change_disc_state)
        self.event_bus.subscribe(DiscStateEvent,self.change_disc_state)



    def start_game(self):                   #发布开始游戏事件，包含游戏得分区等信息，应被所有实体订阅
        print("game_start")
        self.event_bus.publish(GameStartEvent(
            self,None,
            {self.team1.team_id:self.player_num,self.team2.team_id:self.player_num},
            {self.team1.team_id:(0,0,60,1280),self.team2.team_id:(1860,0,60,1280)},
            {self.team1.team_id:[[1920//2-180,1280//(self.player_num+1)*(i+1)] for i in range(self.player_num+1)],
             self.team2.team_id:[[1920//2+180,1280//(self.player_num+1)*(j+1)] for j in range(self.player_num+1)]}
            ))
        self.event_bus.publish(self.game_state)
        while self.running:
            self.clock.tick(60)
            self.mainloop()
            time.sleep(0.01)

    def check_movement(self,event):
        pass

    def mainloop(self):                     #主循环

        current_time = pygame.time.get_ticks()
        self.DiscUI.draw_new_state(self.game_state)  # 绘制界面
        if len(self.updated)>=3:
            self.updated = []
            self.last_update_time = current_time
            self.event_bus.publish(self.game_state)# 发布当前游戏状态
            print("="*20+"tick update"+"="*20)
        elif current_time - self.last_update_time > self.update_timeout:
            print(f"警告: 实体更新超时,将强制更新")
            for i in range(3):
                self.updated.append("Null")#使用填充物代替
            pass
        else:
            pass




class Event:
    def __init__(self,sender,target=None):
        self.sender=sender                  #事件自带信息-发布者、接受者。若接收者为None则不限
        self.target=target



class EventBus:
    def __init__(self):
        self.subscribers = {}               #订阅信息字典

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

#state系列事件应被传输给DiscGame类
#其余事件为不同实体之间传输
class DiscThrownEvent(Event):
    pass

class DiscCaughtEvent(Event):
    pass

class DiscMovedEvent(Event):
    pass

class DiscStateEvent(Event):
    def __init__(self, disc, sender, target=None):
        super().__init__(sender, target)
        self.disc = disc

class PlayerMovedEvent(Event):
    pass

class PlayerActionEvent(Event):
    pass


class TeamStateEvent(Event):

    def __init__(self,team,sender,target=None):
        super().__init__(sender,target)
        self.team=team


class ScoreEvent(Event):
    pass

#开始游戏事件
class GameStartEvent(Event):
    def __init__(self,sender,target,team_player_num,score_loc,pos_dict):
        super().__init__(sender,target)
        self.team_player_num=team_player_num
        self.score_loc = score_loc #得分区列表
        self.pos_dict=pos_dict
#实体-父类，包含位置、事件总线
class Entity:
    def __init__(self,event_bus):
        self.pos=[0,0]
        self.event_bus=event_bus
        pass

    def move(self):                     #内置函数，用于进行移动处理/检测（待定）
        pass


class Team:                             #队伍类，与队员和游戏主进程交互
    def __init__(self,team_id,event_bus):
        self.player_list=[]
        self.team_id=team_id
        self.event_bus=event_bus
        self.event_bus.subscribe(GameStartEvent,self.create_players)

        self.event_bus.subscribe(GameState,self.mainloop)
        self.running=True

    def team_agent(self):               #进行队伍决策
        pass

    def create_players(self,event):     #num为队员数量，pos_list为包含每位队员坐标的列表。应订阅GameStartEvent
        num=event.team_player_num[self.team_id]
        pos_list=event.pos_dict[self.team_id]
        for i in range(num):
            self.player_list.append(Player(i,self.team_id,pos_list[i],self.event_bus,self))
        self.event_bus.publish(TeamStateEvent(self,self))


    def mainloop(self,event):                 #团队主进程，包括更新队伍状态，进行计算/决策等
        self.event_bus.publish(TeamStateEvent(self, self))


class Player(Entity):                   #队员类，不与游戏主进程进行直接交互，将信息传达至自己的team类
    def __init__(self,id,team_id,pos,event_bus,team): #id为队员编号，team_id为队伍编号
        super().__init__(event_bus)
        self.id=id
        self.team_id=team_id
        self.pos=pos
        self.team=team
        pass

    def agent(self):                     #队员自己的决策
        pass



class Disc(Entity):                      #飞盘类，与游戏主线程和队员进行交互
    def __init__(self,event_bus):
        super().__init__(event_bus)
        self.pos=[1920//2,1280//2]
        self.state=None
        self.event_bus.subscribe(GameStartEvent,self.create_disc)
        self.event_bus.subscribe(GameState, self.mainloop)
        self.running=True
    def create_disc(self,event):
        self.event_bus.publish(DiscStateEvent(self,self))



    def state_update(self):              #与主线程进行交互，发布state事件
        pass

    def mainloop(self,event):                  #处理移动等信息

        self.event_bus.publish(DiscStateEvent(self, self))


    def state_change(self):              #与队员交互，处理状态改编事件
        pass

class GameState:                         #游戏主状态，用于传达所有游戏状态，应被所有实体订阅
    def __init__(self,teams,disc:Disc,screen):
        self.teams=teams
        self.disc=disc
        self.screen=screen



import pygame
#使用pygame进行可视化
class UI:                                       #可视化类
    def __init__(self,event_bus,screen,clock):
        self.event_bus=event_bus
        self.screen=screen
        self.clock=clock
        # self.event_bus.subscribe(GameState,self.draw_new_state)
        self.event_bus.subscribe(GameStartEvent,self.set_rule)

    def set_rule(self,event):                   #初始化设置绘制规则
        self.score_loc=list(event.score_loc.values())
        print("ui")

    def draw_new_state(self,event):             #游戏主线程中负责可视化

        for eve in pygame.event.get():
            if eve.type == pygame.QUIT:
                pygame.quit()
        self.screen.fill('green')

        pygame.draw.rect(self.screen,(104,202,255),self .score_loc[0])  #得分区1
        pygame.draw.rect(self.screen,(255,86,86),self.score_loc[1])    #得分区2
        pygame.draw.rect(self.screen, "white", (958, 0, 4, 1280))#中线
        #队员
        for team in list(event.teams.values()):
            for player in team.player_list:
                pygame.draw.circle(self.screen,"blue" if player.team_id==1 else "red",player.pos,15)
        #飞碟
        pygame.draw.circle(self.screen,'yellow',event.disc.pos,10)
        pygame.draw.circle(self.screen, 'black', event.disc.pos, 10,width=1)
        pygame.display.flip()

import sys
'''主程序接口'''
def game(player_num,team_agent_list=None,player_agent_list=None):
    pygame.init()                                   #初始化pygame
    screen = pygame.display.set_mode((1920,1280))
    clock = pygame.time.Clock()
    Game=DiscGame(                                  #创建游戏
        screen,clock,
        player_num,
        team_agent_list,player_agent_list)
    try:
        Game.start_game()
    except pygame.error:
        pass  # 防止pygame退出时报错
    except KeyboardInterrupt:
        pygame.quit()
        sys.exit()                             #开始游戏
'''导入时自动输出注意事项'''
if __name__ == "__main__":
    pass
else:
    print('注意事项:\n1,使用game()函数开始一局游戏\n2,game(player_num,team_agent_dict=None,player_agent_dict=None\n3,team_agent_dict={team_id=1:team_agent,team_id=2:team_agent}\n4,player_agent_disc={team_id:[player_agent1,player_agent2,...,player_agent(player_num)]})')

