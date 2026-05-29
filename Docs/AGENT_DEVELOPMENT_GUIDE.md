# DiscUI Agent 开发完全指南

欢迎来到 DiscUI 飞盘游戏智能体开发世界！本指南将带你从零开始学习如何开发自己的飞盘游戏AI智能体。

## 目录

- [第一章：基础知识准备](#第一章基础知识准备)
- [第二章：理解游戏机制](#第二章理解游戏机制)
- [第三章：第一个简单Agent](#第三章第一个简单agent)
- [第四章：PlayerAgent深度解析](#第四章playeragent深度解析)
- [第五章：TeamAgent团队协作](#第五章teamagent团队协作)
- [第六章：高级策略开发](#第六章高级策略开发)
- [第七章：调试与优化](#第七章调试与优化)
- [第八章：实战案例分析](#第八章实战案例分析)

---

## 第一章：基础知识准备

### 1.1 Python基础要求

在开始之前，请确保你具备以下Python知识：

```python
# 基础语法
变量定义、条件判断、循环控制

# 数据结构
列表(list)、字典(dict)、元组(tuple)

# 面向对象
类(class)、继承(inheritance)、方法(method)

# 示例：基本的类定义
class MyClass:
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        return f"Hello, {self.name}!"
```

### 1.2 游戏框架概念

DiscUI框架的核心概念：

- **Entity（实体）**: 游戏中的基本单位（玩家、飞盘等）
- **Event（事件）**: 实体间通信的消息机制
- **Agent（智能体）**: 控制实体行为的AI逻辑
- **State（状态）**: 游戏当前的各种信息

### 1.3 开发环境搭建

```bash
# 1. 安装必要依赖
pip install pygame

# 2. 创建项目目录结构
mkdir my_discui_project
cd my_discui_project

# 3. 复制框架文件
cp /path/to/DiscUI.py .
cp /path/to/PlayerAgents.py .  # 如果有的话
```

---

## 第二章：理解游戏机制

### 2.1 游戏基本规则

**场地布局**：
```
+-------------------------------------+
|  红队得分区  |        | 蓝队得分区  |
|  (左侧)     |   中线  |  (右侧)     |
|             |        |             |
+-------------------------------------+
```

**游戏目标**：将飞盘投掷到对方得分区获得分数

**基本操作**：
- 移动：控制角色在场地内移动
- 接盘：尝试接住飞行中的飞盘
- 传球：将持有的飞盘投掷给队友或向得分区投掷

### 2.2 游戏状态信息详解

你的Agent可以访问以下游戏信息：

```python
information = {
    'my_position': [x, y],           # 你的当前位置 [横坐标, 纵坐标]
    'my_team_id': 0,                 # 你的队伍ID (0=蓝队, 1=红队)
    'my_id': 0,                      # 你在队伍中的编号
    'hold_disc': None                # 你当前持有的飞盘对象 (不持有飞盘则为None)
    'disc': {                        # 飞盘信息
        'position': [x, y],          # 飞盘当前位置
        'state': 1,                  # 飞盘状态 (0=落地,1=空中,2=持有,3=争夺)
        'holder': Player对象,        # 当前持有者 (None表示无人持有)
        'height': 0                  # 飞盘离地高度
    },
    'teammates': [                   # 队友信息列表
        {'position': [x, y], 'id': 1},
        {'position': [x, y], 'id': 2}
    ],
    'opponents': [                   # 对手信息列表
        {'position': [x, y], 'id': 0},
        {'position': [x, y], 'id': 1}
    ],
    'score_zones': {                 # 得分区域信息
        'my_zone': (x, y, width, height),      # 我方得分区
        'opponent_zone': (x, y, width, height) # 对方得分区
    }
}
```

### 2.3 坐标系统说明

```
(0,0) -------------------------> X轴 (宽度)
  |
  |
  |
  |
  V
Y轴 (高度)

- 左上角为原点 (0,0)
- X轴向右增加
- Y轴向下增加
- 典型屏幕尺寸：980×640像素
```

---

## 第三章：第一个简单Agent

### 3.1 创建基础Agent

让我们从最简单的Agent开始：

```python
# simple_agent.py
from DiscUI import PlayerAgentBase

class SimpleAgent(PlayerAgentBase):
    def __init__(self):
        super().__init__()
        print("我的第一个Agent被创建了！")
    
    def agent_func(self):
        """
        这是Agent的核心函数，必须返回一个动作字典
        """
        # 获取飞盘位置
        disc_pos = self.information['disc']['position']
        
        # 简单策略：总是向飞盘移动
        action = {
            'move': disc_pos  # 移动到飞盘位置
        }
        
        return action

# 测试你的Agent
if __name__ == "__main__":
    from DiscUI import game, NoTeamAgent
    
    # 创建两个相同的简单Agent
    agents = [SimpleAgent() for _ in range(4)]  # 4个玩家，每人一个
    
    # 启动游戏
    game(
        player_num=2,  # 每队2个玩家
        team_agent_list=[NoTeamAgent(), NoTeamAgent()],
        player_agent_list=[agents[:2], agents[2:]]  # 分配给两队
    )
```

### 3.2 理解动作系统

Agent可以执行的动作包括：

```python
def agent_func(self):
    action = {}
    
    # 1. 移动动作
    action['move'] = [target_x, target_y]  # 移动到指定位置
    
    # 2. 接盘动作
    action['catch'] = True  # 尝试接住飞盘
    
    # 3. 投掷动作
    action['throw'] = [power_x, power_y, power_z]  # 投掷力度 [水平x, 水平y, 垂直]
    
    # 4. 记忆更新（可选）
    action['memory_update'] = {'key': 'value'}  # 更新Agent的记忆
    
    return action
```

### 3.3 带条件判断的Agent

```python
class ConditionalAgent(PlayerAgentBase):
    def agent_func(self):
        action = {}
        
        # 获取必要信息
        my_pos = self.information['my_position']
        disc_pos = self.information['disc']['position']
        disc_state = self.information['disc']['state']
        disc_holder = self.information['disc']['holder']
        
        # 条件1：如果飞盘在我附近且我可以接住它
        distance_to_disc = self._calculate_distance(my_pos, disc_pos)
        if (distance_to_disc < 50 and 
            disc_state in [1, 3] and  # 飞盘在空中或争夺中
            disc_holder != self.player):  # 不是我自己持有
            action['catch'] = True
        
        # 条件2：如果我持有飞盘，向对方得分区投掷
        elif disc_holder == self.player:
            opponent_zone = self.information['score_zones']['opponent_zone']
            target_x = opponent_zone[0] + opponent_zone[2] // 2
            target_y = opponent_zone[1] + opponent_zone[3] // 2
            
            # 计算投掷方向和力度
            dx = target_x - my_pos[0]
            dy = target_y - my_pos[1]
            action['throw'] = [dx * 0.3, dy * 0.3, 15]  # 添加垂直分量
        
        # 条件3：否则移动到飞盘位置
        else:
            action['move'] = disc_pos
            
        return action
    
    def _calculate_distance(self, pos1, pos2):
        """计算两点间距离"""
        return ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)**0.5
```

---

## 第四章：PlayerAgent深度解析

### 4.1 PlayerAgentBase类详解

```python
class PlayerAgentBase:
    def __init__(self):
        self.event_bus = None    # 事件总线
        self.player = None       # 关联的玩家对象
        self.memory = {}         # Agent的记忆存储
    
    def inform(self, gamestate):
        """接收游戏状态信息，构建information字典"""
        # 这个方法会被框架自动调用
        pass
    
    def agent(self):
        """执行Agent逻辑的主要入口"""
        # 这个方法也会被框架自动调用
        pass
    
    def agent_func(self):
        """用户需要重写的核心逻辑方法"""
        # 这是你需要实现的方法
        raise NotImplementedError
    
    def act(self):
        """执行动作"""
        # 框架会根据action字典执行相应操作
        pass
```

### 4.2 信息访问技巧

```python
class SmartInformationAgent(PlayerAgentBase):
    def agent_func(self):
        # 1. 快速获取常用信息
        my_pos = self.information['my_position']
        my_team = self.information['my_team_id']
        
        # 2. 分析队友和对手
        teammates = self.information['teammates']
        opponents = self.information['opponents']
        
        # 找到最近的队友
        closest_teammate = min(teammates, 
                              key=lambda t: self._distance(my_pos, t['position']))
        
        # 找到最近的对手
        closest_opponent = min(opponents,
                              key=lambda o: self._distance(my_pos, o['position']))
        
        # 3. 飞盘状态分析
        disc_info = self.information['disc']
        is_held = disc_info['state'] == 2
        is_flying = disc_info['state'] == 1
        holder = disc_info['holder']
        
        # 4. 场地分析
        zones = self.information['score_zones']
        my_zone = zones['my_zone']
        opp_zone = zones['opponent_zone']
        
        # 根据分析结果制定策略...
        
    def _distance(self, pos1, pos2):
        return sum((a-b)**2 for a,b in zip(pos1, pos2))**0.5
```

### 4.3 高级移动策略

```python
class MovementStrategist(PlayerAgentBase):
    def agent_func(self):
        action = {}
        
        # 1. 智能避障移动
        target_pos = self._get_smart_target()
        safe_pos = self._avoid_collisions(target_pos)
        action['move'] = safe_pos
        
        # 2. 路径规划
        if self._need_path_planning():
            path = self._calculate_path(target_pos)
            next_waypoint = path[0] if path else target_pos
            action['move'] = next_waypoint
            
        return action
    
    def _avoid_collisions(self, target_pos):
        """避开其他玩家的智能移动"""
        my_pos = self.information['my_position']
        all_players = (self.information['teammates'] + 
                      self.information['opponents'])
        
        # 检查是否有玩家阻挡路径
        for player in all_players:
            if self._is_blocking(my_pos, target_pos, player['position']):
                # 调整目标位置避开阻挡
                return self._find_alternative_position(my_pos, target_pos, 
                                                     player['position'])
        return target_pos
    
    def _is_blocking(self, start, end, obstacle):
        """判断某点是否在路径上"""
        # 简化的直线阻挡检测
        distance_to_line = self._point_to_line_distance(obstacle, start, end)
        return distance_to_line < 20  # 20像素内的都认为是阻挡
```

### 4.4 记忆系统的使用

```python
class MemoryAgent(PlayerAgentBase):
    def __init__(self):
        super().__init__()
        # 初始化记忆
        self.memory = {
            'last_disc_position': [0, 0],
            'holding_start_time': None,
            'successful_passes': 0,
            'failed_attempts': 0
        }
    
    def agent_func(self):
        action = {}
        
        # 更新记忆
        current_time = self._get_current_time()
        self._update_memory(current_time)
        
        # 基于记忆做决策
        if self._should_pass_based_on_memory():
            action['throw'] = self._calculate_smart_pass()
        elif self._should_move_based_on_memory():
            action['move'] = self._get_strategic_position()
            
        # 更新记忆的动作
        action['memory_update'] = self.memory
        
        return action
    
    def _update_memory(self, current_time):
        """更新各种记忆信息"""
        disc_info = self.information['disc']
        
        # 记录飞盘位置变化
        self.memory['last_disc_position'] = disc_info['position']
        
        # 记录持盘时间
        if disc_info['holder'] == self.player:
            if self.memory['holding_start_time'] is None:
                self.memory['holding_start_time'] = current_time
        else:
            self.memory['holding_start_time'] = None
            
        # 记录成功率统计
        if self._just_scored():
            self.memory['successful_passes'] += 1
        elif self._just_lost_disc():
            self.memory['failed_attempts'] += 1
    
    def _should_pass_based_on_memory(self):
        """基于历史表现决定是否传球"""
        success_rate = (self.memory['successful_passes'] / 
                       max(1, self.memory['successful_passes'] + 
                           self.memory['failed_attempts']))
        holding_time = self._get_holding_duration()
        
        # 如果成功率低或者持盘时间长，考虑传球
        return success_rate < 0.3 or holding_time > 5.0
```

---

## 第五章：TeamAgent团队协作

### 5.1 TeamAgentBase基础

```python
from DiscUI import TeamAgentBase

class BasicTeamAgent(TeamAgentBase):
    def __init__(self):
        super().__init__()
        self.strategy = "balanced"  # 默认策略
    
    def get_mode(self):
        """
        返回队伍模式：
        0 = 进攻模式
        1 = 防守模式
        """
        disc_holder = self.game_state.disc.holder
        my_team_id = self.team_id  # 注意：需要在初始化时设置
        
        # 如果我们队伍持有飞盘，进攻；否则防守
        if disc_holder and disc_holder.team_id == my_team_id:
            return 0  # 进攻
        else:
            return 1  # 防守
    
    def agent(self, gamestate):
        """队伍级别的决策"""
        # 分析场上形势
        self._analyze_field(gamestate)
        
        # 调整队伍策略
        self._adjust_strategy()
        
        # 分配角色给队员
        self._assign_roles(gamestate)
    
    def _analyze_field(self, gamestate):
        """分析场地形势"""
        pass
    
    def _adjust_strategy(self):
        """调整整体策略"""
        pass
    
    def _assign_roles(self, gamestate):
        """给队员分配角色"""
        pass
```

### 5.2 角色分配系统

```python
class RoleBasedTeamAgent(TeamAgentBase):
    def __init__(self):
        super().__init__()
        self.roles = {}  # 存储队员角色分配
        
    def agent(self, gamestate):
        # 根据模式分配角色
        if self.get_mode() == 0:  # 进攻模式
            self._assign_offensive_roles(gamestate)
        else:  # 防守模式
            self._assign_defensive_roles(gamestate)
    
    def _assign_offensive_roles(self, gamestate):
        """进攻时的角色分配"""
        players = self._get_my_players(gamestate)
        
        # 找到最佳投手（靠近对方得分区的）
        best_thrower = self._find_best_thrower(players, gamestate)
        
        # 找到接盘手（跑位最好的）
        receiver = self._find_best_receiver(players, best_thrower)
        
        # 其余为支援角色
        supporters = [p for p in players if p not in [best_thrower, receiver]]
        
        # 分配角色到memory
        self.roles = {
            best_thrower.id: 'thrower',
            receiver.id: 'receiver'
        }
        for supporter in supporters:
            self.roles[supporter.id] = 'supporter'
    
    def _assign_defensive_roles(self, gamestate):
        """防守时的角色分配"""
        players = self._get_my_players(gamestate)
        disc_pos = gamestate.disc.pos
        
        # 按距离飞盘远近排序
        sorted_players = sorted(players, 
                               key=lambda p: self._distance(p.pos, disc_pos))
        
        # 最近的去抢断
        interceptor = sorted_players[0]
        
        # 其余回防得分区
        defenders = sorted_players[1:]
        
        self.roles = {
            interceptor.id: 'interceptor'
        }
        for defender in defenders:
            self.roles[defender.id] = 'defender'
```

### 5.3 团队协调策略

```python
class CoordinatedTeamAgent(TeamAgentBase):
    def __init__(self):
        super().__init__()
        self.formation_positions = {}
        self.communication_log = []
    
    def agent(self, gamestate):
        # 更新阵型位置
        self._update_formation(gamestate)
        
        # 协调队员行动
        self._coordinate_actions(gamestate)
        
        # 记录重要信息用于沟通
        self._log_communication(gamestate)
    
    def _update_formation(self, gamestate):
        """根据模式更新理想阵型"""
        mode = self.get_mode()
        if mode == 0:  # 进攻
            self._set_offensive_formation(gamestate)
        else:  # 防守
            self._set_defensive_formation(gamestate)
    
    def _set_offensive_formation(self, gamestate):
        """设置进攻阵型"""
        my_players = self._get_my_players(gamestate)
        disc_pos = gamestate.disc.pos
        opponent_zone = self._get_opponent_zone(gamestate)
        
        # 创建三角形进攻阵型
        center_x = (disc_pos[0] + opponent_zone[0]) / 2
        center_y = disc_pos[1]
        
        # 分配位置给队员
        for i, player in enumerate(my_players):
            angle = (2 * 3.14159 * i) / len(my_players)
            radius = 80  # 80像素间距
            target_x = center_x + radius * math.cos(angle)
            target_y = center_y + radius * math.sin(angle)
            self.formation_positions[player.id] = [target_x, target_y]
    
    def _coordinate_actions(self, gamestate):
        """协调队员的具体行动"""
        # 这里可以通过设置memory来影响individual agents的行为
        for player in self._get_my_players(gamestate):
            player_role = self.roles.get(player.id, 'default')
            formation_pos = self.formation_positions.get(player.id)
            
            if formation_pos:
                # 通过memory告诉player目标位置
                player.agent.memory['target_position'] = formation_pos
                player.agent.memory['role'] = player_role
```

---

## 第六章：高级策略开发

### 6.1 预测算法

```python
class PredictiveAgent(PlayerAgentBase):
    def __init__(self):
        super().__init__()
        self.position_history = []  # 位置历史记录
        self.prediction_cache = {}  # 预测缓存
    
    def agent_func(self):
        action = {}
        
        # 预测飞盘轨迹
        predicted_landing = self._predict_disc_landing()
        
        # 预测对手行为
        opponent_predictions = self._predict_opponents()
        
        # 基于预测做决策
        target_position = self._calculate_optimal_position(
            predicted_landing, opponent_predictions)
        
        action['move'] = target_position
        return action
    
    def _predict_disc_landing(self):
        """预测飞盘落点"""
        disc_info = self.information['disc']
        
        if disc_info['state'] != 1:  # 不在空中
            return disc_info['position']
        
        # 简单的抛物线预测
        pos = disc_info['position']
        velocity = getattr(disc_info.get('holder', None), 'velocity', [0, 0, 0])
        height = disc_info['height']
        
        # 基于物理公式预测落点
        if velocity[2] > 0:  # 向上运动
            time_to_peak = velocity[2] / 9.8  # 重力加速度
            peak_height = height + velocity[2] * time_to_peak - 0.5 * 9.8 * time_to_peak**2
            time_from_peak = (2 * peak_height / 9.8)**0.5
            total_time = time_to_peak + time_from_peak
            
            landing_x = pos[0] + velocity[0] * total_time
            landing_y = pos[1] + velocity[1] * total_time
            
            return [landing_x, landing_y]
        
        return pos  # 默认返回当前位置
```

### 6.2 机器学习集成

```python
class MLAgent(PlayerAgentBase):
    def __init__(self):
        super().__init__()
        self.decision_model = self._load_model()
        self.training_data = []
    
    def agent_func(self):
        # 准备特征向量
        features = self._extract_features()
        
        # 使用模型预测动作
        action_probs = self.decision_model.predict([features])[0]
        
        # 根据概率选择动作
        action = self._select_action_from_probs(action_probs)
        
        # 收集训练数据
        self._collect_training_data(features, action)
        
        return action
    
    def _extract_features(self):
        """提取决策特征"""
        features = []
        
        # 位置特征
        my_pos = self.information['my_position']
        disc_pos = self.information['disc']['position']
        features.extend([my_pos[0], my_pos[1], disc_pos[0], disc_pos[1]])
        
        # 距离特征
        dist_to_disc = self._distance(my_pos, disc_pos)
        features.append(dist_to_disc)
        
        # 队友和对手特征
        for teammate in self.information['teammates'][:2]:  # 最近两个队友
            features.extend([teammate['position'][0], teammate['position'][1]])
        
        for opponent in self.information['opponents'][:2]:  # 最近两个对手
            features.extend([opponent['position'][0], opponent['position'][1]])
        
        return features
    
    def _select_action_from_probs(self, probs):
        """根据概率分布选择动作"""
        import random
        actions = ['move_to_disc', 'catch', 'throw_to_zone', 'support_teammate']
        chosen_action = random.choices(actions, weights=probs)[0]
        
        # 将选择转换为具体动作
        return self._action_to_command(chosen_action)
```

### 6.3 强化学习框架

```python
class RFAgent(PlayerAgentBase):
    def __init__(self):
        super().__init__()
        self.q_table = {}  # Q值表
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.epsilon = 0.1  # 探索率
        
    def agent_func(self):
        state = self._get_state()
        action = self._choose_action(state)
        
        # 执行动作
        action_dict = self._action_to_dict(action)
        
        # 学习（在下一次调用时）
        self._learn_from_previous(state, action)
        
        return action_dict
    
    def _get_state(self):
        """将复杂信息简化为状态"""
        my_pos = self.information['my_position']
        disc_pos = self.information['disc']['position']
        disc_state = self.information['disc']['state']
        
        # 离散化位置
        my_x_bin = int(my_pos[0] / 100)
        my_y_bin = int(my_pos[1] / 100)
        disc_x_bin = int(disc_pos[0] / 100)
        disc_y_bin = int(disc_pos[1] / 100)
        
        return (my_x_bin, my_y_bin, disc_x_bin, disc_y_bin, disc_state)
    
    def _choose_action(self, state):
        """ε-贪婪策略选择动作"""
        import random
        
        if random.random() < self.epsilon:
            # 探索：随机选择动作
            return random.choice(['move', 'catch', 'throw'])
        else:
            # 利用：选择Q值最高的动作
            if state in self.q_table:
                return max(self.q_table[state].keys(), 
                          key=lambda a: self.q_table[state][a])
            else:
                return 'move'  # 默认动作
```

---

## 第七章：调试与优化

### 7.1 调试技巧

```python
class DebuggableAgent(PlayerAgentBase):
    def __init__(self):
        super().__init__()
        self.debug_mode = True
        self.log_file = open('agent_debug.log', 'w')
    
    def agent_func(self):
        if self.debug_mode:
            self._debug_info()
        
        action = self._make_decision()
        
        if self.debug_mode:
            self._log_action(action)
        
        return action
    
    def _debug_info(self):
        """输出调试信息"""
        info = self.information
        
        debug_msg = f"""
=== DEBUG INFO ===
Frame: {getattr(self, '_frame_count', 0)}
Position: {info['my_position']}
Disc State: {info['disc']['state']}
Disc Holder: {info['disc']['holder']}
Teammates: {len(info['teammates'])}
Opponents: {len(info['opponents'])}
==================
        """
        
        print(debug_msg)
        self.log_file.write(debug_msg + '\n')
        self.log_file.flush()
    
    def _log_action(self, action):
        """记录执行的动作"""
        log_msg = f"Action taken: {action}\n"
        self.log_file.write(log_msg)
        self.log_file.flush()
```

### 7.2 性能优化

```python
class OptimizedAgent(PlayerAgentBase):
    def __init__(self):
        super().__init__()
        self.cache = {}  # 结果缓存
        self.last_calculation = {}  # 上次计算结果
        
    def agent_func(self):
        # 使用缓存避免重复计算
        cache_key = self._generate_cache_key()
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # 执行计算
        result = self._expensive_calculation()
        
        # 缓存结果
        self.cache[cache_key] = result
        
        # 限制缓存大小
        if len(self.cache) > 100:
            self.cache.pop(next(iter(self.cache)))
            
        return result
    
    def _generate_cache_key(self):
        """生成缓存键"""
        # 基于游戏状态生成唯一键
        disc_pos = tuple(self.information['disc']['position'])
        my_pos = tuple(self.information['my_position'])
        return (disc_pos, my_pos)
```

---

## 第八章：实战案例分析

### 8.1 成功案例：区域控制策略

```python
class ZoneControlAgent(PlayerAgentBase):
    """区域控制型Agent，专注于占据关键位置"""
    
    def __init__(self):
        super().__init__()
        self.key_zones = []
        self.current_zone = None
        
    def agent_func(self):
        # 确定当前应该控制的区域
        target_zone = self._select_key_zone()
        
        # 移动到目标区域
        if target_zone:
            action = {'move': [target_zone[0], target_zone[1]]}
            
            # 如果在区域内且有机会接盘
            if self._in_zone(target_zone) and self._can_catch():
                action['catch'] = True
                
            return action
        
        # 默认行为
        return {'move': self.information['disc']['position']}
    
    def _select_key_zone(self):
        """选择最重要的控制区域"""
        # 优先级：得分区 > 中场 > 防守区
        zones = [
            self.information['score_zones']['opponent_zone'],
            (self.screen.get_width()//2, self.screen.get_height()//2, 100, 100),
            self.information['score_zones']['my_zone']
        ]
        
        # 选择最近的未被充分控制的区域
        for zone in zones:
            if not self._zone_controlled_by_teammates(zone):
                return (zone[0] + zone[2]//2, zone[1] + zone[3]//2)
                
        return None
```

### 8.2 比赛数据分析

```python
class AnalyticsAgent(PlayerAgentBase):
    """带数据分析功能的Agent"""
    
    def __init__(self):
        super().__init__()
        self.stats = {
            'passes_attempted': 0,
            'passes_successful': 0,
            'distance_covered': 0,
            'time_with_disc': 0
        }
        self.start_time = time.time()
        
    def agent_func(self):
        # 收集统计数据
        self._update_statistics()
        
        # 基于数据做决策
        if self._pass_success_rate_low():
            play_conservatively = True
        else:
            play_aggressively = True
            
        # 正常决策逻辑...
        return self._normal_decision_logic()
    
    def _update_statistics(self):
        """更新各项统计数据"""
        # 记录传球尝试
        if 'throw' in self.action:
            self.stats['passes_attempted'] += 1
            
        # 记录成功传球
        if (hasattr(self, '_previous_holder') and 
            self._previous_holder != self.information['disc']['holder']):
            self.stats['passes_successful'] += 1
            
        self._previous_holder = self.information['disc']['holder']
```

### 8.3 对抗性策略

```python
class CounterAgent(PlayerAgentBase):
    """专门针对特定对手策略的反制Agent"""
    
    def __init__(self):
        super().__init__()
        self.opponent_patterns = {}
        self.counter_strategies = {}
        
    def agent_func(self):
        # 分析对手模式
        opponent_pattern = self._analyze_opponent_behavior()
        
        # 选择相应的反制策略
        counter_strategy = self._select_counter_strategy(opponent_pattern)
        
        # 执行反制动作
        return self._execute_counter(counter_strategy)
    
    def _analyze_opponent_behavior(self):
        """分析对手的行为模式"""
        opponents = self.information['opponents']
        
        patterns = {}
        for opponent in opponents:
            # 分析移动模式、传球习惯等
            movement_pattern = self._detect_movement_pattern(opponent)
            passing_tendency = self._analyze_passing_tendency(opponent)
            
            patterns[opponent['id']] = {
                'movement': movement_pattern,
                'passing': passing_tendency
            }
            
        return patterns
```

---

## 附录

### A. 常见问题解答

**Q: 如何处理多个Agent之间的协调？**
A: 可以使用TeamAgent进行高层协调，或者让PlayerAgent通过event_bus事件总线系统间接通信。

**Q: Agent的响应速度太慢怎么办？**
A: 优化算法复杂度，使用缓存机制，减少不必要的计算。

**Q: 如何调试复杂的Agent行为？**
A: 使用日志记录、可视化调试工具，或者实现逐步执行模式。

### B. 最佳实践

1. **保持代码简洁**：每个Agent应该有明确的职责
2. **合理使用记忆系统**：避免过度依赖历史信息
3. **注意性能优化**：复杂计算要考虑缓存和预计算
4. **做好异常处理**：确保Agent在各种情况下都能正常工作

### C. 进一步学习资源

- 游戏AI设计模式
- 强化学习在游戏中的应用
- 多智能体系统协调理论
- 实时策略游戏AI开发

---