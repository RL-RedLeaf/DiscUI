from Entity import Entity
from events import *
from systems import *
import random

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
                    # print(f"飞盘争抢：{event.sender},位置{event.sender.pos},飞盘位置{self.pos},飞盘高度{self.height},距离{DiscGame.distance(self.pos[0],self.pos[1],event.sender.pos[0],event.sender.pos[1])}")
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
        # if DiscGame.distance(self.pos[0],self.pos[1],event.sender.pos[0],event.sender.pos[1])<=30 and self.height<=2:
        #     return True
        # else:
        #     return False
        return True
