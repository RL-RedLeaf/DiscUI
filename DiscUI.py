import time,math



class DiscGame:
    @staticmethod
    # 计算距离，需要标准化输入，不能应对特殊情况
    def distance(x1, y1, x2, y2):
        return ((x1 - x2) ** 2 + (y1 - y2) ** 2)**0.5

    @staticmethod
    # 用于拆分字典，需要标准化输入，不能应对特殊情况
    def divide(dic: dict):
        nk = list(dic.keys())
        nv = list(dic.values())
        former = {}
        latter = {}
        for i in range(len(nk) // 2):
            former[nk.pop(0)] = nv.pop(0)
        for j in range(len(nk)):
            latter[nk.pop(0)] = nv.pop(0)
        return [former, latter]

    def idk(self):
        #没用，但是没这个就会报错
        return 0

    def __init__(self,screen,clock,player_num,team_agent_list=None,player_agent_list=None):
        self.screen=screen
        self.clock=clock
        self.player_num=player_num
        self.team_agent_list=team_agent_list      #前半部分为1队，后半部分为2队
        self.player_agent_list=player_agent_list  #前半部分为1队，后半部分为2队

        self.running = True

        self.event_bus = EventBus()                 #事件总线，通过DiscGame类将事件总线分发给各类
        self.DiscUI=UI(self.event_bus,self.screen,self.clock)

        self.team1=Team(1,self.event_bus,team_agent_list[0],player_agent_list[0])
        self.team2=Team(2,self.event_bus,team_agent_list[1],player_agent_list[1])
        self.disc=Disc(self.event_bus)
        #创建游戏所需实体
        self.game_state=GameState({1:self.team1,2:self.team2},self.disc,self.screen)

        self.updated=[]#用于存放当前帧已经更新的实体 判断所有实体更新后再绘制
        self.update_timeout = 1000  # 更新超时时间（毫秒）
        self.last_update_time = 0  # 上次开始更新的时间

        self.subscribe_main_event() #订阅所需事件

    '''change系列函数会订阅对应的事件，接收游戏内实体的状态，以便汇总传入GameState'''
    def change_disc_state(self,event):
        # print("disc update")
        self.game_state.disc= event.disc
        self.updated.append(event.disc)
    def change_team_state(self,event):
        # print("team update")
        self.game_state.teams[event.team.team_id]=event.team
        self.updated.append(event.team)

    def change_score(self,event):
        pass

    def subscribe_main_event(self):
        self.event_bus.subscribe(TeamStateEvent,self.change_team_state)
        self.event_bus.subscribe(DiscStateEvent,self.change_disc_state)




    def start_game(self):                   #发布开始游戏事件，包含游戏得分区等信息，应被所有实体订阅
        print("game_start")
        self.event_bus.publish(GameStartEvent(
            self,None,
            {self.team1.team_id:self.player_num,self.team2.team_id:self.player_num},
            {self.team1.team_id:(0,0,60,self.screen.get_height()),self.team2.team_id:(self.screen.get_width()-60,0,60,self.screen.get_height())},
            {self.team1.team_id:[[self.screen.get_width()//2-180,self.screen.get_height()//(self.player_num+1)*(i+1)] for i in range(self.player_num+1)],
             self.team2.team_id:[[self.screen.get_width()//2+180,self.screen.get_height()//(self.player_num+1)*(j+1)] for j in range(self.player_num+1)]}
            ,self.screen
            ))
        self.event_bus.publish(self.game_state)
        while self.running:
            self.clock.tick(120)
            self.mainloop()
            time.sleep(0.006)

    def check_movement(self,event):
        return True                         #暂时不做移动检测因此直接返回true

    def mainloop(self):                     #主循环
        current_time = pygame.time.get_ticks()
        self.DiscUI.draw_new_state(self.game_state)  # 绘制界面
        if len(self.updated)>=3:
            self.updated = []
            self.last_update_time = current_time
            self.event_bus.publish(self.game_state)# 发布当前游戏状态
            # print("="*20+"tick update"+"="*20)
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
    """
    DiscThrownEvent 用于传递投出飞盘的信息，包含以下参数：
    target(disc) : 目标飞盘
    sender(player) : 投飞盘的队员
    power([x,y,h]) : 投掷飞盘的力度, 预计直接作用于速度
    """
    def __init__(self, sender, target, Power:list) -> None:
        super().__init__(sender, target)
        self.power = Power

class DiscCaughtEvent(Event):
    """
    DiscCaughtEvent 用于传递接取、夺取飞盘的事件，包含以下参数：
    target(disc) : 目标飞盘
    sender(player) : 接取、抢夺飞盘的队员
    """
    def __init__(self, sender, target):
        super().__init__(sender, target)

class DiscMovedEvent(Event):
    """
    DiscMovedEvent 是一个不知道为什么建立的事件
    但是在飞盘游戏中, 持有飞盘的运动员是不允许移动的
    但是先留着, 万一后面用到了呢? 或许以后改成篮球可以用
    """
    def __init__(self,tg_pos, sender, target=None):
        super().__init__(sender, target)
        self.tg_pos=tg_pos

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

class TeamModeEvent(Event):
    def __init__(self,mode,sender,target=None):
        super().__init__(sender,target)
        self.mode=mode


class ScoreEvent(Event):
    pass

#开始游戏事件
class GameStartEvent(Event):
    def __init__(self,sender,target,team_player_num,score_loc,pos_dict,screen,delta_time=0.016):
        super().__init__(sender,target)
        self.team_player_num=team_player_num
        self.score_loc = score_loc #得分区列表
        self.pos_dict=pos_dict
        self.delta_time=delta_time
        self.screen=screen

#实体-父类，包含位置、事件总线
class Entity:
    def __init__(self,event_bus):
        self.pos=[0,0]
        self.event_bus=event_bus
        pass

    def _move(self,pos,tg_pos):                     #内置函数，用于进行移动检测
        return True                                 #暂时不进行移动监测因此直接返回True



class Team:                             #队伍类，与队员和游戏主进程交互
    def __init__(self,team_id,event_bus,agent=None,player_agent=None):
        self.player_list=[]
        self.team_id=team_id
        self.event_bus=event_bus
        self.event_bus.subscribe(GameStartEvent,self.create_players)
        self.event_bus.subscribe(GameState,self.mainloop)
        self.running=True
        self.mode=0 #策略模式，0为进攻，1为防守
        self.new_state=0
        self.agent=agent
        self.player_agent=player_agent

    def team_agent(self,event):               #进行队伍决策,这里接受的是gamestate的event
        self.mode = self.agent.get_mode()
        self.event_bus.publish(TeamModeEvent(self.mode,self,self.player_list))

    def create_players(self,event):     #num为队员数量，pos_list为包含每位队员坐标的列表。应订阅GameStartEvent
        num=event.team_player_num[self.team_id]
        pos_list=event.pos_dict[self.team_id]
        for i in range(num):
            self.new_player = Player(i,self.team_id,pos_list[i],self.event_bus,self)
            self.new_agent = PlayerAgent(self.player_agent[i],self.new_player,self.event_bus)
            self.new_player.agent = self.new_agent
            self.player_list.append(self.new_player)
        self.event_bus.publish(TeamStateEvent(self,self))


    def mainloop(self,event):                 #团队主进程，包括更新队伍状态，进行计算/决策等
        self.agent.inform(event)
        self.team_agent(event)
        self.event_bus.publish(TeamStateEvent(self, self))


class Player(Entity):                   #队员类，不与游戏主进程进行直接交互，将信息传达至自己的team类
    def __init__(self,id,team_id,pos,event_bus,team,agent=None): #id为队员编号，team_id为队伍编号
        super().__init__(event_bus)
        self.id=id
        self.team_id=team_id
        self.pos=pos
        self.team=team
        self.agent=None
        self.event_bus.subscribe(TeamModeEvent,self.set_team_mode)
        pass

    def set_team_mode(self,event:TeamModeEvent):                     #队员自己的决策
        self.team_mode = event.mode
        self.agent.inform()

    def fetch(self,disc):
        self.event_bus.publish(DiscCaughtEvent(self,disc))

    def throw(self,disc,power):
        self.event_bus.publish(DiscThrownEvent(self,disc,power))
    

class Disc(Entity):                      #飞盘类，与游戏主线程和队员进行交互
    def __init__(self,event_bus):
        super().__init__(event_bus)
        self.pos=[0,0]
        self.state=1 #0:落地,1:在空中,2:被持有,3:正在争夺
        self.holder=None #持有者
        self.sub_holder=[]
        # self.motion=[0,0]     # 我发现这个量似乎没什么用，先留着（
        self.height=0   
        self.gravity = 9.8
        self.velocity = [0, 0, 0]  # 三维速度:[x,y,h]
        # self.mass = 1.0       # 我发现这个量似乎没什么用，先留着（
        self.event_bus.subscribe(GameStartEvent,self.create_disc)
        self.event_bus.subscribe(GameState, self.mainloop)
        self.event_bus.subscribe(DiscCaughtEvent, self.state_update)
        self.event_bus.subscribe(DiscThrownEvent, self.state_update)
        self.event_bus.subscribe(DiscMovedEvent, self.state_update)
        self.running=True

    def create_disc(self,event):
        self.delta_time = event.delta_time
        self.screen=event.screen
        self.pos=[self.screen.get_width()//2,self.screen.get_height()//2]
        self.event_bus.publish(DiscStateEvent(self,self))


    def state_update(self,event):              #与主线程进行交互，处理state事件
        # if type(event) == DiscMovedEvent: #游戏规则持盘不可移动
        #     if self.state == 2 and self.holder == event.sender:
        #         if self._move(self.pos,event.tg_pos):
        #             self.pos = event.tg_pos

        if type(event) == DiscThrownEvent:  #投掷飞盘.jpg
            if self.state == 2 and self.holder == event.sender:
                if self._check_movement(event.power):
                    self.velocity[0] += event.power[0]
                    self.velocity[1] += event.power[1]
                    self.velocity[2] += event.power[2]

        if type(event) == DiscCaughtEvent:  #投掷飞盘.jpg
            if self.state != 2:
                if self._check_catch(event):
                    self.state = 3
                    self.sub_holder.append(event.sender)

        pass

    def state_movement(self):                  #物理引擎
        if self.state == 1:
            # 应用重力
            self.velocity[2] -= self.gravity * self.delta_time
            # 更新位置
            self.pos[0] += self.velocity[0] * self.delta_time
            self.pos[1] += self.velocity[1] * self.delta_time
            self.height += self.velocity[2] * self.delta_time
            # 边界检测
            self.pos[0] = max(0, min(self.screen.get_width(), self.pos[0]))
            self.pos[1] = max(0, min(self.screen.get_height(), self.pos[1]))

            # 落地检测
            if self.height <= 0:
                # print(f"飞盘落地：三维速度([x,y,h]){self.velocity} \n 位置([x,y]):{self.pos} \n 高度:{self.height}")
                self.state = 0  # 落地状态
                self.height = 0
                self.velocity = [0, 0, 0]
            
            # print(f"飞盘物理引擎-状态更新：\n 三维速度([x,y,h]){self.velocity} \n 位置([x,y]):{self.pos} \n 高度:{self.height}")
        
        elif self.state == 2:
            pass    #我不管了反正希望在争夺盘的时候已经写好了速度重置代码，要不然就开摆（
            
        pass

    def mainloop(self,event):
        self.state_movement()#处理移动等信息

        """这里要补一个处理抢夺飞盘的逻辑, 但是空白太小写不下, 留待后人来写awa"""

        self.event_bus.publish(DiscStateEvent(self, self))

    def _check_movement(power): #检测投掷飞盘合理性
        return True
    
    def _check_catch(event):
        return True


class GameState:                         #游戏主状态，用于传达所有游戏状态，应被所有实体订阅
    def __init__(self,teams,disc:Disc,screen):
        self.teams=teams
        self.disc=disc
        self.screen=screen



import pygame.event
import pygame.draw
import pygame.display
import pygame.rect
import pygame.time
import pygame.color
import pygame.key
import pygame.surface

#使用pygame进行可视化
class UI:                                       #可视化类
    def __init__(self,event_bus,screen,clock):
        self.event_bus=event_bus
        self.screen=screen
        self.clock=clock
        # self.event_bus.subscribe(GameState,self.dr aw_new_state)
        self.event_bus.subscribe(GameStartEvent,self.set_rule)

    def set_rule(self,event):                   #初始化设置绘制规则
        self.score_loc=list(event.score_loc.values())
        print("ui_init")

    def draw_new_state(self,event):             #游戏主线程中负责可视化
        for eve in pygame.event.get():
            if eve.type == pygame.QUIT:
                pygame.quit()
        self.screen.fill('green')

        pygame.draw.rect(self.screen,(104,202,255),self .score_loc[0])  #得分区1
        pygame.draw.rect(self.screen,(255,86,86),self.score_loc[1])    #得分区2
        pygame.draw.rect(self.screen, "white", (self.screen.get_width()//2-2, 0, 4, self.screen.get_height()))#中线
        #队员
        for team in list(event.teams.values()):
            for player in team.player_list:
                pygame.draw.circle(self.screen,"blue" if player.team_id==1 else "red",player.pos,15)
        #飞碟
        pygame.draw.circle(self.screen,'yellow',event.disc.pos,10)
        pygame.draw.circle(self.screen, 'black', event.disc.pos, 10,width=1)
        pygame.display.flip()


def player_agent_tester(self,event):
    if event.sender.team_id == self.team_id:
        print(1)
    else:
        pass
def team_agent_tester(self,event):
    print(2)
    self.event_bus.publish(TeamModeEvent(self, self))


class PlayerAgent:
    def __init__(self,agent_func,player,event_bus):
        self.agent_func = agent_func
        self.event_bus = event_bus
        self.player = player
        self.memory = {}

    def inform(self,gamestate):
        self.disc = gamestate.disc
        self.information ={
            'my_position': self.player.pos,
            'my_team_id': self.player.team_id,
            'my_id': self.player.id,
            'my_memory':self.memory,
            'disc': {
                'position': gamestate.disc.pos,
                'state': gamestate.disc.state,
                'holder': gamestate.disc.holder,
                'height': gamestate.disc.height,
            },
            'teammates': [
                {'position': p.pos, 'id': p.id}
                for p in gamestate.teams[self.player.team_id].player_list
                if p.id != self.player.id
            ],
            'opponents': [
                {'position': p.pos, 'id': p.id}
                for p in gamestate.teams[3 - self.player.team_id].player_list  # 3-team_id得到对手队伍ID
            ],
            'score_zones': {
                'my_zone': (0, 0, 60, gamestate.screen.get_height()) if self.player.team_id == 1 
                          else (gamestate.screen.get_width()-60, 0, 60, gamestate.screen.get_height()),
                'opponent_zone': (gamestate.screen.get_width()-60, 0, 60, gamestate.screen.get_height()) if self.player.team_id == 1 
                                else (0, 0, 60, gamestate.screen.get_height())
            }
        }
    
    def agent(self):
        self.action = self.agent_func()
        self.act()

    def act(self):
        if 'move' in self.action:
            self.player.pos = self.action['move']
        elif 'catch' in self.action:
            self.player.fetch(self.disc)
        elif 'throw' in self.action:
            self.player.throw(self.disc,self.action['throw']['power'])
        elif 'memory_update' in self.action:
            self.memory = self.action['memory_update']

        
        pass




 



import sys
'''主程序接口'''
def game(player_num,team_agent_list=None,player_agent_list=None,testmode=False):
    pygame.init()                                   #初始化pygame
    screen = pygame.display.set_mode((980,640))
    clock = pygame.time.Clock()

    if testmode:
        player_agent_list=[[player_agent_tester for i in range(player_num)],[player_agent_tester for i in range(player_num)]]
        team_agent_list=[team_agent_tester,team_agent_tester]
    
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
    print('注意事项:\n1,使用game()函数开始一局游戏\n2,game(player_num,team_agent_list=None,player_agent_list=None\n3,team_agent_list=[team_agent1,team_agent2]\n4,player_agent_list=[[player_agent1_1,player_agent1_2,...,player_agent1_(player_num)],[player_agent2_1,player_agent2_2,...,player_agent2_(player_num)]])')

