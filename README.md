# DiscUI - 飞盘游戏智能体框架

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos-lightgrey)](https://pypi.org/project/pygame/)

DiscUI 是一个轻量级的飞盘游戏框架，专为AI研究和智能体开发而设计。支持用户自定义编写智能体（agent），便于开发和测试不同的策略或行为逻辑。

## 📋 目录

- [✨ 特性](#-特性)
- [🚀 快速开始](#-快速开始)
- [🎮 使用示例](#-使用示例)
- [🏗️ 架构说明](#️-架构说明)
- [🔧 API参考](#-api参考)
- [📚 开发指南](#-开发指南)
- [🤝 贡献指南](#-贡献指南)
- [📄 许可证](#-许可证)

## ✨ 特性

- 🎯 **模块化设计** - 易于扩展和定制的插件式架构
- 🤖 **智能体支持** - 完整的Agent基类，支持自定义策略开发
- 🎮 **可视化界面** - 基于pygame的实时游戏画面渲染
- ⚡ **事件驱动** - 高效的发布-订阅模式实现组件间通信
- 🔧 **灵活配置** - 支持多玩家、多队伍的自定义配置

## 🚀 快速开始

### 环境要求

- Python 3.6+
- pip 包管理器

### 安装依赖

```bash
pip install pygame
```


### 基本使用

创建一个简单的游戏实例：

```python
import DiscUI
from DiscUI import ControlledPlayerAgent, NoTeamAgent

# 设置每队玩家数量
player_num = 2

# 创建玩家agent列表
player_agent_list = [
    [ControlledPlayerAgent() for i in range(player_num)],  # 队伍1
    [ControlledPlayerAgent() for i in range(player_num)]   # 队伍2
]

# 创建队伍agent列表
team_agent_list = [NoTeamAgent(), NoTeamAgent()]

# 启动游戏
DiscUI.game(
    player_num=player_num,
    team_agent_list=team_agent_list,
    player_agent_list=player_agent_list
)
```

## 🎮 使用示例

### 默认控制键位

使用 `ControlledPlayerAgent` 时的默认控制：

| 按键 | 功能 |
|------|------|
| W/A/S/D | 移动玩家 |
| 空格键 | 尝试接住飞盘 |
| Q键 | 投掷飞盘（需持有飞盘） |


## 🏗️ 架构说明

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

系统采用发布-订阅模式进行组件通信：

```python
# 订阅事件
event_bus.subscribe(EventType, callback_function)

# 发布事件
event_bus.publish(event_object)
```

### 主要事件类型

| 事件类型 | 用途 | 触发条件 |
|---------|------|----------|
| `GameStartEvent` | 游戏初始化 | 游戏开始时 |
| `DiscStateEvent` | 飞盘状态更新 | 飞盘位置或状态改变 |
| `TeamStateEvent` | 队伍状态更新 | 队伍信息变更 |
| `DiscThrownEvent` | 飞盘投掷 | 玩家投掷飞盘 |
| `DiscCaughtEvent` | 飞盘接住 | 玩家成功接住飞盘 |

## 🔧 API参考

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

玩家agent可访问的游戏状态信息：

```python
{
    'my_position': [x, y],           # 当前位置
    'my_team_id': 1,                 # 队伍ID (1或2)
    'my_id': 0,                      # 玩家ID
    'disc': {
        'position': [x, y],          # 飞盘位置
        'state': 1,                  # 状态 (0=落地,1=空中,2=持有,3=争夺)
        'holder': Player对象,        # 当前持有者
        'height': 0                  # 飞盘高度
    },
    'teammates': [                   # 队友信息
        {'position': [x, y], 'id': 1}
    ],
    'opponents': [                   # 对手信息
        {'position': [x, y], 'id': 0}
    ],
    'score_zones': {                 # 得分区域
        'my_zone': (x, y, width, height),
        'opponent_zone': (x, y, width, height)
    }
}
```

## 📚 开发指南

### 创建高级玩家策略

```python
class AdvancedPlayerAgent(PlayerAgentBase):
    def __init__(self):
        super().__init__()
        self.strategy = "chase_disc"  # 默认策略
        self.target_position = None
        
    def agent_func(self):
        action = {}
        
        # 根据不同情况选择策略
        if self._should_pass():
            action['throw'] = self._calculate_pass()
            self.strategy = "passing"
        elif self._should_catch():
            action['catch'] = True
            self.strategy = "catching"
        else:
            # 默认追逐飞盘
            target = self._find_best_position()
            action['move'] = target
            
        return action
        
    def _should_pass(self):
        # 判断是否应该传球的逻辑
        return (self.disc.holder == self.player and 
                len(self.information['teammates']) > 0)
                
    def _calculate_pass(self):
        # 计算传球力度
        teammate = self.information['teammates'][0]
        dx = teammate['position'][0] - self.player.pos[0]
        dy = teammate['position'][1] - self.player.pos[1]
        return [dx * 0.5, dy * 0.5, 15]  # 添加垂直分量
```

### 队伍协调策略

```python
class CoordinatedTeamAgent(TeamAgentBase):
    def __init__(self):
        super().__init__()
        self.offensive_positions = []
        self.defensive_positions = []
        
    def get_mode(self):
        # 根据控盘情况切换模式
        holder = self.game_state.disc.holder
        if holder and holder.team_id == self.team_id:
            return 0  # 进攻模式
        else:
            return 1  # 防守模式
            
    def agent(self, gamestate):
        # 分析场上形势，调整队伍策略
        self._update_positions(gamestate)
        
    def _update_positions(self, gamestate):
        # 根据游戏状态更新理想站位
        if self.get_mode() == 0:  # 进攻
            self._set_offensive_formation(gamestate)
        else:  # 防守
            self._set_defensive_formation(gamestate)
```

## 🤝 贡献指南

欢迎任何形式的贡献！请遵循以下步骤：

1. **Fork** 项目到您的GitHub账户
2. **创建特性分支**: `git checkout -b feature/AmazingFeature`
3. **提交更改**: `git commit -m 'Add some AmazingFeature'`
4. **推送分支**: `git push origin feature/AmazingFeature`
5. **开启Pull Request**

### 开发环境设置

```bash
# 克隆项目
git clone https://github.com/your-username/DiscUI.git
cd DiscUI

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装开发依赖
pip install pygame
```

### 代码规范

- 遵循PEP 8 Python编码规范
- 函数和类需要适当的文档字符串
- 保持代码简洁和可读性
- 添加必要的类型提示

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

<p align="center">
  我的第一款石山代码(2026)
</p>

