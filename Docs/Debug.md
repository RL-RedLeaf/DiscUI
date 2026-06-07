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

---

## 10. 设计细节答疑（概念补充说明）

### 10.1 FrameBarrier 完整工作流程

> **核心困惑**：`is_timeout()` 和 `on_frame_complete` 到底在哪被调用？怎么串起来的？

FrameBarrier 本身只是**状态机 + 计时器**，不主动调用任何东西。它被外层的 `GameCoordinator.tick()` 驱动：

```python
class FrameBarrier:
    def __init__(self, on_frame_complete, timeout_ms=1000):
        self._phases = ["physics", "ai", "resolve", "render"]
        self._phase_index = 0
        self._on_complete = on_frame_complete  # ← 注册回调
        self._timeout_ms = timeout_ms
        self._start_time = 0

    def start_frame(self):
        """【每帧开头调用】重置计数器和计时器"""
        self._phase_index = 0
        self._start_time = get_ticks()

    def advance_phase(self) -> bool:
        """【每个阶段完成后调用】推进到下一阶段"""
        self._phase_index += 1
        if self._phase_index >= len(self._phases):
            self._on_complete()   # ← 所有阶段走完，触发回调
            return True           # ← 返回 True 表示整帧完成
        return False

    def current_phase(self) -> str:
        return self._phases[self._phase_index]

    def is_timeout(self) -> bool:
        """【GameCoordinator 主动检查】当前帧是否超时"""
        return get_ticks() - self._start_time > self._timeout_ms
```

完整的一帧流程：

```python
class GameCoordinator:
    def __init__(self):
        self.barrier = FrameBarrier(
            on_frame_complete=self._on_frame_done,
            timeout_ms=1000
        )
        self.frame_ready = False

    def _on_frame_done(self):
        """Barrier 所有阶段走完后自动触发"""
        self.frame_ready = True   # 标记整帧完成

    def _tick_playing(self):
        self.barrier.start_frame()          # → phase_index=0, 记录开始时间
        self.frame_ready = False

        # ── Phase 0: 物理 ──
        self.physics_system.update(self.disc)
        if self.barrier.is_timeout():       # ← 主动检查：物理阶段就超了？
            print(f"⚠ 超时: {self.barrier.current_phase()}")
        self.barrier.advance_phase()        # → phase_index=1

        # ── Phase 1: AI 决策 ──
        snapshot = self._create_snapshot()
        self.event_bus.publish(snapshot)    # → Agent 做决策
        if self.barrier.is_timeout():       # ← 主动检查：AI 算太久了？
            print(f"⚠ 超时: {self.barrier.current_phase()}")
        self.barrier.advance_phase()        # → phase_index=2

        # ── Phase 2: 裁决 ──
        self.scoring_system.evaluate(snapshot)
        self.catch_system.resolve(self.disc)
        self.barrier.advance_phase()        # → phase_index=3

        # ── Phase 3: 渲染 ──
        self.renderer.draw(snapshot)
        self.barrier.advance_phase()        # → phase_index=4 ≥ 4
        # ↑ 内部调用 self._on_frame_done() → frame_ready=True

    def run(self):
        while self.running:
            self._tick_playing()
            if self.frame_ready:
                pass  # 帧后处理
```

**`is_timeout()` 和 `on_frame_complete` 的职责：**

| 钩子 | 调用者 | 时机 | 作用 |
|------|--------|------|------|
| `is_timeout()` | GameCoordinator（主动检查） | 每个阶段**之后** | 判断是否超时，决定是否跳过/降级 |
| `on_frame_complete` | `advance_phase()`（自动触发） | 最后一个阶段**内部** | 通知外层整帧结束 |

---

### 10.2 渲染抽象：Port & Adapter 模式详解

> **核心思路**：定义接口（Port），不绑定具体实现（Adapter）。

#### 为什么需要

现在的代码：`DiscGame.mainloop()` 里直接写死了 `self.DiscUI.draw_new_state(...)`。如果你想：
- 换一套渲染库（pygame → pyglet）
- 跑无头测试（headless，不渲染画面）

都得改 `DiscGame`。

#### 三层结构

