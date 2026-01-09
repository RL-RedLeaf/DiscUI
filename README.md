# DiscUI

基于 pygame 的极限飞盘对战演示界面。通过事件总线协调游戏主循环、队伍、队员和飞盘实体，展示两个队伍的站位和飞盘位置。

## 功能特点
- 事件驱动：`EventBus` 分发团队、飞盘和全局状态事件，避免直接耦合。
- 简易实体：`Team`、`Player` 和 `Disc` 负责各自状态更新，`GameState` 汇总后统一渲染。
- 可视化：`UI` 使用 1920×1280 画布绘制场地、得分区、队员与飞盘。
- 可扩展：预留 `team_agent_list` 与 `player_agent_list`，便于挂接自定义决策逻辑。

## 目录
- `DiscUI.py`：核心逻辑与事件、实体、UI 定义。
- `main.py`：示例入口，调用 `DiscUI.game(4)` 启动 4v4。
- `.gitignore`：常用忽略配置。

## 环境要求
- Python 3.10+
- 依赖：`pygame`（未使用额外三方库）

安装依赖：
```bash
pip install pygame
```

## 运行方式
- 直接运行示例（启动一个 4v4 对局）：
```bash
python main.py
```
- 或在其他脚本中调用：
```python
import DiscUI

DiscUI.game(
    player_num=4,                  # 每支队伍的玩家数量
    team_agent_list=None,          # 可传入队伍级 AI/决策函数列表
    player_agent_list=None,        # 可传入队员级 AI/决策函数列表
)
```
游戏窗口打开后将持续刷新，关闭窗口或触发异常时退出。

## 运行机制概览
- 游戏入口：`DiscUI.game` 初始化 `pygame`、创建 `DiscGame` 并进入主循环（`DiscUI.py:274`）。
- 主循环：`DiscGame.start_game` 发布 `GameStartEvent`，驱动 `Team`、`Disc` 创建自身状态并加入 `GameState`，随后以 ~60 FPS 刷新并广播状态。
- 渲染：`UI.draw_new_state` 响应 `GameState`，绘制得分区、中线、队员与飞盘位置，保持画面更新。

## 可扩展点
- 在 `Team.team_agent` 或 `Player.agent` 中实现策略，结合事件系统驱动动作。
- 调整分辨率、得分区和初始站位，可修改 `GameStartEvent` 构造参数和 `UI.set_rule` 渲染逻辑。
- 如需物理/碰撞或计分规则，可在 `Disc.mainloop`、`DiscGame.check_movement` 等预留方法内扩展。

## 已知限制
- 当前未实现碰撞检测、得分统计和 AI 决策；所有实体静态展示。
- 默认分辨率固定为 1920×1280，需根据显示设备自行调整。
