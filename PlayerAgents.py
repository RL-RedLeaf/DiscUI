from DiscUI import PlayerAgentBase
import random

class SimpleAgent(PlayerAgentBase):
    def __init__(self):
        super().__init__()
    
    def agent_func(self):
        """
        这是Agent的核心函数，必须返回一个动作字典
        """
        # 获取飞盘位置
        action = {}
        disc_pos = self.information['disc']['position']
        tgt_pos = [self.player.pos[0], self.player.pos[1]]  # 初始化目标位置
        if random.random()<0: 
            tgt_pos[0]+=random.randint(-1,1)
            tgt_pos[1]+=random.randint(-1,1)
        else: 
            for i in range(len(tgt_pos)):
                if tgt_pos[i]<disc_pos[i]:
                    tgt_pos[i]+=1
                elif tgt_pos[i]>disc_pos[i]:
                    tgt_pos[i]-=1
        if self.player.hold_disc:
            # 如果持有飞盘，尝试向对方投掷
            power = [120,0,6] if self.player.team_id==0 else [-120,0,6]  # 向对方投掷
            action['throw'] = power
        else:
            action['catch'] = True
        # 简单策略：总是向飞盘移动
        action['move'] = tgt_pos  # 移动到飞盘位置
        
        return action

# 测试你的Agent
if __name__ == "__main__":
    from DiscUI import game, NoTeamAgent
    
    # 创建两个相同的简单Agent
    agents = [SimpleAgent() for _ in range(2)]  # 4个玩家，每人一个
    
    # 启动游戏
    game(
        player_num=1,  # 每队2个玩家
        team_agent_list=[NoTeamAgent(), NoTeamAgent()],
        player_agent_list=[agents[:1], agents[1:]]  # 分配给两队
    )