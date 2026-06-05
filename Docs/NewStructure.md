# 架构重构设计文档

> **核心约束**：所有 Agent 接口（`PlayerAgentBase`、`TeamAgentBase` 及其子类）以及 `Player.move()`/`fetch()`/`throw()`/`pos`/`hold_disc` 等 Agent 直接调用的公开 API **绝对不变**。

---

## 1. 现状架构分析

### 1.1 当前组件关系图

```
┌─────────────────────────────────────────────────────────────┐
│                        DiscGame                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │  Team 1  │  │  Team 2  │  │  Disc    │  │     UI      │  │
│  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │  │ (pygame)    │  │
│  │ │Player│ │  │ │Player│ │  │ │Physics│ │  └─────────────┘  │
│  │ │ ...  │ │  │ │ ...  │ │  │ │Score  │ │                   │
│  │ └──────┘ │  │ └──────┘ │  │ │State  │ │                   │
│  └────┬─────┘  └────┬─────┘  │ └──────┘ │                   │
│       │              │        └──────────┘                   │
│       └──────┬───────┘                                       │
│              │ 事件总线 (EventBus)                            │
│              ▼                                                │
│         GameState (共享可变对象)                              │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 当前架构的核心缺陷

| # | 问题 | 表现 | 后果 |
|---|------|------|------|
| 1 | **无分层** | `Disc` 同时包含数据、物理、得分、状态机逻辑 | 修改一处逻辑可能影响其他功能，无法独立测试 |
| 2 | **双向数据流** | 实体通过事件修改 `GameState`，`DiscGame` 又写回自身 | 数据流动方向不清晰，调试困难 |
| 3 | **展示与控制耦合** | `DiscGame.mainloop()` 直接调用 `UI.draw()` | 无法替换渲染后端（如切换 headless 测试模式） |
| 4 | **隐式帧同步** | 用 `updated` 列表 + `"Null"` 字符串判断帧结束 | 类型不安全，无法定位是哪个实体超时 |
| 5 | **事件路由脆弱** | 用 `type(event)` 类对象做 key | 无错误隔离，一个 handler 抛异常会级联崩溃 |
| 6 | **无系统边界** | 物理、AI、渲染逻辑在事件回调中交错触发 | 每次修改都需要理解全部上下文 |

---

## 2. 目标架构设计

### 2.1 总体架构风格：分层 + 系统（Hybrid Layered-System）

选择理由：
- **分层**保证依赖方向清晰（上层依赖下层，不反向）
- **系统（System）** 将逻辑从实体中剥离，符合游戏开发的 ECS-like 模式

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  层                        组件
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  第1层  Agent 层     PlayerAgentBase / TeamAgentBase
                      └─ 用户自定义 Agent（不受重构影响）
  ════════════════════════════════════════════════════
  第2层  展示层        UI (Interface) ← pygame_ui
                      └─ 通过事件监听 GameState，纯只读
  ════════════════════════════════════════════════════
  第3层  游戏逻辑层    GameCoordinator（取代 DiscGame）
                      ├─ Systems（Physics / Scoring / Catch）
                      ├─ 帧同步 Barrier
                      └─ 持有 EventBus
  ════════════════════════════════════════════════════
  第4层  实体层        Disc（纯数据） / Player / Team
                      └─ 仅暴露 getter/setter，无业务逻辑
  ════════════════════════════════════════════════════
  第5层  基础设施层    EventBus / GameState / Constants
                      └─ 被所有上层引用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### 层间依赖规则

- **Agent 层** → 依赖 实体层 + 基础设施层（读 `GameState`、调 `Player.move()`）
- **展示层** → 依赖 基础设施层（读 `GameState`）
- **游戏逻辑层** → 依赖 实体层 + 基础设施层
- **实体层** → 仅依赖 基础设施层（`EventBus`）
- **基础设施层** → 无依赖

> **Agent 层位于最顶层**，意味着它只依赖稳定的底层接口，不会被下层变更影响——这是"不动 agent 接口"的架构保证。

---

## 3. 组件交互设计

### 3.1 数据流架构：单向数据流（Unidirectional Data Flow）

借鉴 Flux/Redux 架构思想：

```
  ┌──────────┐   发布 immutable     ┌──────────────┐
  │  Game    │ ── GameState ──────→ │   Systems    │
  │Coordinator│                     │  (只读)       │
  │          │ ←── 事件通知 ─────── │  Physics     │
  │          │     (DiscThrown等)   │  Scoring     │
  │          │                     │  Catch       │
  └──────────┘                     └──────────────┘
       │                                 │
       │ 发布 GameState                  │ 读取并修改
       ▼                                 ▼
  ┌──────────┐                     ┌──────────────┐
  │   UI     │                     │   Entities   │
  │  (只读)  │                     │  (数据持有)   │
  └──────────┘                     └──────────────┘
       │                                 │
       │ 读取                            │ 读取
       ▼                                 ▼
  ┌──────────────────────────────────────────────┐
  │               Agent Layer                     │
  │  只读 gamestate，通过 Player API 提交动作     │
  └──────────────────────────────────────────────┘
