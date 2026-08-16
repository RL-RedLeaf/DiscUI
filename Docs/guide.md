# RLAgent 任务分配算法导读

本文说明 RLAgent 的核心策略模型：`TeamAgent` 生成任务池，再把任务分配给玩家。这里的 `RL` 指作者名，不指机器学习。

## 1. 问题抽象

假设当前队伍有若干任务：

```text
T = {t1, t2, ..., tm}
```

有若干玩家：

```text
P = {p1, p2, ..., pn}
```

每个“任务-玩家”组合都有一个分数：

```text
W[i][j] = 玩家 pj 执行任务 ti 的收益
```

目标是选择一组不冲突的组合，使总分最高。

数学形式：

```text
maximize sum_i sum_j W[i][j] * x[i][j]
```

其中：

```text
x[i][j] = 1 表示任务 ti 分配给玩家 pj
x[i][j] = 0 表示不这样分配
```

约束：

```text
每个任务最多给一个玩家：
sum_j x[i][j] <= 1

每个玩家最多接一个任务：
sum_i x[i][j] <= 1
```

如果任务数和玩家数相等，并且每个任务、每个玩家都必须被使用，则约束变成：

```text
sum_j x[i][j] = 1
sum_i x[i][j] = 1
```

这就是标准的“分配问题”。

## 2. 二分图

这个问题可以看成一个二分图：

```text
左侧：任务
右侧：玩家
边：某个玩家执行某个任务
边权：这个组合的分数
```

例如：

```text
reset -- player_0: 87
reset -- player_1: 62
deep  -- player_0: 55
deep  -- player_1: 91
```

匹配就是从这些边里选一部分，但要求：

```text
一个任务不能被多个玩家占用
一个玩家不能同时执行多个任务
```

RLAgent 的任务分配，本质上就是：

```text
最大权二分图匹配
```

## 3. 打分矩阵

每条边的分数可以由多个部分组成：

```text
W[i][j] =
    alpha * task_priority[i]
  + beta  * task_to_player_fit[i][j]
  + gamma * player_to_task_fit[j][i]
  + delta * tactical_value[i][j]
  + eps   * continuity_bonus[i][j]
  - lamb  * risk_penalty[i][j]
```

含义：

```text
task_priority:
    任务本身的重要性。例如 reset、mark_holder、chase_disc 通常更高。

task_to_player_fit:
    从任务角度看，这个玩家是否适合。例如 deep 希望找前方空间大、距离目标近的人。

player_to_task_fit:
    从玩家角度看，这个任务是否适合。例如某个玩家上一帧就在 deep，继续 deep 可以加分。

tactical_value:
    战术收益。例如推进距离、得分机会、封堵传盘路线。

continuity_bonus:
    连续性奖励，减少每帧反复换位。

risk_penalty:
    风险惩罚。例如靠边界太近、离对手太近、离持盘手太近可能导致犯规。
```

注意：不要重复计分。比如 `deep` 的重要性只放在 `task_priority`，不要又在 `task_to_player_fit` 里重复加一遍。

## 4. 贪心算法

贪心算法的思想是：

```text
每一步都选当前看起来最好的合法选择。
```

常见做法是把所有“任务-玩家”组合放进大池子：

```text
1. 生成所有边：task-player
2. 计算每条边的 total_score
3. 按 total_score 从高到低排序
4. 依次取边
5. 如果任务和玩家都还没被占用，就选择这条边
6. 否则跳过
```

伪代码：

```python
edges = []

for task in tasks:
    for player in players:
        edges.append((task, player, score(task, player)))

edges.sort(key=lambda e: e.score, reverse=True)

used_tasks = set()
used_players = set()
assignment = {}

for edge in edges:
    task, player, score = edge

    if task in used_tasks:
        continue
    if player in used_players:
        continue

    assignment[player] = task
    used_tasks.add(task)
    used_players.add(player)
```

优点：

```text
简单
快
容易调试
适合第一版
```

缺点：

```text
不保证全局最优
```

反例：

```text
          A    B
reset    95   80
deep     94   20
```

如果先把 `reset` 给 A：

```text
reset -> A = 95
deep  -> B = 20
总分 = 115
```

但更好的分配是：

```text
reset -> B = 80
deep  -> A = 94
总分 = 174
```

所以贪心可能被局部最优误导。

## 5. Required 任务

比赛中有些任务必须优先满足：

```text
attack:
    reset

defense:
    mark_holder

free:
    chase_disc
```

