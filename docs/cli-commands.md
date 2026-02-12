# CLI 命令参考

Luna OS 自定义 CLI 工具完整列表。所有脚本位于 `/home/ubuntu/.openclaw/workspace/scripts/`。

---

## 📦 系统管理

### `openclaw gateway` — OpenClaw 网关管理

管理 OpenClaw 主网关服务的启停状态。

| 命令 | 说明 |
|------|------|
| `openclaw gateway start` | 启动网关 |
| `openclaw gateway stop` | 停止网关 |
| `openclaw gateway restart` | 重启网关 |
| `openclaw gateway status` | 查看运行状态 |

**示例：**
```bash
openclaw gateway restart
# → ✅ Gateway restarted
```

---

### `staging` — 预发布环境管理

一键在生产/预发布环境间切换。位于 `/usr/local/bin/staging`。

| 命令 | 说明 |
|------|------|
| `staging start` | 停生产 → 启预发布 |
| `staging stop` | 停预发布 → 启生产 |
| `staging status` | 查看两个环境运行状态 |
| `staging switch` | 一键切换（谁在跑就停谁，启另一个）|

**示例：**
```bash
staging switch
# → 生产 → 预发布
# → 🔄 停止生产环境...
# → 🚀 启动预发布环境...
# → ✅ 预发布环境已启动
```

---

## 📋 规划器（Planner）

多步骤有序执行编排器，建立在任务面板之上。每个群聊可以有一个活跃计划。

**脚本：** `python3 scripts/planner.py <command> [args]`

### 命令列表

#### `planner init` — 创建计划

```bash
python3 scripts/planner.py init <chat_id> <goal> '<steps_json>'
```

| 参数 | 说明 |
|------|------|
| `chat_id` | 飞书群聊 ID（如 `oc_0900e63860f8...`）|
| `goal` | 计划目标描述 |
| `steps_json` | JSON 数组，每项 `{"title":"标题","prompt":"执行指令"}` |

**示例：**
```bash
python3 scripts/planner.py init oc_xxx "部署新版本" \
  '[{"title":"构建","prompt":"运行 npm build"},{"title":"部署","prompt":"推送到生产"}]'
```

#### `planner show` — 显示计划状态

```bash
python3 scripts/planner.py show <chat_id>
```

输出当前计划的所有步骤及其状态（queued / running / done / failed）。

#### `planner step-done` — 标记步骤完成

```bash
python3 scripts/planner.py step-done <chat_id> <step_id> "结果描述"
```

标记指定步骤完成并自动推进到下一步。

#### `planner step-fail` — 标记步骤失败

```bash
python3 scripts/planner.py step-fail <chat_id> <step_id> "错误原因"
```

#### `planner replan` — 替换待执行步骤

```bash
python3 scripts/planner.py replan <chat_id> '<new_steps_json>'
```

替换所有尚未执行的步骤为新计划。已完成/运行中的步骤不受影响。

#### `planner cancel` — 取消计划

```bash
python3 scripts/planner.py cancel <chat_id>
```

取消整个计划，所有未完成步骤标记为 cancelled。

#### `planner advance` — 手动推进

```bash
python3 scripts/planner.py advance <chat_id>
```

检查当前步骤状态并推进到下一步（用于心跳检查）。

#### `planner check-advances` — 检查所有计划

```bash
python3 scripts/planner.py check-advances
```

遍历所有活跃计划，检查是否有需要推进的。适合心跳调用。

#### `planner list` — 列出所有计划

```bash
python3 scripts/planner.py list
```

列出所有活跃的 planner 及其状态。

#### `planner find-by-task` — 反查任务所属计划

```bash
python3 scripts/planner.py find-by-task <task_id>
```

**示例：**
```bash
python3 scripts/planner.py find-by-task t015
# → 找到 t015 所属的计划及其步骤位置
```

**可选标志：**
- `--dry-run` — 跳过飞书消息发送和任务面板调用，仅输出

---

## ✅ 任务管理（Task Manager）

异步任务面板管理工具，支持依赖关系和自动并行调度。

**脚本：** `python3 scripts/task-manager.py <command> [args]`

**数据存储：** `data/task-board.json`

### 命令列表

#### `tasks add` — 创建任务

```bash
python3 scripts/task-manager.py add "任务描述" [source_chat_id] [--after t001,t002]
```

