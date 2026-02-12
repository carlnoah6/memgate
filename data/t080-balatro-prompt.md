# Research Task: Balatro RL Environment Survey (t080)

## 目标
调研 GitHub 上现有的 Balatro 游戏逻辑模拟器（Python 实现），评估其是否适合作为强化学习（RL）的训练环境。

## 任务清单
1. **GitHub 搜索与筛选**:
   - 关键词: `balatro python`, `balatro simulator`, `balatro rl`, `balatro engine`.
   - 筛选标准:
     - 语言: Python (必须)
     - 完整性: 实现了核心游戏逻辑（发牌、计分、Joker效果、塔罗牌等）。
     - 活跃度: 最近有更新，或 Star 数较多。
     - 接口: 是否易于封装为 Gym/PettingZoo 环境。

2. **深度评估 (Top 3 项目)**:
   - 下载代码并尝试运行 demo。
   - 分析代码结构：
     - 状态表示 (State Representation): 能够获取当前手牌、弃牌堆、商店状态吗？
     - 动作空间 (Action Space): 出牌、弃牌、购买、跳过等动作是否定义清晰？
     - 性能: 模拟速度如何（RL 需要极快的 step 速度）？

3. **同步到 Wiki**:
   - 撰写调研报告。
   - **Space ID**: `7604150806383693538`
   - **Parent Node Token**: `HDiUwEllbiJIdskrKAZlojadgsc`
   - **Title**: "Balatro RL Environment Survey"

4. **更新 Backlog**:
   - 修改 `data/backlog.md`: 将 "RL 环境调研" 标记为完成。

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json` (user_access_token)
- **Wiki API**:
  - 创建节点: `POST /open-apis/wiki/v2/spaces/{space_id}/nodes`
  - 写入内容: `POST /open-apis/docx/v1/documents/{token}/blocks/{token}/children`
- **消息发送**:
  - 脚本: `bash /home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "oc_a2a70c6b4a29c2f2eb6c2500ea42a500" "✅ t080 完成: ..."`

## 任务管理
- 任务 ID: t080
- 完成后运行: `python3 scripts/task-manager.py complete t080 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t080 "错误原因"`
