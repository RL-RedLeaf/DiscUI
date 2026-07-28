# DiscUI - 飞盘游戏智能体框架

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-windows%20|%20linux%20|%20macos-lightgrey)](https://pypi.org/project/pygame/)

DiscUI 是一个 **~~“轻量级”~~** 的飞盘游戏框架，专为智能体设计（当然你也可以用来手操awa）。支持用户自定义编写智能体（agent），并可以开发和测试不同的策略或行为逻辑。
DiscUI 还支持使用不同渲染器来查看游戏对局（支持自定义），也自带 pygame 渲染器

## 目录

- [快速开始](#快速开始)
- [架构说明](#架构说明)
- [API参考](#API参考)
- [代码规范](#代码规范)
- [许可证](#许可证)

## 快速开始

### 环境要求

- Python 3.10+
- pygame (如果你想使用自带渲染器的话)

### 安装依赖

```bash
pip install pygame
```

### 基本使用

飞盘框架主入口位于 `DiscGame.py` 的 `GameCoordinator` 。`PlayerAgents.py` 存放了一些基础的Agent。框架现在不再区分队伍agent和玩家agent，每个玩家直接绑定一个agent实例。

* 主入口`GameCoordinator`
```python
class GameCoordinator:
    def __init__(self, player_num: int, player_agent_list: list[list], fps: int):
        ...
```
**参数:**
- `player_num` (int): 每队玩家数量
- `player_agent_list` (list[list]): 两队agent嵌套列表，第一项为蓝队，最后一项为红队
- `fps` (int): 帧率，同时决定 `delta_time`

* 调用示例
```python
from DiscGame import GameCoordinator
from PlayerAgents import emptyPlayerAgent
from ui import PygameRenderPort

player_num = 4
player_agent_list = [
    [emptyPlayerAgent() for _ in range(player_num)],
    [emptyPlayerAgent() for _ in range(player_num)],
]

game = GameCoordinator(player_num, player_agent_list, fps=60)
game.set_render(PygameRenderPort(1230, 1200))
game.mainloop()
```

### 内置 Agent

`PlayerAgents.py` 提供了一个空 Agent：

```python
class emptyPlayerAgent(AgentBase):
    def init(self, player_key):
        self.player_key = player_key

    def agent(self, gamestate):
        return []   # 什么都不做
```

把你自己的 Agent 替换进去就能看到效果了，具体写法见 API 参考。

## 架构说明

- 本框架架构由我和Deepseek的交流而形成，加以不全面不到位的实施，因此架构显得十分繁琐，堪称 **史山**
- 本架构尝试使用 **事件总线** 以实现各个组件之间的解耦。幸运的是，我们并没有成功（

### 核心组件

```
DiscUI/
├── DiscGame.py          # 游戏协调器、状态机、主循环
├── PlayerAgents.py      # 内置示例 agent
├── EventMonitor.py      # 事件打印工具
├── config/
│   └── Constants.py     # 场地、速度、接盘等常量
├── entities/
│   ├── Disc.py          # 飞盘实体与快照
│   ├── Team.py          # 队伍、玩家、PlayerKey
│   └── Entity.py        # 实体基类
├── events/
│   └── Events.py        # 事件类型定义
├── systems/
│   ├── ActionSystem.py  # Agent 调度、动作校验与执行
│   ├── EventBus.py      # 事件总线
│   ├── GameState.py     # 游戏状态与只读快照
│   ├── PhysicSystem.py  # 飞盘物理更新
│   └── RuleSystem.py    # 得分、犯规、出界等规则
├── ui/
│   ├── port.py          # RenderPort 接口
│   └── pygame_adapter.py# pygame 渲染实现
└── Docs/                # 设计文档与规则说明
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
| `GameStartEvent` | 游戏初始化 | START 阶段完成 |
| `GamePlayEvent` | 游戏状态广播 | 每帧 PLAY 开始时 |
| `FoulEvent` | 比赛犯规 | 身体接触、超时、落地、出界 |
| `ScoreEvent` | 队伍得分 | 持盘者进入对方得分区 |
| `DiscCatchEvent` | 飞盘被接住 | 争抢结算确定持盘者 |
| `ResetEvent` | 比赛重置 | 得分或犯规后重置发盘 |


## API参考

### GameCoordinator

#### `GameCoordinator(player_num, player_agent_list, fps)`

创建比赛实例。

**参数:**
- `player_num` (int): 每队玩家数量
- `player_agent_list` (list[list]): 两队 agent 嵌套列表，`[蓝队agent列表, 红队agent列表]`
- `fps` (int): 目标帧率，同时决定 `delta_time = 1 / fps`

**方法:**
- `set_render(render)` - 设置渲染器，需要在 `mainloop()` 前调用
- `mainloop()` - 启动主循环

### Agent 基类

自定义 agent 需要继承 `systems.AgentBase`：

```python
from entities import PlayerKey
from systems import AgentBase, GameStateSnap, MoveIntent, ThrowIntent, CatchIntent

class MyAgent(AgentBase):
    def init(self, player_key: PlayerKey):
        # 初始化时绑定身份
        self.player_key = player_key

    def agent(self, gamestate: GameStateSnap) -> list:
        # 接收只读快照，返回 Intent 列表
        return []
```

**`init(player_key)`** 在 `ActionSystem.setup()` 中被调用，用于 agent 初始化。

**`agent(gamestate)`** 每帧接收一个 `GameStateSnap`，返回 Intent 列表。返回空列表时本帧不作任何动作。所有 agent 并行调用，单帧超时 10ms。

#### Intent 类型

| Intent | 字段 | 说明 |
|--------|------|------|
| `MoveIntent` | `target_pos: tuple[int]` 长度 2 | 移动玩家到目标 (x, y)，仅限未持盘 |
| `ThrowIntent` | `disc_id: int`, `motion: tuple[int]` 长度 3 | 以速度 (vx, vy, vz) 抛盘，需持盘 |
| `CatchIntent` | `disc_id: int` | 请求接住飞盘，满足距离和高度条件后加入争抢 |

### GameStateSnap（只读快照）

agent 和渲染器只能访问冻结的 `GameStateSnap`：

```python
@dataclass(frozen=True)
class GameStateSnap:
    disc: DiscSnap              # 飞盘快照
    team_list: tuple[TeamSnap]  # 两队快照
    delta_time: float           # 本帧时间步长
    const: Constants            # 游戏常量
    score: tuple                # (蓝队比分, 红队比分)
    tick: int                   # 当前帧数
```

#### DiscSnap

```python
@dataclass(frozen=True)
class DiscSnap:
    pos: tuple[float, float, float]           # 三维坐标 (x, y, z)
    holder_key: PlayerKey | None              # 当前持盘者
    velocity: tuple[float, float, float]       # 三维速度
    state: str                                # 飞盘状态
```

飞盘 `state` 取值：`"waiting"`（等待接盘）、`"flying"`（飞行）、`"competing"`（争抢中）、`"catched"`（被持有）、`"ground"`（落地）。

#### TeamSnap / PlayerSnap

```python
@dataclass(frozen=True)
class TeamSnap:
    team_id: int
    player_num: int
    player_list: tuple[PlayerSnap]

@dataclass(frozen=True)
class PlayerSnap:
    player_key: PlayerKey
    pos: tuple[int, int]       # 二维坐标 (x, y)
    hold_disc: bool            # 是否持盘
```

`PlayerKey(team_id, player_id)` 是玩家唯一标识，分别通过 `team_id` 和 `player_id` 索引到具体玩家：

```python
player = gamestate.team_list[player_key.team_id].player_list[player_key.player_id]
```

## 代码规范

- 不一定遵循PEP 8 Python编码规范
- 函数和类未必需要适当的文档字符串
- 可能会保持代码简洁和可读性
- 可能会添加必要的类型提示

## 许可证


本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

 *应给不会有人想要用我的史山代码叭（*

<iframe align="center" src="//player.bilibili.com/player.html?isOutside=true&aid=80433022&bvid=BV1GJ411x7h7&cid=137649199&p=1" scrolling="no" border="0" frameborder="no" framespacing="0" allowfullscreen="true"></iframe>

---

<p align="center">
  能读到这里你也很厉害了awa 
  生日快乐（）
</p>