```
┌──────────────────────┐
│   游戏逻辑层          │  ← 只依赖 RenderPort 接口
│   (GameCoordinator)  │
└─────────┬────────────┘
          │ 依赖抽象，不依赖具体
          ▼
┌──────────────────────┐
│   RenderPort (接口)   │  ← 定义"能干什么"
│   + draw(state)      │     不关心"怎么干"
└─────────┬────────────┘
          ├──────────────────┐
          ▼                  ▼
┌──────────────────┐ ┌──────────────────┐
│ PygameRenderer   │ │ PygletRenderer   │  ← 各自实现 draw()
│ (具体实现)        │ │ (另一个实现)      │
└──────────────────┘ └──────────────────┘
```

#### 代码实现

```python
# ui/port.py — 抽象接口
from abc import ABC, abstractmethod

class RenderPort(ABC):
    @abstractmethod
    def draw(self, state: GameState):
        pass
```

```python
# ui/pygame_adapter.py — 具体实现
class PygameRenderer(RenderPort):
    def __init__(self, screen):
        self.screen = screen

    def draw(self, state: GameState):
        self.screen.fill('green')
        # ... 绘制所有元素
        pygame.display.flip()
```

```python
# GameCoordinator 只认接口，不认具体类
class GameCoordinator:
    def __init__(self, renderer: RenderPort):  # ← 传入接口
        self.renderer = renderer

    def tick(self):
        # ...
        self.renderer.draw(snapshot)  # ← 调接口，不管底下是谁
```

#### 收益

```python
# 正常启动
game = GameCoordinator(PygameRenderer(screen))

# 测试时用假的，不画任何东西
class MockRenderer(RenderPort):
    def draw(self, state):
        pass  # 啥也不干

game = GameCoordinator(MockRenderer())

# 换渲染库，写个新 Adapter 就行
game = GameCoordinator(PygletRenderer(screen))
```

---

### 10.3 Python ABC 与 @abstractmethod

**`abc`** = Abstract Base Classes（抽象基类），是 Python 标准库。作用是**强制子类实现指定方法**。

#### 为什么需要

假设你写框架要求所有 Agent 必须实现 `agent_func()`：

```python
class PlayerAgentBase:
    def agent_func(self):
        raise NotImplementedError  # 运行时才报错
```

问题：子类**忘了重写**，只有实际调用到 `agent_func()` 时才崩，可能已经跑了好久才暴露。

#### ABC 方案：实例化时就报错

```python
from abc import ABC, abstractmethod

class PlayerAgentBase(ABC):
    @abstractmethod
    def agent_func(self):
        pass  # 没有实现体

class MyAgent(PlayerAgentBase):
    pass  # 没重写 agent_func()

a = MyAgent()  # ❌ 立即报错！
# TypeError: Can't instantiate abstract class MyAgent
# with abstract method agent_func
```

#### 两种方式对比

| 方式 | 报错时机 | 错误信息 |
|------|---------|---------|
| `raise NotImplementedError` | 调用该方法时 | 可能被 try 吞掉，很难排查 |
| `@abstractmethod` | **创建对象时** | 明确告诉你哪个方法没实现 |

#### 用在 RenderPort 里

```python
class RenderPort(ABC):
    @abstractmethod
    def draw(self, state: GameState):
        pass

class IncompleteRenderer(RenderPort):
    pass  # 忘了写 draw()

r = IncompleteRenderer()  # ❌ 立刻报错，不让创建
```

**一句话：`@abstractmethod` 把"运行时才能发现的问题"提前到"创建对象时"。**

---

### 10.4 `__init__.py` 的作用

Python 中，目录要成为**包（package）**，通常需要 `__init__.py`。

#### 核心作用

**把目录变成可 import 的模块命名空间。**

没有 `__init__.py`：

```
my_lib/
├── foo.py
└── bar.py
```
你只能 `import my_lib.foo`。

有 `__init__.py`：

```
my_lib/
├── __init__.py    ← 可以控制"从外面能 import 什么"
├── foo.py
└── bar.py
```

```python
# my_lib/__init__.py
from .foo import FooClass
from .bar import bar_function
```

外面就能：
```python
from my_lib import FooClass        # 直接拿到，不用 my_lib.foo.FooClass
from my_lib import bar_function
```

#### 三个典型用途

| 用途 | 说明 | 示例 |
|------|------|------|
| **简化导入路径** | 把深层嵌套的类/函数提升到包级别 | `from pkg import X` 代替 `from pkg.sub.module import X` |
| **控制公开接口** | 定义 `__all__`，规定 `from pkg import *` 导出什么 | `__all__ = ["Foo", "bar"]` |
| **包初始化** | 做一次性的配置、日志设置、注册 | 在 `__init__.py` 里写初始化代码 |