| 参数 | 说明 |
|------|------|
| `描述` | 任务描述（必填）|
| `source_chat_id` | 来源群聊 ID（可选）|
| `--after t001,t002` | 依赖的前置任务（可选，逗号分隔）|

**示例：**
```bash
python3 scripts/task-manager.py add "生成周报" oc_xxx
# → ✅ t024 created: 生成周报

python3 scripts/task-manager.py add "发布周报" oc_xxx --after t024
# → ✅ t025 created (depends on: t024)
```

#### `tasks start` — 标记运行中

```bash
python3 scripts/task-manager.py start <id> [session_key]
```

**示例：**
```bash
python3 scripts/task-manager.py start t024 agent:main:subagent:abc123
```

#### `tasks complete` — 标记完成

```bash
python3 scripts/task-manager.py complete <id> "结果摘要"
```

标记完成后自动解锁依赖它的后续任务。

#### `tasks fail` — 标记失败

```bash
python3 scripts/task-manager.py fail <id> "错误信息"
```

#### `tasks cancel` — 取消任务

```bash
python3 scripts/task-manager.py cancel <id>
```

#### `tasks list` — 列出全部任务

```bash
python3 scripts/task-manager.py list [status]
```

可选按状态过滤：`queued`、`running`、`done`、`failed`、`cancelled`。

#### `tasks active` — 活跃任务

```bash
python3 scripts/task-manager.py active
```

输出 JSON 格式的当前运行中任务列表。

#### `tasks status` — 状态概览

```bash
python3 scripts/task-manager.py status
```

输出 JSON 格式的状态统计（各状态数量）。

#### `tasks ready` — 可执行任务

```bash
python3 scripts/task-manager.py ready
```

列出 queued 且依赖已满足、可以立即 spawn 的任务。

#### `tasks cleanup` — 清理旧任务

```bash
python3 scripts/task-manager.py cleanup [days]
```

清理 N 天前的已完成任务（默认 7 天）。

---

## 🔄 知识同步（Knowledge Sync）

检测工作区关键文件变更，生成带 diff 的通知，广播到活跃 session。

**脚本：** `python3 scripts/knowledge-sync.py <command> [args]`

**状态文件：** `data/knowledge-sync-state.json`

### 命令列表

#### `ksync check` — 检测文件变更

```bash
python3 scripts/knowledge-sync.py check
```

检测所有监控文件的变更，输出需要广播的 JSON 通知列表。

#### `ksync broadcast` — 广播变更

```bash
python3 scripts/knowledge-sync.py broadcast [--file <name>] [--dry-run]
```

| 参数 | 说明 |
|------|------|
| `--file <name>` | 只处理指定文件（可选）|
| `--dry-run` | 仅输出不实际发送（可选）|

检测变更 → 生成带 diff 的通知 → 通过 `openclaw agent --session-id` 注入到活跃 session。

**示例：**
```bash
python3 scripts/knowledge-sync.py broadcast --dry-run
# → 显示哪些文件有变更、通知内容预览
```

#### `ksync watch` — 启动文件监听

```bash
python3 scripts/knowledge-sync.py watch
```

使用 `inotifywait` 事件驱动监听文件变更，写入即触发广播。

**启停守护进程（推荐用脚本）：**
```bash
bash scripts/start-knowledge-watcher.sh   # 启动（自动检测重复启动）
bash scripts/stop-knowledge-watcher.sh     # 停止
```

PID 文件：`data/knowledge-watcher.pid`
日志文件：`data/knowledge-watcher.log`

#### `ksync notify` — 手动通知

```bash
python3 scripts/knowledge-sync.py notify <file_path> "变更摘要"
```

**示例：**
```bash
python3 scripts/knowledge-sync.py notify SOUL.md "更新了 OS 模式规则"
```

#### `ksync status` — 同步状态

```bash
python3 scripts/knowledge-sync.py status
```

显示所有监控文件的当前哈希值、最后同步时间等。

#### `ksync diff` — 查看文件差异

```bash
python3 scripts/knowledge-sync.py diff <file_path>
```

显示指定文件与上次快照的 diff。

#### `ksync init` — 初始化/重置

```bash
python3 scripts/knowledge-sync.py init
```

初始化状态文件，记录当前所有文件的 MD5（用于首次部署或重置）。

---

## 💬 Lark 工具

### `lark-send-message.sh` — 发送消息

支持纯文本、stdin 和富文本（Post）格式。

