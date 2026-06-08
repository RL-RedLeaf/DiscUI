class Event:
    def __init__(self,sender,target=None):
        self.sender=sender                  #事件自带信息-发布者、接受者。若接收者为None则不限
        self.target=target


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

