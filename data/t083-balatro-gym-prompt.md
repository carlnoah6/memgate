# Research Task: Balatro Gym Environment Wrapping (t083)

## 目标
基于 `t080` 推荐的 `python-balatro-ai` 项目，将其核心逻辑封装为标准 OpenAI Gym (Gymnasium) 环境，以便用于强化学习训练。

## 任务清单
1.  **获取代码**:
    - Clone `https://github.com/jullanggit/python-balatro-ai` 到 `balatro_rl/engine`。
    - 验证其核心类 `Run` (或类似 Game State 管理类) 可被导入和实例化。

2.  **设计 Gym 环境 (`balatro_rl/env.py`)**:
    - 继承 `gymnasium.Env`。
    - **Action Space**:
        - 定义为 `Discrete` 或 `MultiDiscrete`。
        - 动作包括：出牌 (Play Hand)、弃牌 (Discard)、购买 (Buy Joker/Card)、出售 (Sell)、跳过 (Skip Blind) 等。
        - 需处理非法动作屏蔽 (Action Masking)。
    - **Observation Space**:
        - 定义为 `Dict` 或 `Box` (Tensor)。
        - 需包含：当前手牌、公共牌 (Jokers/Consumables)、当前 Blind 信息、筹码数、剩余次数等。
        - **关键**: 将非结构化对象转换为数值 Tensor。

3.  **实现核心方法**:
    - `reset()`: 初始化新游戏。
    - `step(action)`: 执行动作，返回 `(obs, reward, terminated, truncated, info)`。
    - `render()`: 简单的文本输出即可。

4.  **编写测试 (`tests/test_balatro_env.py`)**:
    - 实例化环境。
    - 运行 Random Agent 进行 1000 步测试，确保不崩溃。
    - 验证 Observation Shape 和 Action Space 的正确性。

5.  **同步到 Wiki**:
    - **Space ID**: `7604150806383693538`
    - **Parent Node Token**: `H2KpdZybIoYiRuxDQRHlG92sgch` (Balatro 调研节点的子节点，或同一层级)
    - **Title**: "Balatro Gym Environment Implementation"

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json`
- **消息发送**: `bash scripts/lark-send-message.sh ...`

## 任务管理
- 任务 ID: t083
- 完成后运行: `python3 scripts/task-manager.py complete t083 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t083 "错误原因"`
