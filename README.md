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

飞盘框架主入口位于 `DiscGame.py` 的 `GameCoordinator` 。`PlayerAgents.py` 存放了一些基础的Agent。框架采用**分层智能体**架构：每队一个**队伍级 Agent（教练）**负责制定作战计划，每个玩家绑定一个**玩家 Agent**消费计划并产出动作（所以现在不用再纠结什么通信了，直接用一个全局大手子分配即可awa）

* 主入口`GameCoordinator`
```python
class GameCoordinator:
    def __init__(self, player_num: int, player_agent_list: list[list], team_agent_list: list[TeamAgentBase], fps: int, record = False):
        ...
```
**参数:**
- `player_num` (int): 每队玩家数量
- `player_agent_list` (list[list]): 两队玩家agent嵌套列表，第一项为蓝队，最后一项为红队
- `team_agent_list` (list[TeamAgentBase]): 两队队伍级Agent（教练），下标 0 为蓝队、1 为红队
- `fps` (int): 帧率，同时决定 `delta_time`
- `record` (bool): 是否将对局录制到 `records/` 目录（平常不建议开启，除非你想要你的盘爆炸（写入大小约为190B/帧））

* 调用示例
```python
from DiscGame import GameCoordinator
from PlayerAgents import emptyPlayerAgent, emptyTeamAgent
from ui import PygameRenderPort

player_num = 4
player_agent_list = [
    [emptyPlayerAgent() for _ in range(player_num)],
    [emptyPlayerAgent() for _ in range(player_num)],
]
team_agent_list = [emptyTeamAgent(), emptyTeamAgent()]

game = GameCoordinator(player_num, player_agent_list, team_agent_list, fps=60)
game.set_render(PygameRenderPort(1230, 1200))
game.mainloop()
```

### 内置 Agent

`PlayerAgents.py` 提供了空玩家 Agent 和空队伍 Agent：

```python
class emptyPlayerAgent(AgentBase):
    def init(self, player_key):
        self.player_key = player_key

    def agent(self, gamestate, plan):
        return []   # 什么都不做

class emptyTeamAgent(TeamAgentBase):
    def init(self, team_id, player_list):
        self.team_id = team_id
        self.player_list = player_list

    def agent(self, gamestate):
        return None   # 不产出计划，玩家各自为战
```

把你自己的 Agent 替换进去就能看到效果了，具体写法见 API 参考。

## 架构说明

- ~~本框架架构由我和Deepseek的交流而形成，加以不全面不到位的实施，因此架构显得十分繁琐，堪称 **史山**~~
- ~~本架构尝试使用 **事件总线** 以实现各个组件之间的解耦。幸运的是，我们并没有成功（~~

**以上两个是重构前的内容，我们的重构就旨在解决这两点，于是现在的架构：**

- 使用状态机统一管理游戏内容，至少没有反复引用和横条了
- 重新设计 agent 调用机制，防止牵一发而动全身
- 边缘化Eventbus（并非），总之就不完全依靠这东西作耦合了

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

### 分层智能体

框架采用**队伍级 + 玩家级**两层智能体结构：

- **队伍级 Agent（教练）**：每队一个，继承 `TeamAgentBase`。每帧读取游戏快照，产出一份**作战计划**（角色分配、目标点等，内容完全自定义）。
- **玩家级 Agent（执行者）**：每个玩家一个，继承 `AgentBase`。每帧接收 `(游戏快照, 本队计划)`，产出自己的动作。

计划在**帧间传递**：教练每帧产出的计划存入框架，下一帧才分发给本队玩家。
反正根据AI给我的介绍，这么做的好处是：
> - **零锁**：计划的读写只发生在主线程，多线程的 agent 之间不存在共享可变状态，不需要任何锁。
> - **免费降级**：教练超时或抛异常时框架保留旧计划，玩家继续按上次计划行动；没有计划的帧（比如第一帧），`plan` 为 `None`，玩家各自为战。

教练和玩家之间靠**泛型对齐**保证协议一致：两个基类都是 `Generic[PlanT]`，框架只认识占位符 `PlanT`，建议在自己的 agent 里把它定死为同一个计划类，但是实际上类型检查器不会强制报错，所以嘛...（be like：类型只是资本家的谎言）

具体用法（`PlanT` 在 `systems/ActionSystem.py` 里已定义，不过类型变量名并不重要，关键是两端下标化用**同一个具体计划类**）：

```python
from typing import TypeVar
from systems import AgentBase, TeamAgentBase

PlanT = TypeVar("PlanT")

class MyPlan:  # 你的计划类，内容随便定：角色分配、目标点、战术呼叫……
    ...

class MyCoach(TeamAgentBase[MyPlan]):    # 教练：产出 MyPlan
    ...

class MyPlayer(AgentBase[MyPlan]):       # 玩家：消费 MyPlan
    ...
```

两边都下标化成同一个 `MyPlan`，协议就锁死了。如果某个玩家写成了 `AgentBase[OtherPlan]`，类型检查器会告诉你的。（绝对是提升生产力的好方法，有了它就只用按 TAB 键了）

*注：再次声明，泛型检查只在启用类型检查器（pyright/mypy）时生效，纯运行时不受影响，不写下标也能跑。*

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

为了事件管理和性能管理，**队伍级和玩家级** agent 的 `agent()` 方法统一通过 `ThreadPoolExecutor(max_workers=8)` 并发调用。每帧流程如下：

