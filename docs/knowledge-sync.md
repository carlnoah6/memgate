# 知识同步总线 v2 (Knowledge Sync Bus)

## 概述

知识同步总线解决多 session 认知不一致的问题。当工作区关键文件（SOUL.md, MEMORY.md 等）发生变更时：

1. **事件驱动**：inotifywait 监听文件写入，立即触发（不再依赖心跳轮询）
2. **直接注入**：通过 `openclaw agent --session-id` 直接注入通知到活跃 session
3. **包含 diff**：通知消息包含实际变更内容，不只是"文件更新了"

## 架构 (v2)

```
文件被修改
    ↓
inotifywait 触发事件
    ↓
knowledge-sync.py broadcast --file <name>
    ↓
检测变更 + 生成带 diff 的通知
    ↓
openclaw sessions --json --active 120  (获取活跃 session)
    ↓
对每个目标 session:
  openclaw agent --session-id <id> --message "<带diff的通知>"
```

**关键改进**（相比 v1）：
- 不再等心跳轮询，写入即触发
- 不再经过 LLM 中转，`openclaw agent` 直接注入
- 通知包含实际 diff 内容

## 用法

### 基础命令（v1 兼容）

```bash
# 检测文件变更（输出 JSON）
python3 scripts/knowledge-sync.py check

# 手动通知
python3 scripts/knowledge-sync.py notify <file_path> "<变更描述>"

# 查看同步状态（含 watcher 运行状态）
python3 scripts/knowledge-sync.py status

# 初始化/重置状态
python3 scripts/knowledge-sync.py init

# 查看文件 diff
python3 scripts/knowledge-sync.py diff <file_path>
```

### 新增命令（v2）

```bash
# 广播变更到所有活跃 session
python3 scripts/knowledge-sync.py broadcast

# 只广播指定文件的变更
python3 scripts/knowledge-sync.py broadcast --file SOUL.md

# 试运行（不实际发送）
python3 scripts/knowledge-sync.py broadcast --dry-run

# 跳过指定 session
python3 scripts/knowledge-sync.py broadcast --skip-session "agent:main:feishu:group:oc_xxx"

# 启动文件监听守护进程
python3 scripts/knowledge-sync.py watch
```

### 守护进程管理

```bash
# 启动 watcher
bash scripts/start-knowledge-watcher.sh

# 停止 watcher
bash scripts/stop-knowledge-watcher.sh

# 查看状态（含 watcher PID）
python3 scripts/knowledge-sync.py status

# 查看 watcher 日志
tail -f data/knowledge-watcher.log
```

## 通知消息格式

通知包含实际 diff 内容：

```
📢 知识同步 — SOUL.md 更新
🔴 优先级：高 — 请立即重新加载此文件

变更位置：第 42-48 行

新增内容：
## 新规则
- 项目进行中提新需求时必须 replan
- 不要在主 session 里跑长任务
```

如果 diff 超过 500 字，会截断并提示：
```
… 完整变更请读 SOUL.md
```

## 监控文件与优先级

| 文件 | 优先级 | 隐私 | 说明 |
|------|--------|------|------|
| SOUL.md | 🔴 high | public | 核心规则变更，必须立即通知 |
| MEMORY.md | 🟡 medium | **private** | 长期记忆，仅私聊/双人群可见详情 |
| AGENTS.md | 🟡 medium | public | 工作区规范 |
| USER.md | 🟡 medium | **private** | 用户档案 |
| IDENTITY.md | 🟡 medium | public | 身份定义 |
| TOOLS.md | 🟢 low | public | 工具笔记 |
| HEARTBEAT.md | 🟢 low | public | 心跳配置 |

## 隐私过滤

- **public** 文件：变更详情（含 diff）发到所有 session
- **private** 文件：
  - 多人群聊：只提示"此文件为私密文件，变更详情仅在私聊中可见"
  - 私聊/双人群：显示完整 diff 内容

## Session 过滤规则

broadcast 命令会自动过滤 session：

| Session 类型 | 行为 |
|-------------|------|
| `agent:main:feishu:group:*` | ✅ 广播 |
| `agent:main:telegram:dm:*` | ✅ 广播 |
| `agent:main:subagent:*` | ❌ 跳过 |
| `agent:main:main` | ❌ 跳过 |
| label 以 `t\d` 开头 | ❌ 跳过（任务 session） |

## 防抖 (Debounce)

watcher 内置 3 秒防抖：同一文件在 3 秒内的多次修改只触发一次广播。这避免编辑器保存时多次触发。

## 文件说明

| 文件 | 说明 |
|------|------|
| `scripts/knowledge-sync.py` | 主脚本（检测 + 广播 + 守护进程） |
| `scripts/start-knowledge-watcher.sh` | 启动守护进程 |
| `scripts/stop-knowledge-watcher.sh` | 停止守护进程 |
| `data/knowledge-sync-state.json` | 同步状态（MD5 + 内容快照） |
| `data/knowledge-watcher.pid` | 守护进程 PID 文件 |
| `data/knowledge-watcher.log` | 守护进程日志 |

## 添加新的监控文件

编辑 `scripts/knowledge-sync.py` 中的 `WATCHED_FILES` 字典：

```python
"NEW_FILE.md": {
    "priority": "medium",    # high / medium / low
    "privacy": "public",     # public / private
    "label": "文件描述",
    "emoji": "🟡",           # 🔴 / 🟡 / 🟢
},
```
