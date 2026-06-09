from Entity import Entity
from events import *
from systems import *
import random

class Disc(Entity):                      #飞盘类，与游戏主线程和队员进行交互
    def __init__(self,event_bus):
        super().__init__(event_bus)
        pass

    def _inner(region,pos): #检测pos是否在region内，region格式为(x,y,w,h)
        pass

    def create_disc(self,event):
        pass

    def reset(self,event):
        pass

    def state_update(self,event):              #与主线程进行交互，处理state事件
        pass

    def state_movement(self):                  #物理引擎    
        pass
    
    def score_check(self):
        pass

    def mainloop(self,event):
        pass

    def _check_movement(self,power): #检测投掷飞盘合理性
        return True
    
    def _check_catch(self,event):
        # if DiscGame.distance(self.pos[0],self.pos[1],event.sender.pos[0],event.sender.pos[1])<=30 and self.height<=2:
        #     return True
        # else:
        #     return False
        return True