```

### 3.2 帧循环架构设计

每帧被拆分为清晰的**阶段（Phase）**，而非当前的事件扩散模式：

```
一帧的时间线：
───────────────────────────────────────────────────────────→

 Phase 0    Phase 1       Phase 2         Phase 3       Phase 4
 ────────  ──────────  ──────────────  ─────────────  ──────────
 输入处理 → 物理更新 →  AI 决策       →  状态裁决    →  渲染
 (pygame   (Physics    (Agent.agent()   (得分判定      (UI.draw()
 事件)     System)     被调用)         抢夺裁决)       GameState)

           ↑──────── 每帧新 GameState 快照 ────────→
```

每一帧的 `GameCoordinator` 伪代码：

```python
def tick(self):
    # Phase 1: 物理系统 — 修改实体内部状态
    self.physics_system.update(self.disc)

    # Phase 2: 创建不可变快照发布给所有 Agent 和 System
    snapshot = self._create_snapshot(self.disc, self.teams, self.score)
    self.event_bus.publish(snapshot)       # → Agent.agent(), Team 决策

    # Phase 3: 裁决系统 — 处理抢夺、得分
    self.scoring_system.evaluate(snapshot)
    self.catch_system.resolve(snapshot)

    # Phase 4: 通知 UI 绘制 (UI 异步监听 GameState)
    self.event_bus.publish(snapshot)
```

### 3.3 通信契约：事件类型与方向

| 事件 | 发布者 | 订阅者 | 方向 | 数据是否可变 |
|------|--------|--------|------|------------|
| `GameStartEvent` | GameCoordinator | Team, Disc, UI | 向下 | 只读 |
| `GameState` (快照) | GameCoordinator | Systems, Team, UI, Agents | 向下 | **只读** |
| `DiscThrownEvent` | Player | Disc | 平级 | — |
| `DiscCaughtEvent` | Player | Disc | 平级 | — |
| `DiscCaughtSuccessEvent` | Disc | Player | 平级 | — |
| `ScoreEvent` | ScoringSystem | GameCoordinator | 向上 | — |
| `ResetEvent` | GameCoordinator | Team, Disc | 向下 | 只读 |

**关键变更**：移除 `TeamStateEvent` 和 `DiscStateEvent` 作为同步信号的角色，改为 Barrier 显式同步。

---

## 4. 子系统详细设计

### 4.1 GameCoordinator（取代 DiscGame）

**职责**：
- 持有游戏生命周期（start / tick / reset）
- 编排帧循环的各个阶段
- 管理 `FrameBarrier` 进行同步

```
GameCoordinator
├── entities:       disc, teams[], players[]
├── systems:        physics, scoring, catch_resolver
├── event_bus:      EventBus
├── barrier:        FrameBarrier
├── running:        bool
│
├── start_game()    → 发布 GameStartEvent
├── tick()          → 编排 5 阶段帧循环
└── reset()         → 发布 ResetEvent
```

对比 `DiscGame` 的移除项：
- ~~`change_disc_state`~~ → 不再是回调，由系统直接更新
- ~~`change_team_state`~~ → 同上
- ~~`updated` / `last_update_time`~~ → 由 `FrameBarrier` 替代
- ~~`DiscUI` 直接调用~~ → 改为事件驱动

### 4.2 Entity 层：纯数据对象

所有实体仅持有数据，不包含业务方法（除 Agent 所需的公开 API 外）。

```
Disc (Entity)
├── pos: [x, y]
├── state: int (0=落地,1=空中,2=持有,3=争夺)
├── holder: Player | None
├── sub_holder: list[Player]
├── height: float
├── velocity: [vx, vy, vz]
└── gravity: float（可考虑移入 PhysicsSystem）

