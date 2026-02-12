# 任务调度器优先级系统 + Lark Bot 可视化方案 — 研究报告

> **任务 ID:** t135
> **日期:** 2026-02-11
> **作者:** Luna（研究型任务）

---

## 目录

1. [背景 & 现状分析](#1-背景--现状分析)
2. [Part 1: 优先级系统设计](#2-part-1-优先级系统设计)
   - [2.1 业界调研](#21-业界调研)
   - [2.2 Luna 场景分析](#22-luna-场景分析)
   - [2.3 推荐方案](#23-推荐方案)
   - [2.4 实现计划](#24-实现计划)
3. [Part 2: Lark Bot 可视化方案](#3-part-2-lark-bot-可视化方案)
   - [3.1 Lark 开放平台能力调研](#31-lark-开放平台能力调研)
   - [3.2 方案评估](#32-方案评估)
   - [3.3 推荐方案](#33-推荐方案)
4. [综合实施路线图](#4-综合实施路线图)

---

## 1. 背景 & 现状分析

### 1.1 当前架构

Luna 的任务调度系统由以下组件构成：

| 组件 | 文件 | 功能 |
|------|------|------|
| 任务引擎 | `scripts/task_engine.py` | 核心：状态管理、调度、健康检查 |
| CLI 工具 | `scripts/task-manager.py` | 任务 CRUD 命令行接口 |
| 健康检查 | `scripts/task-health-check.py` | 心跳时检测卡死任务 |
| 仪表盘 | `scripts/task-dashboard.py` | 看板展示 |
| 数据存储 | `data/task-board.json` | JSON 文件存储 |

### 1.2 当前任务数据模型

```json
{
  "id": "t135",
  "status": "queued|running|done|failed|cancelled",
  "description": "任务描述",
  "created": "ISO8601",
  "started": null,
  "session_key": null,
  "source_chat": "chat_id",
  "depends_on": ["t001"],
  "result": null,
  "completed": null,
  "task_chat_id": null
}
```

### 1.3 当前调度逻辑

- **FIFO 顺序**：`_get_ready_tasks()` 返回所有 queued + 依赖满足的任务，按数组顺序（即创建顺序）
- **并发控制**：`MAX_CONCURRENT = 3`
- **依赖链**：`depends_on` 字段，等待前置任务 `done` 后解锁
- **无优先级**：紧急用户请求和后台日报任务排同一队列，先到先执行
- **心跳触发调度**：主 session 在心跳时检查 `ready` 队列并 spawn

### 1.4 痛点

1. **用户请求被日报/研究任务阻塞**：Carl 在群聊发出请求，但前面排了 3 个后台任务
2. **无法表达紧急程度**：所有任务"平权"，没有区分 critical 和 background
3. **状态不透明**：Carl 需要主动问"任务做完了吗"，缺乏可视化看板
4. **Lark 消息是纯文本**：当前通知是简单文字，无法展示任务全貌

---

## 2. Part 1: 优先级系统设计

### 2.1 业界调研

#### 2.1.1 Celery（分布式任务队列）

| 特性 | 设计 |
|------|------|
| 优先级模型 | 数字优先级 0-9（RabbitMQ），0 最高 |
| 调度方式 | 每个优先级一个队列，或 broker 原生优先级 |
| 抢占 | ❌ 不支持。高优先级只影响出队顺序 |
| 推荐实践 | **分队列** > 数字优先级。高优先级任务路由到专用 worker |
| 饥饿处理 | 无内建机制，靠运维保证 |

**启示**：Celery 社区共识是"**用队列分隔比用数字优先级更可靠**"。但 Luna 场景太小，不需要多队列。

#### 2.1.2 Apache Airflow（工作流调度器）

| 特性 | 设计 |
|------|------|
| 优先级模型 | `priority_weight`（整数），越大越优先 |
| 权重算法 | `downstream`（默认）/ `upstream` / `absolute` |
| 调度方式 | Scheduler 按 effective weight 排序，先执行高权重任务 |
| 抢占 | ❌ 不支持抢占，仅影响排队顺序 |
| 自定义 | v2.9+ 支持自定义 `PriorityWeightStrategy` |
| 默认值 | `priority_weight = 1` |

**启示**：Airflow 的 `absolute` 模式最适合 Luna——直接指定权重值，简单直接。

#### 2.1.3 Kubernetes Pod Priority & Preemption

| 特性 | 设计 |
|------|------|
| 优先级模型 | `PriorityClass`（命名 + 数字 value） |
| 抢占 | ✅ 支持。高优先级 Pod 可驱逐低优先级 Pod |
| 预防饥饿 | `preemptionPolicy: Never` 可选关闭抢占 |
| 设计理念 | 命名 class（如 `system-critical`、`high-priority`）映射到数字 |

**启示**：K8s 的"命名优先级类"设计很好——人类用名字，系统用数字。Luna 可以借鉴。

#### 2.1.4 Linux CFS（完全公平调度器）

| 特性 | 设计 |
|------|------|
| 优先级模型 | `nice` 值 -20 到 +19（共 40 级） |
| 调度方式 | 虚拟运行时间（vruntime），高优先级 vruntime 增长慢 → 更多 CPU |
| 抢占 | ✅ 时间片用完自动抢占 |
| 饥饿处理 | vruntime 保证每个进程最终都会被调度（无饥饿） |

**启示**：CFS 的 vruntime 太复杂，但"所有优先级都会被调度，只是频率不同"的理念值得参考。

### 2.2 Luna 场景分析

#### 2.2.1 任务特征

| 维度 | 值 |
|------|-----|
| 日均任务量 | 10-30 个 |
| 并发上限 | 3 个 |
| 任务类型 | 研究、检查、日报、用户请求、开发 |
| 任务时长 | 1-60 分钟 |
| 调度频率 | 心跳驱动（~30 分钟） |
| 用户 | Carl（单用户） |

#### 2.2.2 任务类型-优先级映射

| 任务类型 | 典型场景 | 期望优先级 |
|----------|---------|-----------|
| 用户即时请求 | Carl 在群聊说"帮我查一下 X" | 🔴 最高 |
| 系统告警 | 健康检查发现问题 | 🔴 最高 |
| 用户异步请求 | "有空帮我研究一下 Y" | 🟡 高 |
| 日常任务 | 日报、定期检查 | 🟢 普通 |
| 后台维护 | 文档整理、内存清理 | 🔵 低 |

#### 2.2.3 关键决策

**Q1: 是否需要抢占？**
> **不需要。** Luna 的任务是 AI session（subagent），一旦启动就应该运行完。抢占 = kill session，代价太大。高优先级应该"插队"而非"抢占"。

**Q2: 饥饿问题严重吗？**
> **不严重。** 日均 10-30 任务 + 3 并发，queue 很少超过 5 个。但仍应有基本保护：任务等待超过 N 个心跳后自动提升优先级（aging）。

**Q3: 几级优先级？**
> **4 级**。太少（2 级）则区分度不够；太多（10 级）则选择困难。4 级 = critical / high / normal / low，覆盖所有场景。

### 2.3 推荐方案

#### 2.3.1 优先级定义

| 名称 | 数字值 | 图标 | 说明 | 场景 |
|------|--------|------|------|------|
| `critical` | 4 | 🔴 | 紧急，立即插队 | 用户即时请求、系统告警 |
| `high` | 3 | 🟡 | 重要，优先调度 | 用户异步请求 |
| `normal` | 2 | 🟢 | 默认，正常排队 | 日常任务、日报 |
| `low` | 1 | 🔵 | 后台，空闲时执行 | 维护、整理、实验 |

- **默认值**: `normal`（向后兼容，现有任务自动获得 `normal` 优先级）
- **数字值大 = 优先级高**（直觉友好，与 Airflow 一致）

#### 2.3.2 数据模型变更（task-board.json）

新增字段：

```json
{
  "id": "t136",
  "priority": "normal",
  "priority_value": 2,
  "priority_boosted": false,
  "queued_heartbeats": 0,
  // ... 其他字段不变
}
```

| 新字段 | 类型 | 说明 |
|--------|------|------|
| `priority` | string | 优先级名称：`critical/high/normal/low` |
| `priority_value` | int | 数字值 1-4，用于排序 |
| `priority_boosted` | bool | 是否被 aging 自动提升过 |
| `queued_heartbeats` | int | 在 queued 状态经历了几次心跳（用于 aging） |

#### 2.3.3 调度算法变更（task_engine.py）

**核心改动：`_get_ready_tasks()` 排序逻辑**

```python
# 当前（FIFO）
def _get_ready_tasks(self, board, just_completed=None):
    ready = [t for t in board["tasks"] 
             if t["status"] == "queued" and deps_met(t)]
    return ready  # 数组顺序 = 创建顺序

# 改为（优先级 + FIFO）
def _get_ready_tasks(self, board, just_completed=None):
    ready = [t for t in board["tasks"] 
             if t["status"] == "queued" and deps_met(t)]
    # 先按 priority_value 降序，再按 created 升序（同优先级 FIFO）
    ready.sort(key=lambda t: (
        -t.get("priority_value", 2),  # 高优先级优先
        t.get("created", "")          # 同优先级按创建时间
    ))
    return ready
```

**Aging 机制（防饥饿）：**

在 `health_check()` 中添加：

```python
# 每次心跳，queued 任务的 queued_heartbeats += 1
# 如果 queued_heartbeats >= 6（约 3 小时），自动提升一级优先级
AGING_THRESHOLD = 6  # 6 次心跳 ≈ 3 小时

for t in board["tasks"]:
    if t["status"] == "queued":
        t["queued_heartbeats"] = t.get("queued_heartbeats", 0) + 1
        if (t["queued_heartbeats"] >= AGING_THRESHOLD 
            and t.get("priority_value", 2) < 4
            and not t.get("priority_boosted")):
            t["priority_value"] = min(t.get("priority_value", 2) + 1, 3)
            t["priority_boosted"] = True
```

> **注意**：Aging 最多提升到 `high`（3），不会提升到 `critical`（4）。Critical 保留给显式标记。

#### 2.3.4 CLI 接口变更（task-manager.py）

```bash
# 创建任务时指定优先级
task-manager.py add "描述" [chat_id] --priority critical
task-manager.py add "描述" [chat_id] --priority high --after t001

# 修改已有任务优先级
task-manager.py priority t135 high

# 列表显示优先级图标
task-manager.py list
# 🔄 进行中:
#   🏃 [t135] 🟡 研究报告 (15min)
#   ⏳ [t136] 🔴 用户请求：帮忙查 API
#   ⏳ [t137] 🟢 日报生成
```

**新增 `priority` 子命令：**

```python
elif cmd == "priority":
    task_id = sys.argv[2]
    new_priority = sys.argv[3]
    result = engine.set_priority(task_id, new_priority)
    print(json.dumps(result, ensure_ascii=False))
```

**`add` 命令增加 `--priority` 参数：**

```python
# 在 args 解析中增加：
if args[i] == "--priority" and i + 1 < len(args):
    priority = args[i + 1]
    i += 2
```

#### 2.3.5 TaskEngine 新增方法

```python
PRIORITY_MAP = {
    "critical": 4,
    "high": 3,
    "normal": 2,
    "low": 1,
}
PRIORITY_ICONS = {
    "critical": "🔴",
    "high": "🟡",
    "normal": "🟢",
    "low": "🔵",
}

def add(self, description, source_chat=None, depends_on=None, priority="normal"):
    """创建新任务（增加 priority 参数）"""
    task = {
        # ... 现有字段 ...
        "priority": priority,
        "priority_value": PRIORITY_MAP.get(priority, 2),
        "priority_boosted": False,
        "queued_heartbeats": 0,
    }

def set_priority(self, task_id, priority):
    """修改任务优先级"""
    board = self.load_board()
    for t in board["tasks"]:
        if t["id"] == task_id:
            t["priority"] = priority
            t["priority_value"] = PRIORITY_MAP.get(priority, 2)
            self.save_board(board)
            return {"id": task_id, "priority": priority}
    raise ValueError(f"Task {task_id} not found")
```

#### 2.3.6 心跳调度器利用优先级

在主 session 的心跳逻辑中（HEARTBEAT.md / spawn-task 流程）：

```
1. 运行 health_check()（含 aging 逻辑）
2. 获取 ready_tasks（已按优先级排序）
3. 计算可用 slot = MAX_CONCURRENT - running_count
4. 取 ready_tasks[:可用slot] 进行 spawn
5. critical 任务额外行为：
   - 如果 running_count == MAX_CONCURRENT 且有 critical 任务等待
   - 发送提醒消息"⚠️ 紧急任务 {id} 等待中，当前 slot 已满"
   - 不抢占，但确保 Carl 知道情况
```

#### 2.3.7 向后兼容方案

```python
def _compat_priority(self, task):
    """为没有 priority 字段的旧任务添加默认值"""
    if "priority" not in task:
        task["priority"] = "normal"
        task["priority_value"] = 2
        task["priority_boosted"] = False
        task["queued_heartbeats"] = 0
    return task
```

在 `load_board()` 后自动迁移：

```python
@staticmethod
def load_board():
    board = ...  # 现有加载逻辑
    # 向后兼容：为旧任务补充 priority 字段
    for t in board.get("tasks", []):
        if "priority" not in t:
            t["priority"] = "normal"
            t["priority_value"] = 2
            t["priority_boosted"] = False
            t["queued_heartbeats"] = 0
    return board
```

### 2.4 方案对比总结

| 维度 | Celery 风格（分队列） | Airflow 风格（数字权重） | **推荐方案（命名 + 数字）** |
|------|----------------------|------------------------|-----------------------|
| 复杂度 | 高（需多队列管理） | 中（纯数字，缺乏语义） | **低**（4 个命名级别） |
| 可读性 | 中 | 低（数字意义不直观） | **高**（`critical` 一目了然） |
| 灵活性 | 高 | 高 | **够用**（4 级覆盖所有场景） |
| 抢占 | ❌ | ❌ | **❌**（设计决策：不抢占） |
| 饥饿保护 | ❌ | ❌ | **✅**（aging 机制） |
| 向后兼容 | 需迁移 | 需迁移 | **✅**（默认 `normal`） |
| 适合 Luna | ❌（过度设计） | ⚠️（缺语义） | **✅** |

---

## 3. Part 2: Lark Bot 可视化方案

### 3.1 Lark 开放平台能力调研

#### 3.1.1 消息卡片（Interactive Message Card）

飞书/Lark 的消息卡片能力非常丰富：

| 能力 | 支持情况 | 说明 |
|------|---------|------|
| 富文本排版 | ✅ | `lark_md` 支持 Markdown 子集（加粗、链接、列表） |
| 多列布局 | ✅ | `fields` + `is_short` 实现两列/三列布局 |
| 按钮（Button） | ✅ | 支持 `url` 跳转链接 和 `value` 回调两种模式 |
| 链接按钮 | ✅ | Button 设置 `url` 字段可直接打开浏览器/飞书内网页 |
| `multi_url` | ✅ | 按钮可针对不同平台（PC/iOS/Android）设置不同 URL |
| 分割线 | ✅ | `hr` 标签 |
| 图片 | ✅ | 需先上传获取 `img_key` |
| 笔记/备注 | ✅ | `note` 标签，用于底部灰色小字 |
| 卡片头部 | ✅ | `header` 支持标题 + 颜色主题 |
| 回调交互 | ✅ | 按钮点击后可回调服务端，返回更新后的卡片 |
| 宽屏模式 | ✅ | `wide_screen_mode: true` |

#### 3.1.2 卡片更新（PATCH API）

**关键发现**：飞书支持通过 `PATCH /open-apis/im/v1/messages/:message_id` 更新已发送的卡片消息！

这意味着可以：
1. 首次发送一张"任务看板"卡片
2. 每次心跳时 PATCH 更新这张卡片的内容
3. 用户看到的是**同一条消息在原地更新**，而非新消息刷屏

#### 3.1.3 按钮 URL 跳转

卡片按钮支持直接设置 `url` 字段，点击后：
- **PC 端**：在飞书内置浏览器打开
- **移动端**：跳转外部浏览器
- **可选**：使用 `multi_url` 分平台设置不同跳转地址

还支持 **Applink 协议**：`https://applink.feishu.cn/client/web_url/open?url=xxx`，可在飞书客户端内打开网页。

#### 3.1.4 网页应用（H5 Web App）

飞书支持将 H5 页面注册为"网页应用"：
- 在飞书开发者后台创建应用 → 添加"网页"能力
- 配置桌面端/移动端主页 URL
- 用户通过工作台或消息卡片链接访问
- 支持 JSAPI 获取用户身份（免登录）
- 需要公网可访问的 HTTPS URL

#### 3.1.5 Bot 菜单

Bot 支持自定义菜单（出现在聊天输入框上方），菜单项支持：
- 跳转到指定链接
- 触发 Bot 命令
- 打开小程序

### 3.2 方案评估

---

### 方案 A：增强现有 Lark 卡片消息

#### 用户体验

Carl 在群聊中输入 `@Luna 任务看板` 或在心跳时自动推送：

```
┌─────────────────────────────────────┐
│ 📋 Luna 任务看板                    │
│ 2026-02-11 08:30 SGT               │
├─────────────────────────────────────┤
│ 🏃 运行中 (2/3)                     │
│                                     │
│ 🔴 [t138] 帮忙查 API 限频策略       │
│    ⏱ 5min | 🔄 Working | 12k tok   │
│                                     │
│ 🟢 [t137] 每日检查                  │
│    ⏱ 12min | 🔄 Working | 8k tok   │
│                                     │
│ ⏳ 等待中 (2)                        │
│                                     │
│ 🟡 [t139] 研究 GraphQL 方案         │
│    待 t138 完成                      │
│                                     │
│ 🔵 [t140] 整理 docs 目录            │
├─────────────────────────────────────┤
│ ✅ 今日完成: 3  ❌ 失败: 0           │
│ ℹ️ 上次更新: 08:30                   │
│                                     │
│ [🔄 刷新看板]  [📊 详情]             │
└─────────────────────────────────────┘
```

- 心跳时自动 PATCH 更新这张卡片（原地刷新，不刷屏）
- "刷新看板"按钮点击后回调服务端，返回最新状态
- "详情"按钮跳转到 Web Dashboard（如果有的话）

#### 评估

| 维度 | 评分 |
|------|------|
| 用户体验 | ⭐⭐⭐⭐ 原地更新，信息密度高 |
| 实现难度 | ⭐⭐ 简单（改造现有 send_notification） |
| 额外权限 | 无（现有 Bot 权限足够） |
| 额外配置 | 需记录 message_id 用于 PATCH |
| 预计开发 | **2-4 小时** |
| 局限性 | 卡片元素数量有限（不超过约 50 个），大量任务时信息截断 |

---

### 方案 B：Bot 发送含网页链接的卡片 → Web Dashboard

#### 用户体验

1. Luna 在服务器上启动一个轻量 Web 服务（Flask/FastAPI）
2. 通过 ngrok / Cloudflare Tunnel 暴露公网 HTTPS URL
3. 卡片消息包含"📊 打开任务看板"按钮，点击跳转到 Web Dashboard
4. Web Dashboard 实时读取 `task-board.json` 渲染看板

```
┌─────────────────────────────────────┐
│ 📋 Luna 任务看板                    │
│ 运行中: 2 | 等待: 3 | 今日完成: 5   │
│                                     │
│ [📊 打开实时看板]  [🔄 刷新卡片]     │
└─────────────────────────────────────┘
```

Carl 点击"打开实时看板"→ 在飞书内置浏览器打开 → 看到完整的实时 Web 看板。

Web 看板可以包含：
- 任务甘特图 / 时间线
- 实时状态更新（WebSocket / 轮询）
- 历史统计图表
- 筛选和搜索

#### 评估

| 维度 | 评分 |
|------|------|
| 用户体验 | ⭐⭐⭐⭐⭐ 全功能看板，交互丰富 |
| 实现难度 | ⭐⭐⭐ 中等（Web 服务 + 隧道 + 前端） |
| 额外权限 | 无额外飞书权限；需服务器端口 |
| 额外配置 | ngrok/CF Tunnel、HTTPS 证书 |
| 预计开发 | **4-8 小时** |
| 维护成本 | 需保持隧道稳定运行 |

---

### 方案 C：飞书小程序 / 网页应用（原生集成）

#### 用户体验

1. 在飞书开发者后台为现有 Bot 应用添加"网页"能力
2. 配置桌面端/移动端主页 URL（指向 Luna Web 服务）
3. 用户通过飞书工作台直接打开"Luna 任务看板"
4. 支持 JSAPI 免登录（自动识别用户身份）

Carl 可以：
- 在工作台找到"Luna"应用 → 点击打开看板
- 在消息卡片中点按钮 → 直接在飞书内打开（类似 Tab 体验）
- Bot 菜单中配置"📊 任务看板"快捷入口

#### 评估

| 维度 | 评分 |
|------|------|
| 用户体验 | ⭐⭐⭐⭐⭐ 最原生、最流畅 |
| 实现难度 | ⭐⭐⭐⭐ 较高（飞书审核 + 权限配置 + JSAPI） |
| 额外权限 | 需在开发者后台添加网页能力、配置安全域名 |
| 额外配置 | HTTPS 公网 URL、H5 鉴权、安全域名白名单 |
| 预计开发 | **1-2 天** |
| 维护成本 | 同方案 B + 飞书应用配置维护 |

---

### 方案 D：定期推送 + 卡片轮播（创新方案）

#### 用户体验

结合方案 A，但增加"智能推送"逻辑：

1. **状态变更卡片**：任务状态变化时推送精美卡片（非文本）
2. **日报卡片**：每日定时推送当日任务汇总卡片
3. **看板置顶**：将最新看板卡片置顶到群聊（飞书支持置顶消息）
4. **紧急提醒**：critical 任务等待时发送加急卡片（红色头部）

```
┌─ 🔴 紧急任务等待 ─────────────────────┐
│ t142: 帮忙查 API 限频策略              │
│ 优先级: critical | 等待: 5min          │
│ 当前运行: 3/3 slot                     │
│                                       │
│ [🏃 立即处理]  [⏸️ 降级为普通]          │
└───────────────────────────────────────┘
```

#### 评估

| 维度 | 评分 |
|------|------|
| 用户体验 | ⭐⭐⭐⭐ 被动接收，无需主动查询 |
| 实现难度 | ⭐⭐ 简单（基于方案 A 扩展） |
| 额外权限 | 需要"置顶消息"权限（im:message:pin） |
| 额外配置 | 最小化 |
| 预计开发 | **3-5 小时** |
| 局限性 | 信息推送频率需控制，避免消息轰炸 |

### 3.3 方案对比总结

| 维度 | 方案 A（增强卡片） | 方案 B（Web 链接） | 方案 C（飞书应用） | 方案 D（智能推送） |
|------|-----|-----|-----|-----|
| 用户体验 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 实现难度 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| 维护成本 | 低 | 中 | 高 | 低 |
| 开发时间 | 2-4h | 4-8h | 1-2d | 3-5h |
| 无额外依赖 | ✅ | ❌(隧道) | ❌(域名/审核) | ✅ |

### 3.4 推荐方案

**Phase 1（立即实施）：方案 A + D 组合**

理由：
- 无需额外基础设施，利用现有 Lark Bot 权限
- 2-4 小时即可上线，立竿见影
- PATCH 更新机制避免消息刷屏
- 智能推送让 Carl 被动获取信息

**Phase 2（后续演进）：叠加方案 B**

当 Carl 需要更丰富的看板（历史统计、甘特图）时，再启动 Web Dashboard：
- 用 Python (Flask) 写一个单文件 Web 服务
- Cloudflare Tunnel 暴露
- 卡片按钮链接到 Web Dashboard

---

## 4. 综合实施路线图

### Phase 1：优先级系统 + 卡片看板（1 天）

| 步骤 | 内容 | 时间 |
|------|------|------|
| 1.1 | 数据模型变更：task_engine.py 添加 priority 字段 + 向后兼容 | 30min |
| 1.2 | 调度算法变更：_get_ready_tasks() 排序 | 30min |
| 1.3 | CLI 变更：task-manager.py add --priority / priority 命令 | 30min |
| 1.4 | Aging 机制：health_check() 中实现 | 20min |
| 1.5 | 卡片消息模板：生成 interactive card JSON | 1h |
| 1.6 | PATCH 更新机制：记录 message_id + 心跳更新 | 1h |
| 1.7 | 测试 + 调试 | 1h |

### Phase 2：智能推送 + 紧急提醒（半天）

| 步骤 | 内容 | 时间 |
|------|------|------|
| 2.1 | 状态变更卡片：complete/fail 时推送精美卡片 | 1h |
| 2.2 | 紧急等待提醒：critical 任务等待时发加急卡片 | 30min |
| 2.3 | 日报卡片整合：日报中包含任务统计 | 30min |
| 2.4 | 主 session 心跳流程集成 | 1h |

### Phase 3：Web Dashboard（可选，1 天）

| 步骤 | 内容 | 时间 |
|------|------|------|
| 3.1 | Flask Web 服务 + 简单前端 | 3h |
| 3.2 | Cloudflare Tunnel 配置 | 1h |
| 3.3 | 卡片按钮链接集成 | 30min |
| 3.4 | 自动刷新（WebSocket/轮询） | 1h |

### 文件变更清单

| 文件 | 变更 |
|------|------|
| `scripts/task_engine.py` | 添加 PRIORITY_MAP、修改 add()、新增 set_priority()、修改 _get_ready_tasks()、修改 health_check() |
| `scripts/task-manager.py` | 添加 --priority 参数、priority 子命令、列表显示优先级图标 |
| `scripts/task-dashboard.py` | 显示优先级信息 |
| `scripts/lark-card-builder.py` | **新建**：生成任务看板卡片 JSON |
| `scripts/lark-send-card.py` | **新建**：发送/更新卡片消息 |
| `data/task-board.json` | 自动迁移，无需手动改 |
| `HEARTBEAT.md` | 添加卡片更新逻辑 |

---

## 附录

### A. 卡片 JSON 示例

```json
{
  "config": {
    "wide_screen_mode": true,
    "enable_forward": true
  },
  "header": {
    "title": {
      "content": "📋 Luna 任务看板",
      "tag": "plain_text"
    },
    "template": "blue"
  },
  "elements": [
    {
      "tag": "div",
      "fields": [
        {
          "is_short": true,
          "text": {
            "tag": "lark_md",
            "content": "**🏃 运行中**\n2/3"
          }
        },
        {
          "is_short": true,
          "text": {
            "tag": "lark_md",
            "content": "**⏳ 等待中**\n3"
          }
        },
        {
          "is_short": true,
          "text": {
            "tag": "lark_md",
            "content": "**✅ 今日完成**\n5"
          }
        }
      ]
    },
    {
      "tag": "hr"
    },
    {
      "tag": "div",
      "text": {
        "tag": "lark_md",
        "content": "🔴 **[t138]** 帮忙查 API 限频策略 ⏱5min\n🟢 **[t137]** 每日检查 ⏱12min"
      }
    },
    {
      "tag": "hr"
    },
    {
      "tag": "div",
      "text": {
        "tag": "lark_md",
        "content": "**⏳ 等待中**\n🟡 [t139] 研究 GraphQL 方案 ← t138\n🔵 [t140] 整理 docs 目录"
      }
    },
    {
      "tag": "note",
      "elements": [
        {
          "tag": "plain_text",
          "content": "🕐 更新于 08:30 SGT | 下次心跳约 09:00"
        }
      ]
    }
  ]
}
```

### B. PATCH 更新 API 示例

```python
# 更新已发送的卡片消息
def update_card(message_id, card_json):
    req = urllib.request.Request(
        f"https://open.larksuite.com/open-apis/im/v1/messages/{message_id}",
        data=json.dumps({"content": json.dumps(card_json)}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )
    urllib.request.urlopen(req, timeout=10)
```

### C. 优先级系统完整改动伪代码

```python
# task_engine.py 改动汇总

PRIORITY_MAP = {"critical": 4, "high": 3, "normal": 2, "low": 1}
PRIORITY_ICONS = {"critical": "🔴", "high": "🟡", "normal": "🟢", "low": "🔵"}
AGING_THRESHOLD = 6

class TaskEngine:

    @staticmethod
    def load_board():
        board = ...  # 现有逻辑
        for t in board.get("tasks", []):
            if "priority" not in t:
                t.setdefault("priority", "normal")
                t.setdefault("priority_value", 2)
                t.setdefault("priority_boosted", False)
                t.setdefault("queued_heartbeats", 0)
        return board

    def add(self, description, source_chat=None, depends_on=None, priority="normal"):
        task = {
            ...,
            "priority": priority,
            "priority_value": PRIORITY_MAP.get(priority, 2),
            "priority_boosted": False,
            "queued_heartbeats": 0,
        }

    def set_priority(self, task_id, priority):
        ...

    def _get_ready_tasks(self, board, just_completed=None):
        ready = [queued tasks with deps met]
        ready.sort(key=lambda t: (-t.get("priority_value", 2), t.get("created", "")))
        return ready

    def health_check(self):
        ...  # 现有逻辑
        # 新增 aging
        for t in board["tasks"]:
            if t["status"] == "queued":
                t["queued_heartbeats"] = t.get("queued_heartbeats", 0) + 1
                if (t["queued_heartbeats"] >= AGING_THRESHOLD
                    and t.get("priority_value", 2) < 3
                    and not t.get("priority_boosted")):
                    t["priority_value"] += 1
                    t["priority_boosted"] = True
```

---

> **结论**：优先级系统 + 卡片看板可以在 1 天内落地，显著提升 Carl 对任务的掌控力。推荐先做 Phase 1 + Phase 2（约 1 天），Phase 3 视需求再启动。
