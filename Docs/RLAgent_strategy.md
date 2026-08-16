## 基础策略
锦标赛定调为 5v5 比赛，所以理论默认每队5人

RLagent选择使用策略模式，核心机制应该就是打分公式，会在后文中进行详细设计
不过为了做到灵活且不受固定人数影响，选择使用`TeamAgent 规划 Player <--> Task, PlayerAgent 执行`的模式

## TeamAgent 设计
TeamAgent 初始化时接受player_key列表，作为后续生成依据
TeamAgent 持有 memory 字典，用于全局规划
TeamAgent 持有一张 Task_p 字典，存放不同模式下，不同 Task 的权重（目前只想到这种固定模式，后续可能会有动态计算？）

### 规划流程

TeamAgent 收到  GamestateSnap   
->  summary函数总结现有形式，确定现在场上局势（current_mode）
->  枚举 Task2Player 的集合，调用某种分数计算函数计算当前形势下，玩家与该任务之间适配度的分数，返回一个池子（或两个列表+一个字典的形式）
->  plan 函数通过某种方法从池子中挑选合适的 task2player，生成为最终的 plan
->  player_agent 通过 plan 找到自己的 task 并执行

## 核心字段设计
```python
@dataclass
class TeamAgent:
    player_keys: list[PlayerKey]  # 玩家key列表
    memory: dict[str, any] = field(default_factory=dict)  # 全局记忆字典
    task_p: dict[str, dict[str, float]] = field(default_factory=dict)  # 不同模式下，不同任务的权重字典

    def _summary(self, gamestate_snap: GameStateSnap) -> dict:
        """
        总结当前场上局势，返回当前模式以及候选任务
        """
        pass

    def _score(self, player_key: PlayerKey, task: Task, situation: dict, gamestate: GameStateSnap) -> AssignmentEdge:
        """
        计算玩家与任务之间的适配度分数
        """
        pass

    def _plan(self, assignments: list[AssignmentEdge]) -> Plan:
        """
        生成最终的任务分配计划
        """
        pass

@dataclass
class Task:
    task_id: str  # 任务ID
    task_type: str  # 任务类型
    target: any  # 任务目标
    priority: float  # 任务优先级，用于在分配时进行排序
    params: dict[str, Any] = field(default_factory=dict)

@dataclass
class AssignmentEdge:
    player_key: PlayerKey  # 玩家key
    task: Task  # 分配的任务
    score: float  # 分数，用于评估分配的合理性

@dataclass
class Plan:
    situation: dict  # 当前局势
    task2player: dict[PlayerKey, Task] = field(default_factory=dict)# 玩家key到任务的映射
```


## Summary 设计
> ds建议我summary产出一个Situation对象以方便维护，但是我还是选择返回字典，这方便没有必要做的太复杂，后续也可以通过小步快跑的方式进行迭代优化