Player (Entity)   ← Agent 依赖的公共 API 保持不变
├── pos: [x, y]
├── hold_disc: Disc | None
├── id, team_id
├── move(tg_pos)      ← 保留
├── fetch(disc)       ← 保留
├── throw(disc,power) ← 保留
└── set_disc(event)   ← 保留
```

### 4.3 System 层：纯逻辑

```python
class PhysicsSystem:
    """只负责物理模拟，不关心得分、状态"""
    def __init__(self, constants: PhysicsConstants):
        self.gravity = constants.GRAVITY

    def update(self, disc: Disc, dt: float):
        if disc.state != 1:          # 仅空中状态需要物理
            return
        disc.velocity[2] -= self.gravity * dt
        disc.pos[0] += disc.velocity[0] * dt
        disc.pos[1] += disc.velocity[1] * dt
        disc.height += disc.velocity[2] * dt
        # 边界钳制
        disc.pos[0] = clamp(disc.pos[0], 0, SCREEN_WIDTH)
        disc.pos[1] = clamp(disc.pos[1], 0, SCREEN_HEIGHT)
        # 落地检测
        if disc.height <= 0:
            disc.state = 0
            disc.height = 0
            disc.velocity = [0, 0, 0]

class ScoringSystem:
    """纯得分判定，通过 ScoreEvent 上报"""
    def __init__(self, event_bus):
        self.event_bus = event_bus

    def evaluate(self, state: GameState):
        disc = state.disc
        if disc.state not in (0, 1):   # 仅空中/落地状态可得分
            return
        for team_id, zone in state.score_zones.items():
            if point_in_rect(disc.pos, zone):
                scoring_team = 1 - team_id
                self.event_bus.publish(ScoreEvent(scoring_team))
                break

class CatchResolver:
    """裁决飞盘抢夺结果"""
    def resolve(self, disc: Disc):
        if disc.state == 3 and disc.sub_holder:
            winner = random.choice(disc.sub_holder)
            disc.holder = winner.sender
            disc.state = 2
            disc.pos = disc.holder.pos[:]
            disc.sub_holder = []
            self.event_bus.publish(DiscCaughtSuccessEvent(disc, disc.holder))
```

**System 设计原则**：
- 无状态（stateless）：所有数据从参数传入，结果写回实体或发布事件
- 单一职责：每个 System 只做一件事
- 可测试：传入 mock 实体即可单元测试

### 4.4 帧同步 Barrier

```python
class FrameBarrier:
    """
    同步屏障：等待所有子系统完成当前帧。
    - 替代旧的 updated[] + "Null" 填充方式
    - 每个 Phase 完成后调用 mark_ready
    - 全部完成后触发 on_frame_complete
    """
    def __init__(self, on_frame_complete: Callable, timeout_ms: int = 1000):
        self._phases = ["physics", "ai", "resolve", "render"]
        self._phase_index = 0
        self._on_complete = on_frame_complete
        self._timeout_ms = timeout_ms
        self._start_time = 0

    def start_frame(self):
        self._phase_index = 0
        self._start_time = get_ticks()

    def advance_phase(self) -> bool:
        """推进到下一阶段，返回是否超时"""
        self._phase_index += 1
        if self._phase_index >= len(self._phases):
            self._on_complete()
            return True
        return False

    def current_phase(self) -> str:
        return self._phases[self._phase_index]

    def is_timeout(self) -> bool:
        return get_ticks() - self._start_time > self._timeout_ms
```

### 4.5 UI 层：Port & Adapter 模式

```python
# ui/port.py — 抽象接口
class RenderPort(ABC):
    @abstractmethod
    def draw(self, state: GameState): ...

# ui/pygame_adapter.py — 具体实现
class PygameRenderer(RenderPort):
    def __init__(self, event_bus, screen):
        self.screen = screen
        self.font = pygame.font.SysFont('SimHei', 40, bold=True)
        event_bus.subscribe(GameStartEvent, self._init_zones)
        event_bus.subscribe(GameState, self.draw)

    def draw(self, state: GameState):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
        self.screen.fill('green')
        # ... 绘制所有元素
        pygame.display.flip()
```

**设计决策**：UI 通过 `GameState` 事件被动更新，而不是被主动调用。这使得：
- 可以在 headless 模式下运行（不创建 UI）
- 可以替换为其他渲染库（如 arcade, pyglet）
- Agent 层完全隔离

---

## 5. 依赖注入设计

当前代码通过**属性赋值**注入依赖（`self.agent.team = self`），这是一种隐式耦合。引入**构造注入**在不改 Agent 接口的前提下规范化依赖设置：

```python
# Team 中规范化 Agent 初始化
class Team:
    def _setup_agent(self, agent: TeamAgentBase):
        # 保持与现有 Agent 接口完全兼容的属性设置方式
        agent.team = self
        agent.event_bus = self.event_bus
        # 但改为在构造时集中完成，而非分散在 create_players 中
        agent.init()

    def _setup_player_agent(self, agent: PlayerAgentBase, player: Player):
        agent.player = player
        agent.event_bus = self.event_bus
        agent.init()
