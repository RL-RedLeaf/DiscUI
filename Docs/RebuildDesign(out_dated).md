# 过时了，有些设计和实际实现不一样，不推荐来看(((

## 1 状态机设计
|状态机名称|注解|退出条件|下一步|
|--------|----------------------|----------------------|--------|
|PREPARE|赛前准备状态, 调度外部资源|外部加载完成|START|
|START|开始比赛前的准备，运动员入场，盘就位|盘就位，运动员就位|PLAY|
|PLAY|正式比赛中|得分/失误/犯规|RESET/PAUSE/HALT|
|PAUSE|暂停, 不更新所有游戏实体|外部触发输入|PLAY/RESET/HALT|
|RESET|得分或触发规则事件，重置飞盘位置|飞盘就位|PLAY|
|HALT|程序结束, 释放资源|-|-|

### PREPARE设计
- 创建系统层应用 ( EventBus 事件总线除外. 由于事件总线允许被外部调用, 因此会直接在GameCoordinator创建时创建)
- 渲染引擎初始化（如有）
- 检测状态退出

### START设计
- 创建游戏实体
- 初始化实体位置、比分
- 推送游戏开始事件（渲染）
- 检测状态退出

### PLAY设计
- 创建游戏快照
- 推送游戏快照事件（渲染）
- 反作弊计算
- 智能体行为
- 物理引擎计算
- 规则计算
- 检测状态退出
- tick+=1

### PAUSE设计
- 创建游戏快照
- 渲染界面
- 处理输入
- 检测状态退出

### RESET设计
- 创建游戏快照
- 推送重置事件
- 飞盘位置重置
- 检测状态退出

### HALT设计
- 清除资源
- HALT

## 2 GameState容器设计
```python 
from dataclasses import dataclass

@dataclass
class GameState:
    disc: Disc
    team_list: list[Team]
    delta_time: float
    const: Constants
    score: dict[int, int]
    tick: int                   #记录游戏进行的总帧数

@dataclass(frozen = True)
class PlayerKey:
    team_id: int
    player_id: int

@dataclass
class Disc:
    pos: list[int]              #x,y,z三维坐标
    velocity: list[int]         #x,y,z三维速度
    state: int                  #飞盘当前状态
    holder: PlayerKey              #持盘状态下的持有者
    sub_holder: list[PlayerKey]    #潜在争夺者
    competing_ticks: int           #争夺帧数计数

@dataclass
class Team:
    team_id: int                #team唯一标识
    player_num: int             #队伍人数
    player_list: list[Player]   #队伍队员

@dataclass
class Player:
    player_key: PlayerKey       #player唯一标识
    pos: list[int]              #x,y二维位置
    hold_disc: bool             #是否持盘
```



规则：
- GameState 是每一帧的事实来源
- 系统层可以直接对 GameState 应用更改
- Agent 只读 GameStateSnap (只读快照) 
- Renderer 只读 GameStateSnap
- PlayerKey 作为队员的唯一标识, 用于寻找对应的队员。因此除去 Team 以外所有的球员均用 PlayerKey 存储

## 3 系统层设计
|系统|系统职能|
|----|--------------|
|GameCoordinator|总管理器, 状态机管理器|
|PhysicSystem|物理引擎, 更新飞盘状态|
|RuleSystem|规则引擎, 检测所有规则时间|
|ActionSystem|检测Action合法性, 反作弊, 应用Action|
|EventBus|事件总线|

### PhysicSystem
读取GameState中Disc数据, 直接应用物理引擎, 进行飞盘移动

### ActionSystem
收集所有Agent的动作, 进行反作弊校验, 进行动作
动作:
```python
from dataclasses import dataclass

@dataclass
class Action(frozen = True):
    player_key: PlayerKey
    intent: Intent

class Intent:
    pass
    
class MoveIntent(Intent):
    target_pos: list[int]

class ThrowIntent(Intent):
    disc_id: int
    motion: list[int]

class CatchIntent(Intent):
    disc_id: int
```
*所有行动校验和施行均以 PlayerKey 作为标识*


### RuleSystem
1. 检测是否有身体对抗（接触）        -> 状态机 RESET + 发布 FoulEvent
2. 检测持盘者是否超时               -> 状态机 RESET + 发布 FoulEvent
3. 接盘抢夺                        -> 发布 DiscCatchEvent
4. 检测盘是否落地                   -> 状态机 RESET + 发布 DownEvent
5. 检测盘界外                       -> 状态机 RESET + 发布 StallOutEvent
6. 检测飞盘是否在得分区并被正确接住   -> 状态机 RESET + 发布 ScoreEvent
7. 检测得分是否满足预定分数          -> 状态机 HALT + 发布SuccessEvent


## 4 Agent设计
用户通过集成AgentBase父类以编写自己的Agent子类
```python
class AgentBase:
    player_key: PlayerKey

    def main(self, observation: GameStateSnap) -> list[Intent]:
        pass

```
Agent 子类至少需要包含一个 main 方法, 接收 GameState 快照, 经过决策后返回一个 Intent 列表, 列表需要包含所有的动作, 见上文 ActionSystem 环节
ActionSystem 在接收 Intent 时会根据注册表打包成 Action, 确保目标一致性

Player 在 START 状态下由 Team 创建和管理。
Agent 实例由外部传入，在 START 状态下由 GameCoordinator 按顺序绑定
ActionSystem 保存 PlayerKey -> Agent 注册表，并在 PLAY 状态中调用 Agent。

注册表字典结构:
```python
register_dict: dict{PlayerKey, AgentBase} = {   #PlayerKey(team_id, player_id)
    PlayerKey(0, 0): player_agent_0,
    PlayerKey(0, 1): player_agent_1,
    PlayerKey(1, 0): player_agent_2,
    PlayerKey(1, 1): player_agent_3,
}
```