建议第一版使用：

```text
required 任务优先 + 剩余任务贪心
```

流程：

```text
1. 先给 required tasks 分配玩家
2. 再把剩余玩家分配给 optional tasks
3. 最后仍未分配的玩家执行 fallback tasks
```

这样能保证队伍结构不崩。

## 6. 暴力全局搜索

因为 DiscUI 通常最多 7 人一队，所以可以直接枚举所有分配。

如果有 `n` 个任务和 `n` 个玩家，所有分配数量是：

```text
n!
```

规模：

```text
5! = 120
7! = 5040
```

这其实很小。

伪代码：

```python
best_score = -float("inf")
best_assignment = None

for perm in permutations(players):
    total = 0
    assignment = {}

    for i, task in enumerate(tasks):
        player = perm[i]
        total += score(task, player)
        assignment[player] = task

    if total > best_score:
        best_score = total
        best_assignment = assignment
```

优点：

```text
能得到全局最优
代码比匈牙利算法更直观
在 3-7 人规模下可行
```

缺点：

```text
理论复杂度高
人数变大后不可扩展
```

对当前项目来说，暴力搜索是很实用的第二版方案。

## 7. 匈牙利算法 / KM 算法

匈牙利算法用于解决分配问题。常见有两个版本：

```text
矩阵版匈牙利算法：
    通常讲最小成本匹配。

KM 算法：
    通常讲最大权二分图完美匹配。
```

RLAgent 的任务分配更接近最大收益问题，所以可以看成 KM 算法场景。

目标：

```text
maximize sum_i W[i][match(i)]
```

KM 算法维护两个顶标：

```text
lx[i]：左侧任务 i 的顶标
ly[j]：右侧玩家 j 的顶标
```

要求始终满足：

```text
lx[i] + ly[j] >= W[i][j]
```

如果某条边满足：

```text
lx[i] + ly[j] == W[i][j]
```

这条边叫相等边。算法只在相等边组成的图里找匹配。

初始化：

```text
lx[i] = max_j W[i][j]
ly[j] = 0
```

如果相等边里找不到完整匹配，就调整顶标，制造新的相等边。

定义 slack：

```text
slack(i, j) = lx[i] + ly[j] - W[i][j]
```

当 `slack(i, j) = 0` 时，这条边就是相等边。

搜索时维护：

```text
S：已经访问过的左侧点
T：已经访问过的右侧点
```

若找不到增广路径，则计算：

```text
delta = min { lx[i] + ly[j] - W[i][j] | i in S, j not in T }
```

然后调整：

```text
对 i in S:
    lx[i] -= delta

对 j in T:
    ly[j] += delta
```

这样至少会产生一条新的相等边，并继续寻找匹配。

KM 算法复杂度通常是：

```text
O(n^3)
```

对 7 人规模：

```text
7^3 = 343
```

性能不是问题，但实现复杂度比贪心和暴力搜索更高。

## 8. 任务数和玩家数不同

标准匈牙利算法通常处理方阵：

```text
n x n
```

如果任务比玩家多：

```text
添加虚拟玩家 dummy_player
```

如果玩家比任务多：

```text
添加虚拟任务 fallback / spacing / idle
```

例如 5 个真实任务、7 个玩家：

```text
真实任务：
    reset
    under
    deep
    wide
    safety

虚拟任务：
    spacing_1
    spacing_2
```

这样每个玩家都能拿到一个任务。

## 9. 推荐路线

建议 RLAgent 按下面顺序演进：

```text
第一版：
    任务池 + 边池 + required 优先 + 贪心匹配

第二版：
    加入 player profile、continuity bonus、risk penalty

第三版：
    用暴力搜索做小规模全局最优

第四版：
    如果以后人数扩大，再考虑 KM / 匈牙利算法
```

对 DiscUI 当前规模来说：

```text
贪心足够简单
暴力搜索足够可行
匈牙利算法更标准，但不是第一优先级
```

## 10. 最重要的结论

RLAgent 的分配系统应该先把所有 `(task, player)` 组合打分，形成一个大池子：

```text
AssignmentEdge(task, player, score)
```

然后由 `TeamAgent` 统一选择一组不冲突的边。

最终输出给队员时，不需要暴露整个大池子，只需要：

```text
player -> task
```

也就是：

```python
task_by_player: dict[PlayerKey, RLTask]
```

队员 Agent 只关心自己的任务；队伍 Agent 才负责全局分配。