```

这样既保留了 Agent 期望的 `self.team` / `self.player` 属性，又把依赖注入的逻辑集中到一处。

---

## 6. 架构决策记录（Architecture Decision Records）

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 架构风格 | 分层 / ECS / MVC | 分层 + System | ECS 侵入性太强需改 Agent；分层过渡平滑 |
| 数据流 | 双向 / 单向 | 单向 | 单向数据流可预测、易调试 |
| 帧同步 | Barrier / 计数 / 回调链 | Barrier | 明确阶段转换、可加超时监控 |
| 渲染方式 | 主动拉取 / 事件驱动 | 事件驱动 | 解耦游戏逻辑与展示，UI 可替换 |
| 事件路由 | 类对象 key / 枚举 key | 类对象 key（保留） | 为兼容现有 subscribe 调用，不改变 event 类型体系 |
| 实体逻辑 | 自包含 / System 外置 | System 外置 | 职责分离，可独立测试 |

---

## 7. 重构路线图

### 阶段 1：基础设施加固（不改功能、不拆文件）

1. 抽取常量到 `core/constants.py`
2. `EventBus` 加 try/except 隔离 + 发布历史日志
3. 删除所有注释掉的死代码
4. 删除未使用的空事件类（`PlayerMovedEvent`、`PlayerActionEvent`）

**验证**：游戏运行行为完全一致。

### 阶段 2：数据流梳理（改内部结构，不改 API）

1. 在 `Team` 中集中化 Agent 依赖注入（`_setup_agent`）
2. 移除 `TeamStateEvent` / `DiscStateEvent` 作为同步信号的依赖
3. 引入 `FrameBarrier`，逐步替换 `updated` + `"Null"` 机制

**验证**：Agent 行为完全一致，`PlayerAgents.py` 运行通过。

### 阶段 3：System 提取（分离职责）

1. 从 `Disc` 中提取 `PhysicsSystem.update()`
2. 从 `Disc` 中提取 `ScoringSystem.evaluate()`
3. 从 `Disc` 中提取 `CatchResolver.resolve()`
4. `Disc` 降级为纯数据容器 + 事件响应（`on_thrown`）

**验证**：物理行为和得分逻辑与重构前一致。

### 阶段 4：展示层解耦

1. 创建 `RenderPort` 抽象类
2. `PygameRenderer` 实现该接口
3. UI 改为订阅 `GameState` 事件，从主循环移除直接调用

**验证**：渲染效果与重构前一致；可编写 headless 测试。

### 阶段 5：模块化拆分

1. 创建 `core/`、`entities/`、`systems/`、`ui/`、`agents/` 目录
2. 逐文件迁移代码
3. `DiscUI.py` 改为 import + re-export 入口

**验证**：`from DiscUI import ...` 全部可用，`main.py`、`PlayerAgents.py` 无需修改。

---

## 8. 架构验证方法

| 验证维度 | 方法 | 工具/指标 |
|---------|------|----------|
| Agent 兼容性 | 运行 `PlayerAgents.py` | 游戏行为与重构前一致 |
| 单向数据流 | 审计所有 `GameState` 修改点 | 仅 `GameCoordinator` 创建新快照 |
| 层间依赖 | 检查 import 方向 | 禁止下层 import 上层 |
| 系统独立性 | 单元测试 System | 无需创建 `DiscGame` 实例即可测试 |
| 渲染可替换 | 编写 mock renderer | `RenderPort` 可被 mock 实现 |
| 帧同步正确性 | 极端情况测试 | 超时、某 phase 异常时游戏不崩溃 |

---

## 9. 不变契约清单（绝对不允许变更）

```python
# ─── Agent 接口 ───
PlayerAgentBase:
    init(), inform(gs), agent_func(), agent(), act()
    .player, .event_bus, .memory, .information, .action, .disc

TeamAgentBase:
    init(), inform(gs), agent_func(), set_mode(m), get_mode()
    .team, .event_bus, .memory, .mode, .information, .disc

ControlledPlayerAgent:  继承 PlayerAgentBase（签名不变）
NoTeamAgent:            继承 TeamAgentBase（签名不变）

# ─── Entity 公开 API ───
Player:
    move(tg_pos), fetch(disc), throw(disc, power)
    .pos, .hold_disc, .id, .team_id

Team:
    .player_list, .team_id

# ─── GameState 字段路径 ───
gs.disc.{pos, state, holder, height, velocity}
gs.teams[team_id].player_list
gs.score
gs.screen
```

任何重构若触及上述接口，必须重新评估方案。