1. 检查上一帧遗留的 future：已经完成的直接清理（结果过期，丢弃）；仍在运行的标记为"还在跑"
2. 提交每队的教练任务，产出作战计划
3. 为每个不在"还在跑"状态中的玩家 agent 提交新任务，并把**本队上一帧的计划**作为参数传入
4. 统一等待最多 10ms，收集按时返回的结果
5. 超时未返回的 future 保留，下一帧如果还没结束，该 agent 不会再提交新任务，并打印：

```
Agent {player_key} still running, skip
TeamAgent {team_id} still running, skip
```

所以 agent 必须在 10ms 内返回。耗时计算、阻塞 IO、长循环和 sleep 都会导致动作丢帧。如果 agent 抛出异常，本帧该 agent 的动作同样被丢弃，并打印错误信息。

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

### 对局录制与回放

**录制**：`GameCoordinator(..., record=True)` 开启后，每帧对局状态都会被写入 `records/game_时间戳.jsonl`（JSONL，每帧一行，约 190B/帧，反正我已经把这玩意关掉了awa）。记录内容包括比分、飞盘位置/速度/状态、持有者，以及两队全部玩家的位置和持盘标志。

每行的 JSON 格式（我已经尽力把能省的都省了，不然几分钟数据量上 MB 级别）：

| 键 | 内容 |
|----|------|
| `t` | 帧号 |
| `s` | 比分 `[蓝队, 红队]` |
| `d` | 飞盘：位置 `(x,y,z)` + 速度 `(vx,vy,vz)` + 状态码 + 持有者（`PlayerKey` 或 `null`） |
| `p` | 两队玩家，每人 `[x, y, 是否持盘]` |

飞盘状态码：`w`=waiting，`f`=flying，`x`=competing，`c`=catched，`g`=ground。

**回放**：用 `DiscGame.Replayer` 把录制文件喂给任意渲染器：

```python
from DiscGame import Replayer
from ui import PygameRenderPort

replayer = Replayer(0, PygameRenderPort(1230, 1200), 'records\\game_xxx.jsonl')
#这里文件路径使用双斜杠"//"是因为我怕不必要的转义，不过这个担心到底存不存在我也不清楚，反正能跑起来就行
while True:
    replayer.replay_loop()
```

`Replayer(start, render, path, fps=60)`：`start` 是起始帧号（0 表示从头），`replay_loop()` 每调用一次推进一帧并保持帧率。播放完成后自动退出

回放走的是 `GamePlayEvent`，所以**自定义渲染器只要订阅了 `GamePlayEvent` 就能直接看回放**，零额外适配（原汤化原食这一块/.）

## API参考

### GameCoordinator

#### `GameCoordinator(player_num, player_agent_list, team_agent_list, fps, record = False)`

创建比赛实例。

**参数:**
- `player_num` (int): 每队玩家数量
- `player_agent_list` (list[list]): 两队玩家 agent 嵌套列表，`[蓝队agent列表, 红队agent列表]`
- `team_agent_list` (list[TeamAgentBase]): 两队教练，`[蓝队教练, 红队教练]`
- `fps` (int): 目标帧率，同时决定 `delta_time = 1 / fps`
- `record` (bool): 是否录制对局，录制文件在 `records/` 目录

**方法:**
- `set_render(render)` - 设置渲染器，需要在 `mainloop()` 前调用
- `mainloop()` - 启动主循环

### Agent 基类

#### 玩家 Agent（`AgentBase`）

自定义玩家 agent 需要继承 `systems.AgentBase`：

```python
from entities import PlayerKey
from systems import AgentBase, GameStateSnap, MoveIntent, ThrowIntent, CatchIntent

class MyAgent(AgentBase):
    def init(self, player_key: PlayerKey):
        # 初始化时绑定身份
        self.player_key = player_key

    def agent(self, gamestate: GameStateSnap, plan) -> list:
        # 接收只读快照 + 本队计划，返回 Intent 列表
        return []
```

**`init(player_key)`** 在 `ActionSystem.setup()` 中被调用，用于 agent 初始化。

**`agent(gamestate, plan)`** 每帧接收一个 `GameStateSnap` 和本队计划（暂无计划时为 `None`），返回 Intent 列表。返回空列表时本帧不作任何动作。所有 agent 并行调用，单帧超时 10ms。

#### 队伍 Agent（`TeamAgentBase`）

自定义教练需要继承 `systems.TeamAgentBase`：

```python
from systems import TeamAgentBase, GameStateSnap

class MyCoach(TeamAgentBase):
    def init(self, team_id, player_list: list[PlayerKey]):
        # 绑定队伍和本队全部 PlayerKey
        self.team_id = team_id
        self.player_list = player_list

    def agent(self, gamestate: GameStateSnap) -> MyPlan | None:
        # 返回本队作战计划；返回 None 表示沿用上一帧计划
        return MyPlan(...)
```

**`init(team_id, player_list)`** 在 `ActionSystem.setup()` 中被调用，`player_list` 是本队全部玩家标识，教练据此分配角色。

**`agent(gamestate)`** 每帧接收一个只读快照，返回作战计划。计划内容完全自定义（角色分配、目标点、战术呼叫……），但**教练和玩家必须使用同一个计划类**——两个基类都是 `Generic[PlanT]`，建议在你的 agent 文件里把 `PlanT` 定死为具体的计划类，让类型检查器保证两侧协议一致。

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


