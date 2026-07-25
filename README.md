# DiscUI - 飞盘游戏智能体框架

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Renderer: pygame](https://img.shields.io/badge/renderer-pygame-green.svg)](https://www.pygame.org/)

DiscUI 是一个面向智能体的飞盘游戏实验框架。项目将比赛状态、物理更新、规则判定、动作校验和渲染输出拆分为相对独立的系统，并通过只读快照向 agent 提供游戏信息，便于开发和验证不同的策略逻辑。

该框架适用于编写玩家 agent、测试基础飞盘策略、观察规则系统与物理系统的交互，并为后续扩展渲染、记录、调试或外部控制接口提供基础结构。

## 快速开始

### 环境要求

- Python 3.10+
- pygame

```bash
pip install pygame
```

### 运行内置示例

当前入口在 `DiscGame.py`。直接运行该文件会创建两队各 2 名空 agent，并使用 pygame 渲染比赛场地。

```bash
python DiscGame.py
```

### 最小启动代码

```python
from DiscGame import GameCoordinator
from PlayerAgents import emptyPlayerAgent
from ui import PygameRenderPort

player_num = 2
player_agents = [
    [emptyPlayerAgent() for _ in range(player_num)],
    [emptyPlayerAgent() for _ in range(player_num)],
]

game = GameCoordinator(player_num, player_agents, fps=60)
game.set_render(PygameRenderPort(1230, 1200))
game.mainloop()
```

如果需要接入自定义监控、记录或外部控制逻辑，可以在 `GameCoordinator` 创建后通过 `game.event_bus` 订阅事件。

## 当前架构

项目现在围绕 `GameCoordinator` 驱动的状态机运行：

```text
PREPARE -> START -> PLAY -> RESET -> PLAY
                         \-> HALT
```

主要目录：

```text
DiscUI/
├── DiscGame.py          # 游戏协调器、状态机、主循环
├── PlayerAgents.py      # 示例 agent
├── config/              # 游戏常量
├── entities/            # Disc、Team、Player 及只读快照
├── events/              # 事件类型
├── systems/             # 动作、物理、规则、事件总线、游戏状态
├── ui/                  # 渲染端口与 pygame 适配器
└── Docs/                # 规则、重构设计和调试记录
```

每一帧的核心流程如下：

1. `GameCoordinator` 创建 `GameStateSnap`。
2. `EventBus` 发布 `GamePlayEvent`，渲染器等订阅者读取快照。
3. `ActionSystem` 并发调用所有 agent，收集 `Intent`。
4. `ActionSystem` 对动作做合法性校验，然后写回 `GameState`。
5. `PhysicSystem` 更新飞盘位置和速度。
6. `RuleSystem` 判定得分、犯规、超时、争抢、落地和出界。
7. 如需重置，状态机进入 `RESET` 并发布 `ResetEvent`。

## 编写 Agent

Agent 需要继承 `systems.AgentBase`，实现两个方法：

- `init(player_key)`：绑定当前 agent 对应的 `PlayerKey`。
- `agent(gamestate)`：读取 `GameStateSnap`，返回一个 `Intent` 列表。

```python
from systems import AgentBase, CatchIntent, MoveIntent, ThrowIntent


class MyPlayerAgent(AgentBase):
    def init(self, player_key):
        self.player_key = player_key

    def agent(self, gamestate):
        player = gamestate.team_list[self.player_key.team_id].player_list[self.player_key.player_id]
        disc = gamestate.disc

        if disc.state in ("flying", "waiting"):
            return [CatchIntent(disc_id=0)]

        target_x = player.pos[0] + 1
        target_y = player.pos[1]
        return [MoveIntent((target_x, target_y))]
```

目前支持三类意图：

| Intent | 用途 | 关键字段 |
| --- | --- | --- |
| `MoveIntent` | 移动未持盘玩家 | `target_pos: tuple[int, int]` |
| `ThrowIntent` | 持盘者投掷飞盘 | `motion: tuple[int, int, int]` |
| `CatchIntent` | 尝试接住飞盘 | `disc_id: int` |

`ActionSystem` 会把 agent 返回的 Intent 包装成 Action，并校验：动作类型、移动速度、持盘状态、接盘距离/高度/速度、重复抢盘等。校验失败的动作会被丢弃。

## 游戏状态快照

系统内部维护可变的 `GameState`，agent 和渲染器读取冻结快照 `GameStateSnap`。

```python
@dataclass(frozen=True)
class GameStateSnap:
    disc: DiscSnap
    team_list: tuple[TeamSnap]
    delta_time: float
    const: Constants
    score: tuple
    tick: int
```

该设计约定如下：

- 系统层可以修改 `GameState`。
- agent 只能根据 `GameStateSnap` 做决策。
- renderer 也只读取 `GameStateSnap`。
- 玩家身份统一使用 `PlayerKey(team_id, player_id)`。

飞盘状态当前使用字符串：

| 状态 | 含义 |
| --- | --- |
| `waiting` | 开盘点等待接盘 |
| `flying` | 飞盘在空中运动 |
| `competing` | 多名玩家正在争抢 |
| `catched` | 已被玩家持有 |
| `ground` | 落地，随后触发规则重置 |

## 事件系统

`EventBus` 提供最小的发布订阅机制：

```python
game.event_bus.subscribe(GamePlayEvent, callback)
game.event_bus.publish(event)
```

当前主要事件：

| 事件 | 触发时机 |
| --- | --- |
| `GameStartEvent` | START 阶段完成场地初始化后 |
| `GamePlayEvent` | PLAY 阶段每一帧 |
| `FoulEvent` | 触碰、超时、出界、落地等规则事件 |
| `DiscCatchEvent` | 争抢结束并确定持盘者 |
| `ScoreEvent` | 有队伍得分 |
| `ResetEvent` | 得分或犯规后重置发盘 |

pygame 渲染器通过订阅这些事件完成画面更新。

## 渲染端口

渲染层通过 `ui.RenderPort` 抽象出来：

```python
class RenderPort(ABC):
    def init(self, game_size, event_bus):
        pass

    def draw(self, state):
        pass
```

默认实现是 `PygameRenderPort`。如果需要接入其他前端、记录回放，或执行无窗口测试，可以实现自定义 `RenderPort`，再传给：

```python
game.set_render(MyRenderPort())
```

## 规则概览

当前规则系统已经处理：

- 得分区内正确持盘得分。
- 持盘者被对方身体接触后犯规。
- 持盘时间超过 `Constants.MAX_HOLD_TIME` 后犯规。
- 多人尝试接盘时进入短暂争抢，并随机确定持盘者。
- 飞盘落地或出界后重置。

这些规则并非正式极限飞盘规则全集，而是服务于 agent 实验的基础可运行判定集。

## 代码风格

该项目正在从早期单体脚本迁移到模块化结构。当前主要设计约定如下：

- `GameCoordinator` 只负责调度状态和系统。
- `GameState` 是系统层唯一事实来源。
- 对外暴露快照，不直接暴露可变实体。
- agent 返回意图，不直接改游戏对象。
- 事件用于渲染、监控和外部扩展，不强行承担全部业务解耦。

部分命名、类型标注和文档仍处于迁移过程中，后续可继续统一接口、补充测试并完善开发文档。

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE)。
