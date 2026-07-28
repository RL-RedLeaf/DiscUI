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

飞盘框架主入口位于 `DiscGame.py` 的 `GameCoordinator` 。`PlayerAgents.py` 存放了一些基础的Agent。框架现在不再区分队伍agent和玩家agent（其实这里我也在想如何实现多队员之间的通信，所以敬请期待），每个玩家直接绑定一个agent实例。

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

- ~~本框架架构由我和Deepseek的交流而形成，加以不全面不到位的实施，因此架构显得十分繁琐，堪称 **史山**~~
- ~~本架构尝试使用 **事件总线** 以实现各个组件之间的解耦。幸运的是，我们并没有成功（~~

**以上两个是重构前的内容，我们的重构就旨在解决这两点，于是现在的架构：**

- 使用状态机统一管理游戏内容，至少没有反复引用和横条了
- 重新设计 agent 调用机制，防止牵一发而动全身
- 边缘化Eventbus（并非），我也不知道我现在设计他有什么用了(

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

系统采用发布-订阅模式进行组件通信 (但是实际用到的其实并不多):

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

### 渲染器

框架通过 `ui.RenderPort` 抽象接口分离渲染逻辑。内置的 `PygameRenderPort` 将场地坐标等比缩放绘制到 pygame 窗口，通过订阅事件驱动画面更新。

使用内置渲染器：

```python
from ui import PygameRenderPort

game = GameCoordinator(...)
game.set_render(PygameRenderPort(1230, 1200))
game.mainloop()
```

`PygameRenderPort(width, height)` 的窗口尺寸是请求尺寸，实际渲染区域会根据场地比例自动缩放。

如果不设置渲染器，`game.set_render()` 不会被调用，主循环仍然正常运行，适合后台批量模拟。

也可以自己写渲染器，接口见 API 参考章节。

### 反作弊系统

隆重推出：全新的反作弊系统！
（在旧的版本中，agent 系统和游戏本体是紧密耦合的，因此无法达到较好的反作弊效果，这次改用全新架构，专防作弊w）

所有 agent 返回的 Intent 在被执行前都会经过 `ActionSystem._anti_cheat()` 校验。校验不通过的动作会被直接丢弃，大部分情况下连错误日志都不会打印——所以如果你的 agent 看起来没反应，建议先检查是不是哪条规则没满足。（当然也很有可能就是项目本身的问题，欢迎反馈）

**移动校验：**
- 仅限未持盘玩家移动
- 目标位置必须是长度为 2 的 tuple
- 移动距离不能超过 `PLAYER_SPEED * delta_time`

**抛盘校验：**
- 仅限持盘玩家抛盘
- 速度必须是长度为 3 的 tuple
- 三个轴的速度绝对值都必须达到 `MIN_THROW_SPEED` 的下限
- 飞盘状态必须是 `"catched"`

**接盘校验：**
- 飞盘状态必须是 `"flying"`、`"competing"` 或 `"waiting"`
- 玩家不能已经持盘，飞盘不能已有持有者
- 玩家与飞盘的二维距离必须在 `CATCH_DISTANCE` 以内
- 飞盘高度不能超过 `CATCH_HIGHT`
- 同一玩家不能重复加入争抢列表

另外，`CatchIntent` 提交后不会立刻让玩家持盘，而是把玩家加入 `sub_holder` 列表，等规则系统在后续帧（目前为3帧）中结算争抢结果。

*注：反作弊校验不通过的动作直接静默丢弃了，甚至没有任何输出(*

### 多线程调度

为了事件管理和性能管理，所有 agent 的 `agent()` 方法通过 `ThreadPoolExecutor(max_workers=8)` 并发调用。每帧流程如下：

1. 检查上一帧遗留的 future：已经完成的直接清理（结果过期，丢弃）；仍在运行的标记为"还在跑"
2. 为每个不在"还在跑"状态中的 agent 提交新任务到线程池
3. 等待最多 10ms，收集按时返回的结果
4. 超时未返回的 future 保留，下一帧如果还没结束，该玩家不会再提交新任务，并打印：

```
Agent {player_key} still running, skip
```

所以 agent 必须在 10ms 内返回。耗时计算、阻塞 IO、长循环和 sleep 都会导致动作丢帧。如果 agent 抛出异常，本帧该玩家的动作同样被丢弃，并打印错误信息。

*也是终于接触上多线程了awa 预计以后的更新会加入异步内容w*

### 规则系统

本次更新中也重新参考现实中的飞盘游戏重构了规则，但是可能要诸多不完善，欢迎反馈w

每帧在动作执行和物理更新完成后，`RuleSystem.apply()` 按固定顺序依次判定。一旦某条规则触发了 `RESET`，后续规则不再执行：

1. **得分**：持盘者位于对方得分区内时本队得分，重置发盘
2. **身体接触犯规**：防守方与持盘者距离小于 `PLAYER_SIZE * 2` 时防守方犯规，重置
3. **持盘超时犯规**：持盘超过 `MAX_HOLD_TIME`（2 秒）时持盘方犯规，重置
4. **争抢结算**：`competing_ticks` 递减到 0 后，从 `sub_holder` 中随机选一人成为持盘者
5. **飞盘落地**：飞盘 z 轴触地后，最后持盘方犯规，重置
6. **飞盘出界**：飞盘 xy 坐标超出 `GAME_SIZE` 后，最后持盘方犯规，重置

犯规或得分后的重置会将飞盘移到对方半场的发盘点，并清空所有玩家的持盘标志，但不会移动玩家位置和清空比分（这是试验性的，我想看看如果全场连贯跑下来会不会效果更好，不过后续可能还是会有改动）。


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

飞盘 `state` 取值：`"waiting"`（开盘后等待接盘）、`"flying"`（飞行）、`"competing"`（争抢中）、`"catched"`（被持有）、`"ground"`（落地）。
*这里其实是懒得做状态机管理了，反正这样也能用*

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

### 自定义渲染器

实现 `ui.RenderPort` 抽象类即可接入任意渲染后端：

```python
from ui import RenderPort
from systems import GameStateSnap

class MyRenderPort(RenderPort):
    def init(self, game_size, event_bus):
        # 在这里订阅事件、初始化窗口或连接远程服务
        # game_size 是场地逻辑尺寸，event_bus 用于接收状态更新
        event_bus.subscribe(GamePlayEvent, self.on_frame)
        pass

    def draw(self, state: GameStateSnap):
        # 收到快照后执行渲染
        pass

    def on_frame(self, event):
        self.draw(event.game_state)
```

之后传入 `GameCoordinator.set_render()` 即可生效：

```python
game.set_render(MyRenderPort())
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