#### 在重构中的应用（阶段 5）

重构后目录结构：

```
DiscUI/                      ← 这个目录就是最终的包
├── __init__.py              ← 导出所有公开 API
├── core/
│   ├── __init__.py          ← 导出 Constants, EventBus
│   ├── constants.py
│   └── event_bus.py
├── entities/
│   ├── __init__.py          ← 导出 Disc, Player, Team
│   ├── disc.py
│   ├── player.py
│   └── team.py
├── systems/
│   ├── __init__.py          ← 导出 PhysicsSystem, ScoringSystem...
│   ├── physics.py
│   ├── scoring.py
│   └── catch.py
├── ui/
│   ├── __init__.py          ← 导出 RenderPort, PygameRenderer
│   ├── port.py
│   └── pygame_adapter.py
└── agents/
    ├── __init__.py          ← 导出 PlayerAgentBase, TeamAgentBase...
    ├── base.py
    ├── controlled.py
    └── no_team.py
```

最顶层的 `__init__.py`：

```python
# DiscUI/__init__.py
from .agents.base import PlayerAgentBase, TeamAgentBase
from .agents.controlled import ControlledPlayerAgent
from .agents.no_team import NoTeamAgent
```

用户代码**完全不变**：
```python
from DiscUI import PlayerAgentBase  # 和原来一模一样
```

**一句话：`__init__.py` 是包的"门面"，对外暴露什么、怎么暴露，都由它控制。**

---

### 10.5 游戏主类设计：两层架构

游戏主类（`GameCoordinator`）需要两层设计：**高层状态机 + 底层帧 Barrier**。

#### 高层状态机：控制游戏整体生命周期

现在代码存在的问题：得分复位时，事件发出去各实体各自处理，但主循环还在照常跑 tick，逻辑混在一起。

解决方案：引入显式的 `GamePhase`：

```
    ┌──────────┐   得分     ┌───────────┐   复位完成    ┌──────────┐
    │ PLAYING  │ ──────→  │ RESETTING │ ────────→  │ PLAYING  │
    │  游戏中  │           │   复位中   │            │  游戏中  │
    └──────────┘           └───────────┘            └──────────┘
         │
         │ 达到分数上限
         ▼
    ┌──────────┐
    │GAME_OVER │
    │  结束    │
    └──────────┘
```

```python
from enum import Enum

class GamePhase(Enum):
    PLAYING = "playing"
    RESETTING = "resetting"
    GAME_OVER = "game_over"

class GameCoordinator:
    def __init__(self):
        self.phase = GamePhase.PLAYING
        self.score = {0: 0, 1: 0}
        self.score_limit = 5
        self.reset_timer = 0  # 复位等待帧数

    def tick(self):
        """根据当前阶段分发到不同的处理函数"""
        if self.phase == GamePhase.PLAYING:
            self._tick_playing()
        elif self.phase == GamePhase.RESETTING:
            self._tick_resetting()
        elif self.phase == GamePhase.GAME_OVER:
            self._tick_game_over()

    def _tick_playing(self):
        """正常游戏帧"""
        self.barrier.start_frame()

        self.physics_system.update(self.disc)
        self.barrier.advance_phase()

        snapshot = self._create_snapshot()
        self.event_bus.publish(snapshot)
        self.barrier.advance_phase()

        self.scoring_system.evaluate(snapshot)  # 得分时调用 _on_score()
        self.catch_system.resolve(self.disc)
        self.barrier.advance_phase()

        self.renderer.draw(snapshot)
        self.barrier.advance_phase()

    def _on_score(self, team_id):
        """得分回调 — 切换状态"""
        self.score[team_id] += 1
        if max(self.score.values()) >= self.score_limit:
            self.phase = GamePhase.GAME_OVER
        else:
            self.phase = GamePhase.RESETTING
            self.reset_timer = 60  # 等 60 帧再继续
            self.event_bus.publish(ResetEvent(...))

    def _tick_resetting(self):
        """复位阶段：等待计时归零后恢复"""
        self.reset_timer -= 1
        if self.reset_timer <= 0:
            self.phase = GamePhase.PLAYING

    def _tick_game_over(self):
        """结束阶段：显示结果，退出循环"""
        self.renderer.draw_game_over(self.score)
        self.running = False
```

#### 两层的关系

