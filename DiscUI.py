import time,random



class DiscGame:
    @staticmethod
    # 计算距离，需要标准化输入，不能应对特殊情况
    def distance(x1, y1, x2, y2,):
        return ((x1 - x2) ** 2 + (y1 - y2) ** 2)**0.5


    def __init__(self,screen,clock,player_num,team_agent_list=None,player_agent_list=None):
        self.screen=screen
        self.clock=clock
        self.player_num=player_num
        self.team_agent_list=team_agent_list      #前半部分为1队，后半部分为2队
        self.player_agent_list=player_agent_list  #前半部分为1队，后半部分为2队

        self.running = True

        self.event_bus = EventBus()                 #事件总线，通过DiscGame类将事件总线分发给各类
        self.DiscUI=UI(self.event_bus,self.screen,self.clock)

        self.team1=Team(0,self.event_bus,team_agent_list[0],player_agent_list[0])
        self.team2=Team(1,self.event_bus,team_agent_list[1],player_agent_list[1])
        self.disc=Disc(self.event_bus)
        #创建游戏所需实体
        self.game_state=GameState({0:self.team1,1:self.team2},self.disc,self.screen)

        self.updated=[]#用于存放当前帧已经更新的实体 判断所有实体更新后再绘制
        self.update_timeout = 1000  # 更新超时时间（毫秒）
        self.last_update_time = 0  # 上次开始更新的时间

        self.subscribe_main_event() #订阅所需事件

    '''change系列函数会订阅对应的事件，接收游戏内实体的状态，以便汇总传入GameState'''
    def change_disc_state(self,event) -> None:
        # print("disc update")
        self.game_state.disc= event.disc
        self.updated.append(event.disc)
    def change_team_state(self,event) -> None:
        # print("team update")
        self.game_state.teams[event.team.team_id]=event.team
        self.updated.append(event.team)

    def change_score(self,event) -> None:
        self.game_state.score[event.team_id] += 1
        print(f"得分！当前比分：{self.game_state.score}")
        self.event_bus.publish(ResetEvent(self,None,{self.team1.team_id:[[self.screen.get_width()//2-180,self.screen.get_height()//(self.player_num+1)*(i+1)] for i in range(self.player_num+1)],
             self.team2.team_id:[[self.screen.get_width()//2+180,self.screen.get_height()//(self.player_num+1)*(j+1)] for j in range(self.player_num+1)]},"score"))#发布重置事件，重置原因是得分

        
    def subscribe_main_event(self) -> None:
        self.event_bus.subscribe(TeamStateEvent,self.change_team_state)
        self.event_bus.subscribe(DiscStateEvent,self.change_disc_state)
        self.event_bus.subscribe(ScoreEvent,self.change_score)




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
    def __init__(self, sender, target, power:list) -> None:
        super().__init__(sender, target)
        self.power = power

class DiscCaughtEvent(Event):
    """
    DiscCaughtEvent 用于传递接取、夺取飞盘的事件，包含以下参数：
    target(disc) : 目标飞盘
    sender(player) : 接取、抢夺飞盘的队员
    """
    def __init__(self, sender, target):
        super().__init__(sender, target)


class DiscCaughtSuccessEvent(Event):
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
    def __init__(self,mode,gamestate,sender,target=None):
        super().__init__(sender,target)
        self.gamestate=gamestate
        self.mode=mode


class ScoreEvent(Event):
    def __init__(self, sender, target, team_id):
        super().__init__(sender, target)
        self.team_id = team_id

#开始游戏事件
class GameStartEvent(Event):
    def __init__(self,sender,target,team_player_num,score_loc,pos_dict,screen,delta_time=0.016):
        super().__init__(sender,target)
        self.team_player_num=team_player_num
        self.score_loc = score_loc #得分区列表
        self.pos_dict=pos_dict
        self.delta_time=delta_time
        self.screen=screen

class ResetEvent(Event):
    """
    ResetEvent 用于触发游戏重置，包含以下参数：
    sender(DiscGame) : 发送者
    target(None) : 接收者（广播）
    reason(str) : 重置原因（如"score"表示得分重置）
    """
    def __init__(self, sender, target=None,pos_dict=None, reason="score"):
        super().__init__(sender, target)
        self.reason = reason
        self.pos_dict =pos_dict #重置后玩家位置列表



#实体-父类，包含位置、事件总线
class Entity:
    def __init__(self,event_bus):
        self.pos=[0,0]
        self.event_bus=event_bus
        pass




class Team:                             #队伍类，与队员和游戏主进程交互
    def __init__(self,team_id,event_bus,agent,player_agent:list):
        self.player_list=[]
        self.team_id=team_id
        self.event_bus=event_bus
        self.event_bus.subscribe(GameStartEvent,self.create_players)
        self.event_bus.subscribe(GameState,self.mainloop)
        self.event_bus.subscribe(ResetEvent,self.reset)
        self.running=True
        self.mode=0 #策略模式
        self.agent=agent
        self.agent.team = self
        self.agent.event_bus = self.event_bus
        self.player_agent=player_agent

    
    def reset(self,event):
        self.mode=0 #重置策略模式
        for player in self.player_list:
            player.pos = event.pos_dict[self.team_id][player.id]
            player.hold_disc = None
    def team_agent(self,event):               #进行队伍决策,这里接受的是gamestate的event
        self.agent.agent_func()
        self.mode = self.agent.get_mode()
        self.event_bus.publish(TeamModeEvent(self.mode,event,self,self.player_list))

    def create_players(self,event):     #num为队员数量，pos_list为包含每位队员坐标的列表。应订阅GameStartEvent
        num=event.team_player_num[self.team_id]
        pos_list=event.pos_dict[self.team_id]
        for i in range(num):
            self.new_player = Player(i,self.team_id,pos_list[i],self.event_bus,self,self.player_agent[i])
            self.new_agent = self.player_agent[i]
            self.new_agent.player = self.new_player
            # self.new_agent.event_bus = self.event_bus
            self.new_agent.init()#玩家智能体初始化
            self.player_list.append(self.new_player)
        self.agent.init()#队伍智能体初始化
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
        self.agent=agent
        self.event_bus.subscribe(TeamModeEvent,self.main)
        self.event_bus.subscribe(DiscCaughtSuccessEvent,self.set_disc)
        self.hold_disc = None

    def __str__(self):
        return f"TeamMember:{self.id} from Team:{self.team_id}"
    
    def _move(self,pos,tg_pos):                     #内置函数，用于进行移动检测
        # print(self,' holds ',self.hold_disc)
        if self.hold_disc is None:
            return True      
        else:
            # print(self,' holds ',self.hold_disc)
            return False                           

    def set_disc(self,event:DiscCaughtSuccessEvent):
        if event.target == self:
            self.hold_disc = event.sender

    def main(self,event:TeamModeEvent):                     #队员自己的决策
        self.team_mode = event.mode
        self.agent.inform(event.gamestate)
        self.agent.agent()
    def fetch(self,disc):
        self.event_bus.publish(DiscCaughtEvent(self,disc))

    def move(self,tg_pos):
        if self._move(self.pos,tg_pos):
            # for i in range(len(tg_pos)):
            #     tg_pos[i] += (random.random() - 0.5) * 2 #增加随机扰动
            self.pos = tg_pos
    def throw(self,disc,power):
        if self.hold_disc is None:
            return 0
        else:
            # for i in range(len(power)):
            #     power[i] *= random.uniform(0.7, 1.3) #增加随机扰动
            self.event_bus.publish(DiscThrownEvent(self,disc,power))
            self.hold_disc = None

    

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
        self.event_bus.subscribe(ResetEvent,self.reset)
        self.running=True

    @staticmethod
    def _inner(region,pos): #检测pos是否在region内，region格式为(x,y,w,h)
        if region[0]<=pos[0]<=region[0]+region[2] and region[1]<=pos[1]<=region[1]+region[3]:
            return True
        else:
            return False
    def create_disc(self,event):
        self.delta_time = event.delta_time
        self.screen=event.screen
        self.pos=[self.screen.get_width()//2,self.screen.get_height()//2]
        self.score_loc = event.score_loc
        self.event_bus.publish(DiscStateEvent(self,self))

    def reset(self,event):
        self.pos=[self.screen.get_width()//2,self.screen.get_height()//2]
        self.state=0
        self.holder=None
        self.sub_holder=[]
        self.height=0   
        self.velocity = [0, 0, 0]  # 三维速度:[x,y,h]
    def state_update(self,event):              #与主线程进行交互，处理state事件
        # if type(event) == DiscMovedEvent: #游戏规则持盘不可移动
        #     if self.state == 2 and self.holder == event.sender:
        #         if self._move(self.pos,event.tg_pos):
        #             self.pos = event.tg_pos

        if type(event) == DiscThrownEvent:  #投掷飞盘.jpg
            if self.state == 2 and self.holder == event.sender:
                if self._check_movement(event.power):
                    print(f"飞盘投掷：{event.sender},位置{event.sender.pos},投掷力度{event.power}")
                    self.state = 1
                    self.velocity[0] += event.power[0]
                    self.velocity[1] += event.power[1]
                    self.velocity[2] += event.power[2]
                    self.height += 3 #投掷时飞盘会有一个初始高度，防止被自己投出的飞盘砸到（
                    self.holder = None 
                    self.sub_holder =[] #我是傻子我怎么忘了在扔飞盘的时候清空飞盘所有者列表来着
                    

        if type(event) == DiscCaughtEvent:  #抓取飞盘.jpg
            if self.state != 2:
                if self._check_catch(event):
                    print(f"飞盘争抢：{event.sender},位置{event.sender.pos},飞盘位置{self.pos},飞盘高度{self.height},距离{DiscGame.distance(self.pos[0],self.pos[1],event.sender.pos[0],event.sender.pos[1])}")
                    self.state = 3
                    self.sub_holder.append(event)

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
    
    def score_check(self):
        if self._inner(self.score_loc[0],self.pos):  #进入1队得分区
            self.event_bus.publish(ScoreEvent(self,None,1))
        elif self._inner(self.score_loc[1],self.pos):  #进入0队得分区
            self.event_bus.publish(ScoreEvent(self,None,0))
        else:
            pass

    def mainloop(self,event):
        self.state_movement()#处理移动等信息
        self.score_check()#处理得分
        if self.state == 3:
            self.holder = self.sub_holder[random.randrange(0,len(self.sub_holder))].sender          #处理飞盘抢夺。我选择直接随机（
            self.state = 2
            self.event_bus.publish(DiscCaughtSuccessEvent(self,self.holder))
            print(f"飞盘被抢：{self.holder}")
            self.pos = self.holder.pos
            
        """这里要补一个处理抢夺飞盘的逻辑, 但是空白太小写不下, 留待后人来写awa"""

        self.event_bus.publish(DiscStateEvent(self, self))

    def _check_movement(self,power): #检测投掷飞盘合理性
        return True
    
    def _check_catch(self,event):
        if DiscGame.distance(self.pos[0],self.pos[1],event.sender.pos[0],event.sender.pos[1])<=30 and self.height<=2:
            return True
        else:
            return False


class GameState:                         #游戏主状态，用于传达所有游戏状态，应被所有实体订阅
    def __init__(self,teams,disc:Disc,screen):
        self.teams=teams
        self.disc=disc
        self.screen=screen
        self.score={0:0,1:0}



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
        self.font = pygame.font.SysFont('SimHei',40,bold=True) # 系统字体
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
                pygame.draw.circle(self.screen,"blue" if player.team_id==0 else "red",player.pos,15)
        #飞碟
        pygame.draw.circle(self.screen,'yellow',event.disc.pos,10)
        pygame.draw.circle(self.screen, 'black', event.disc.pos, 10,width=1)
        
        self.score_text_surface = self.font.render(f"{event.score[0]}  {event.score[1]}", True, (0,0,0))
        self.screen.blit(self.score_text_surface, (self.screen.get_width()//2 - self.score_text_surface.get_width()//2, 10))

        pygame.display.flip()


class PlayerAgentBase:
    def __init__(self):
        self.event_bus = None
        self.player:Player = None
        self.memory = {}

    def init(self):
        self.event_bus = self.player.event_bus


    def inform(self,gamestate):
        self.disc = gamestate.disc
        self.information ={
            'my_position': self.player.pos.copy(),
            'my_team_id': self.player.team_id,
            'my_id': self.player.id,
            'my_memory':self.memory,
            'hold_disc': False if self.player.hold_disc is None else True,
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
                for p in gamestate.teams[1 - self.player.team_id].player_list  # 1-team_id得到对手队伍ID
            ],
            'score_zones': {
                'my_zone': (0, 0, 60, gamestate.screen.get_height()) if self.player.team_id == 1 
                          else (gamestate.screen.get_width()-60, 0, 60, gamestate.screen.get_height()),
                'opponent_zone': (gamestate.screen.get_width()-60, 0, 60, gamestate.screen.get_height()) if self.player.team_id == 1 
                                else (0, 0, 60, gamestate.screen.get_height())
            },
            'score': gamestate.score.copy()
        }
    
    def agent(self):
        self.action = self.agent_func()
        self.act()

    def agent_func(self):
        pass

    def act(self):
        if 'move' in self.action:
            self.player.move(self.action['move'])
        if 'catch' in self.action:
            self.player.fetch(self.disc)
        if 'throw' in self.action:
            self.player.throw(self.disc,self.action['throw'])
        if 'memory_update' in self.action:
            self.memory = self.action['memory_update']



class TeamAgentBase:
    def __init__(self):
        # self.agent_func = None
        self.event_bus = None
        self.team = None
        self.memory = {}
        self.mode = 0
    def init(self):
        self.event_bus = self.team.event_bus

    def inform(self,gamestate):
        self.disc = gamestate.disc
        for i in gamestate.teams.keys():
            if gamestate.teams[i].team_id != self.team.team_id:
                self.oppose_team = gamestate.teams[i]
        
        self.information ={
            'my_team_id': self.team.team_id,
            'oppose_team_id': self.oppose_team.team_id,
            'my_memory':self.memory,
            'disc': {
                'position': gamestate.disc.pos,
                'state': gamestate.disc.state,
                'holder': gamestate.disc.holder,
                'height': gamestate.disc.height,
            },
            'teammates': [
                {'position': p.pos, 'id': p.id}
                for p in gamestate.teams[self.team.team_id].player_list
            ],
            'opponents': [
                {'position': p.pos, 'id': p.id}
                for p in gamestate.teams[1 - self.team.team_id].player_list  # 1-team_id得到对手队伍ID
            ],
            'score_zones': {
                'my_zone': (0, 0, 60, gamestate.screen.get_height()) if self.team.team_id == 1 
                          else (gamestate.screen.get_width()-60, 0, 60, gamestate.screen.get_height()),
                'opponent_zone': (gamestate.screen.get_width()-60, 0, 60, gamestate.screen.get_height()) if self.team.team_id == 1 
                                else (0, 0, 60, gamestate.screen.get_height())
            },
            'score': gamestate.score.copy()
        }
    
    def agent_func(self):
        pass

    def set_mode(self,mode):
        self.mode = mode

    def get_mode(self):
        return self.mode




import sys
'''主程序接口'''


class ControlledPlayerAgent(PlayerAgentBase):
    def __init__(self):
        super().__init__()
    def agent_func(self):
        action = {}
        keys = pygame.key.get_pressed()
        dt = 1/60
        SPEED = 30
        tgt_pos = [self.player.pos[0], self.player.pos[1]]
        if keys[pygame.K_w]:
            tgt_pos[1] -= SPEED * dt
        if keys[pygame.K_s]:
            tgt_pos[1] += SPEED * dt
        if keys[pygame.K_a]:
            tgt_pos[0] -= SPEED * dt
        if keys[pygame.K_d]:
            tgt_pos[0] += SPEED * dt
        action['move'] = tgt_pos
        if keys[pygame.K_q] and self.disc.holder == self.player:        
            action['throw'] = [random.randint(-75,75),random.randint(-75,75),random.randint(10,20)]
            print("throw",action['throw'])
        elif keys[pygame.K_SPACE]:
            action['catch'] = True
            # print("catch")
                
        return action
    pass

class NoTeamAgent(TeamAgentBase):
    def __init__(self):
        super().__init__()

    def agent(self,event):
        pass

    # def agent_func(self):
    #     pass



def game(player_num,team_agent_list,player_agent_list):
    pygame.init()                                   #初始化pygame
    screen = pygame.display.set_mode((980,640))
    clock = pygame.time.Clock()
    
    # if testmode:
    #     player_agent_list=[[PlayerAgent() for i in range(player_num)],[PlayerAgent() for i in range(player_num)]]
    #     team_agent_list=[TeamAgent(),TeamAgent()]
    
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

