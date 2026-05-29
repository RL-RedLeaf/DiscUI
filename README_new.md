# DiscUI - 飞盘游戏智能体框架

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-windows%20|%20linux%20|%20macos-lightgrey)](https://pypi.org/project/pygame/)

DiscUI 是一个轻量级的飞盘游戏框架。作者受到一个名为CardUI的牌类游戏框架启发，开发了这款为智能体设计的飞盘框架（当然你要手操也没问题awa）。支持用户自定义编写智能体（agent），并可以开发和测试不同的策略或行为逻辑。

## 目录

## 快速开始

### 环境要求

- Python 3.6+

### 安装依赖

```bash
pip install pygame
```

### 基本使用

飞盘框架主体逻辑位于 `DiscUI.py` , 主入口位于 `game()` ，`main.py` 提供了一个使用示例。而 `PlayerAgent.py` 存放了一些基础的Agent（其实`DiscUI.py`中也内置了两个Agent）。

* 主入口`game()` 
```python
def game(player_num: int, team_agent_list: list, player_agent_list: list) -> None:
    pygame.init()                              #初始化pygame
    screen = pygame.display.set_mode((980,640))
    ...
```

* 调用示例
```python
import DiscUI                                   #导入模块
from DiscUI import ControlledPlayerAgent, NoTeamAgent
                                                #内置两个简易Agent(键盘操控玩家 & 无团队策略)
from PlayerAgents import SimplePlayerAgent, SimpleTeamAgent
                                                #PlayerAgents模块提供两个简单的策略Agent
player_num = 2                                  #设定玩家数量

player_agent_list = [[SimplePlayerAgent() for i in range(player_num)],
                     [ControlledPlayerAgent() for i in range(player_num)]]

team_agent_list = [NoTeamAgent(),NoTeamAgent()]
                                                #创建Agent实例
DiscUI.game(player_num = player_num,
            team_agent_list = team_agent_list,
            player_agent_list = player_agent_list)
                                                #调用主入口函数，传入对应参数
```

### 默认控制键位

使用 `ControlledPlayerAgent` 时的默认控制：

| 按键 | 功能 |
|------|------|
| W/A/S/D | 移动玩家 |
| 空格键 | 尝试接住飞盘 |
| Q键 | 投掷飞盘（需持有飞盘） |

## 架构说明

- 本框架架构由我和Deepseek的交流而形成，加以不全面不到位的实施，因此架构显得十分繁琐，堪称 **史山**
- 本架构尝试使用 **事件总线** 以实现各个组件之间的解耦。幸运的是，我们并没有成功（

### 核心组件

```
DiscUI/
├── DiscGame        # 游戏主控制器
├── EventBus        # 事件总线系统
├── Team            # 队伍管理器
├── Player          # 玩家实体
├── Disc            # 飞盘物理引擎
├── UI              # 可视化界面
└── Agent基类       # 策略接口
```

### 事件驱动架构

系统采用发布-订阅模式进行组件通信:

```python
# 订阅事件
event_bus.subscribe(EventType, callback_function)

# 发布事件
event_bus.publish(event_object)
```

事件总线调用方式:

```python
    def publish(self, event):
        """发布事件：将事件分发给所有订阅者"""
        event_type = type(event)
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                callback(event)
```


### 主要事件类型

| 事件类型 | 用途 | 触发条件 |
|---------|------|----------|
| `GameStartEvent` | 游戏初始化 | 游戏开始时 |
| `GameStateEvent` | 游戏总状态 | 每一游戏刻（驱动游戏整体运行） |
| `DiscStateEvent` | 飞盘状态更新 | 飞盘位置或状态改变 |
| `TeamStateEvent` | 队伍状态更新 | 队伍信息变更 |
| `DiscThrownEvent` | 飞盘投掷 | 队员尝试投掷飞盘 |
| `DiscCaughtEvent` | 飞盘接住 | 队员尝试接住飞盘 |


## API参考

### 主函数

#### `game(player_num, team_agent_list, player_agent_list)`

启动飞盘游戏

**参数:**
- `player_num` (int): 每队玩家数量
- `team_agent_list` (list): 队伍agent列表 `[team1_agent, team2_agent]`
- `player_agent_list` (list): 玩家agent嵌套列表 `[[team1_players], [team2_players]]`

### Agent基类

#### PlayerAgentBase

```python
class MyPlayerAgent(PlayerAgentBase):
    def agent_func(self):
        # 访问游戏信息
        info = self.information
        # 返回动作指令
        return {'move': [x, y], 'catch': True}
```

#### TeamAgentBase

```python
class MyTeamAgent(TeamAgentBase):
    def get_mode(self):
        return 0  # 0=进攻, 1=防守
    
    def agent(self, gamestate):
        # 队伍级别决策
        pass
```

### 游戏信息结构

玩家agent可访问的游戏状态信息:
```python
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
```

队伍agent可访问的游戏状态信息: