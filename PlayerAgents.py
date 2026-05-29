from DiscUI import PlayerAgentBase,TeamAgentBase,ResetEvent
import random



class SimplePlayerAgent(PlayerAgentBase):
    '''一个非常简单的Agent示例,它会一直向飞盘移动,如果持有飞盘则向对方投掷'''
    def __init__(self):
        super().__init__()

    def init(self):
        self.event_bus.subscribe(ResetEvent, self.on_reset)  # 订阅重置事件

    def agent_func(self):
        """
        这是Agent的核心函数,必须返回一个动作字典
        """
        # 获取飞盘位置
        action = {}
        disc_pos = self.information['disc']['position']
        tgt_pos = self.information['my_position'] # 初始化目标位置
        if random.random()<0.1: 
            pass  # 10%的概率不动
        else: 
            for i in range(len(tgt_pos)):
                if tgt_pos[i]<disc_pos[i]:
                    tgt_pos[i]+=1
                elif tgt_pos[i]>disc_pos[i]:
                    tgt_pos[i]-=1
        if self.information['hold_disc']:
            # 如果持有飞盘，尝试向对方投掷
            power = [200,random.randrange(-100,100),6] if self.information['my_team_id']==0 else [-200,random.randrange(-100,100),6]  # 向对方投掷
            action['throw'] = power
        else:
            action['catch'] = True
        # 简单策略：总是向飞盘移动
        action['move'] = tgt_pos  # 移动到飞盘位置
        return action

    def on_reset(self, event):
        # 在游戏重置时清空记忆
        self.action['memory_update'] = {}
        print(f"Agent {self.player} has been reset. Memory cleared.")

class SimpleTeamAgent(TeamAgentBase):
    """简易队伍决策模型,领先就防守(0),落后就进攻(1)"""
    def __init__(self):
        super().__init__()

    def init(self):
        pass
    def agent_func(self):
        """
        """
        if self.information['my_score']>self.information['opponent_score']:
            self.set_mode(0)
        else:
            self.set_mode(1)


if __name__ == "__main__":
    from DiscUI import game, NoTeamAgent
    
    # 创建两个相同的简单Agent
    agents = [SimplePlayerAgent() for _ in range(2)]  # 4个玩家，每人一个
    
    # 启动游戏
    game(
        player_num=1,  # 每队2个玩家
        team_agent_list=[SimplePlayerAgent(), SimplePlayerAgent()],
        player_agent_list=[agents[:1], agents[1:]]  # 分配给两队
    )