```bash
# 纯文本消息
bash scripts/lark-send-message.sh <chat_id> "消息内容"

# 从 stdin 读取纯文本
echo "消息" | bash scripts/lark-send-message.sh <chat_id> -

# Markdown 转 Post 富文本
cat report.md | bash scripts/lark-send-message.sh <chat_id> --post

# 直接 Post JSON
bash scripts/lark-send-message.sh <chat_id> --post-json '{"zh_cn":{...}}'
```

**示例：**
```bash
# 发送简单消息
bash scripts/lark-send-message.sh oc_xxx "✅ 任务完成"

# 发送格式化报告
cat docs/report.md | bash scripts/lark-send-message.sh oc_xxx --post
```

---

### `lark-calendar-today.py` — 查询日历

查询 Carl 的飞书日历事件，正确处理重复事件和时区。

```bash
python3 scripts/lark-calendar-today.py [日期]
```

| 参数 | 说明 |
|------|------|
| （无参数）| 查询今天的事件 |
| `YYYY-MM-DD` | 指定日期 |
| `tomorrow` | 明天 |
| `--range N` | 从今天起 N 天内的事件 |

**示例：**
```bash
python3 scripts/lark-calendar-today.py
# → 列出今天所有事件

python3 scripts/lark-calendar-today.py 2026-02-15
# → 列出指定日期事件

python3 scripts/lark-calendar-today.py --range 3
# → 列出未来 3 天的事件
```

---

### `send-confirm-card.sh` — 发送交互确认卡片

发送带按钮的交互式卡片到飞书群聊。用户点击按钮后，Luna 收到 `[按钮] <value>` 回调。

```bash
bash scripts/send-confirm-card.sh <chat_id> "标题" "内容" [button_label:value ...]
```

| 参数 | 说明 |
|------|------|
| `chat_id` | 飞书群聊 ID |
| `标题` | 卡片标题 |
| `内容` | 卡片正文 |
| `label:value` | 按钮文字和回调值（可选，不传则默认 ✅确认/❌取消）|

**示例：**
```bash
# 默认确认/取消按钮
bash scripts/send-confirm-card.sh oc_xxx "确认重启" "要重启 Gateway 吗？"

# 自定义按钮
bash scripts/send-confirm-card.sh oc_xxx "选择环境" "部署到哪个环境？" \
  "🚀 生产:deploy_prod" "🧪 预发布:deploy_staging" "❌ 取消:cancel"
```

---

## 📖 Wiki 同步

### `sync-md-to-wiki.py` — MD ↔ Wiki 同步

将本地 Markdown 文件同步到飞书 Wiki。MD 是 Luna 写的，Wiki 是 Carl 看的。

**映射表：** `data/wiki-sync.json`

```bash
# 同步所有有变更的文件
python3 scripts/sync-md-to-wiki.py

# 注册新文件（自动创建 Wiki 文档）
python3 scripts/sync-md-to-wiki.py --register <file> "标题" <space_id> <parent_token>

# 列出所有映射
python3 scripts/sync-md-to-wiki.py --list

# 强制同步指定文件
python3 scripts/sync-md-to-wiki.py --force <file>

# 强制同步所有文件
python3 scripts/sync-md-to-wiki.py --force-all
```

| 参数 | 说明 |
|------|------|
| `--register <file>` | 注册文件并立即首次同步 |
| `"标题"` | Wiki 文档标题 |
| `<space_id>` | Wiki 知识库 ID |
| `<parent_token>` | 父节点 token |

**示例：**
```bash
# 注册新文档到 Wiki
python3 scripts/sync-md-to-wiki.py --register docs/cli-commands.md \
  "CLI 命令参考" 7604126789916479197 IUBdwFzDhisMDrkm1fAltnOhgGd

# 增量同步所有文件
python3 scripts/sync-md-to-wiki.py

# 强制重新同步单个文件
python3 scripts/sync-md-to-wiki.py --force docs/cli-commands.md
```

---

## 📊 仪表盘

### `lark-task-dashboard.py` — 任务仪表盘

发送或更新可刷新的飞书交互卡片，显示所有任务状态和 session 概览。

```bash
python3 scripts/lark-task-dashboard.py
```

自动判断是发送新卡片还是原地更新已有卡片。

**状态保存：** `data/dashboard-state.json`（message_id + hash 防重复）

---

*最后更新：2026-02-12*