```
GameCoordinator
│
├── phase: GamePhase          ← 【高层】PLAYING / RESETTING / GAME_OVER
│     │
│     └── tick() 按 phase 分发
│           │
│           └── _tick_playing()
│                 │
│                 ├── barrier.start_frame()      ← 【底层】帧阶段控制
│                 ├── physics_system.update()
│                 ├── barrier.advance_phase()
│                 ├── snapshot = _create_snapshot()
│                 ├── event_bus.publish(snapshot)
│                 ├── barrier.advance_phase()
│                 ├── scoring_system.evaluate()  ← 触发 _on_score()
│                 ├── barrier.advance_phase()
│                 ├── renderer.draw()
│                 └── barrier.advance_phase()
```

**高层管"游戏在干嘛"（打/复位/结束），底层管"一帧里先干嘛后干嘛"（物理/AI/裁决/渲染）。** 互不干扰。

---

### 10.6 `_create_snapshot()` 实现

#### 为什么需要快照

现在代码直接把真实实体发给 Agent：

```python
# DiscGame.mainloop()
self.event_bus.publish(self.game_state)  # ← 发的是真实对象
```

问题：Agent 收 `GameState` 时，物理系统可能正在更新 `disc.pos`，同一帧内不同 Agent 看到的数据不一致。

#### 方案：从实体提取数据，组装成只读对象

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class GameSnapshot:
    """游戏状态快照 — 不可变，一帧内固定不变"""

    @dataclass(frozen=True)
    class DiscInfo:
        position: tuple
        state: int
        holder_id: Optional[int]
        height: float
        velocity: tuple

    @dataclass(frozen=True)
    class PlayerInfo:
        id: int
        team_id: int
        position: tuple

    @dataclass(frozen=True)
    class TeamInfo:
        team_id: int
        players: List['PlayerInfo']
        mode: int

    disc: DiscInfo
    teams: List[TeamInfo]
    score: dict
    screen_size: tuple

class GameCoordinator:
    def _create_snapshot(self) -> GameSnapshot:
        """冻结当前时刻所有游戏数据"""
        # 飞盘数据：list → tuple，不可变
        disc = GameSnapshot.DiscInfo(
            position=tuple(self.disc.pos),
            state=self.disc.state,
            holder_id=self.disc.holder.id if self.disc.holder else None,
            height=self.disc.height,
            velocity=tuple(self.disc.velocity),
        )

        # 队伍和玩家数据
        teams = []
        for team in [self.team1, self.team2]:
            players = [
                GameSnapshot.PlayerInfo(
                    id=p.id,
                    team_id=p.team_id,
                    position=tuple(p.pos),
                ) for p in team.player_list
            ]
            teams.append(GameSnapshot.TeamInfo(
                team_id=team.team_id,
                players=players,
                mode=team.mode,
            ))

        return GameSnapshot(
            disc=disc,
            teams=teams,
            score=self.score.copy(),
            screen_size=(self.screen.get_width(), self.screen.get_height()),
        )
```

#### 与现有 Agent 接口的兼容

在 Agent 基类里把快照转回 dict，**用户代码完全不用改**：

```python
class PlayerAgentBase:
    def inform(self, snapshot: GameSnapshot):
        """框架调用：将快照转为 information 字典"""
        my_team = snapshot.teams[self.player.team_id]
        my_info = my_team.players[self.player.id]
        opp_team = snapshot.teams[1 - self.player.team_id]

        w, h = snapshot.screen_size
        my_zone = (0, 0, 60, h) if self.player.team_id == 1 else (w - 60, 0, 60, h)
        opp_zone = (w - 60, 0, 60, h) if self.player.team_id == 1 else (0, 0, 60, h)

        self.information = {
            'my_position': list(my_info.position),
            'my_team_id': my_info.team_id,
            'my_id': my_info.id,
            'hold_disc': ...,
            'disc': {
                'position': list(snapshot.disc.position),
                'state': snapshot.disc.state,
                'holder': snapshot.disc.holder_id,
                'height': snapshot.disc.height,
            },
            'teammates': [
                {'position': list(p.position), 'id': p.id}
                for p in my_team.players if p.id != my_info.id
            ],
            'opponents': [
                {'position': list(p.position), 'id': p.id}
                for p in opp_team.players
            ],
            'score_zones': {
                'my_zone': my_zone,
                'opponent_zone': opp_zone,
            },
            'score': snapshot.score.copy(),
        }
```

**核心效果：** Agent 拿到的 `self.information` 内容不变，但数据来自**冻结快照**而非正在被修改的实体。所有 Agent 看到的是同一帧的一致数据。
