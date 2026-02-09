# Luna 系统架构全景图

> 📅 整理日期：2026-02-08  
> 📍 运行环境：AWS EC2 (Linux 6.14.0-1018-aws, x64)  
> 🏠 主机名：ip-10-1-26-47  

---

## 一、整体架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        外部接入层                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Lark/飞书    │  │  OpenClaw    │  │  Tailscale Funnel       │  │
│  │  Webhook     │  │  WebChat     │  │  (公网入口)              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                 │                      │                  │
│         ▼                 ▼                      │                  │
│  ┌──────────────────────────────────┐            │                  │
│  │  OpenClaw Gateway (port 18789)   │◄───────────┘                  │
│  │  模式: local, bind: loopback     │                               │
│  └──────────┬───────────────────────┘                               │
└─────────────┼───────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        核心引擎层                                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Agent: main                                                   │ │
│  │  ├── Main Session (直接对话)                                    │ │
│  │  ├── Heartbeat (每 5 分钟轮询)                                  │ │
│  │  └── Subagents (子任务，最多 8 并发)                             │ │
│  │      ├── periodic      (定期检查: 邮件+日历+TODO)               │ │
│  │      ├── comments      (Wiki 文档评论检查)                      │ │
│  │      ├── research      (后台研究任务)                           │ │
│  │      ├── dailyReport   (每日日报)                               │ │
│  │      └── morningGreeting (早安日程提醒)                          │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Session 隔离策略: per-channel-peer                            │ │
│  │  每个用户 × 每个渠道 = 独立 session                             │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        模型层                                       │
│  ┌────────────────────────┐  ┌──────────────────────────────────┐  │
│  │  主模型 (antigravity)   │  │  备用模型 (moonshot)             │  │
│  │  Claude Opus 4.6       │  │  Kimi K2.5                      │  │
│  │  (thinking/reasoning)  │  │  contextWindow: 256K            │  │
│  │  contextWindow: 1M     │  │  maxTokens: 8192                │  │
│  │  maxTokens: 16384      │  │  baseUrl: api.moonshot.cn       │  │
│  │  via API 代理           │  └──────────────────────────────────┘  │
│  │  (localhost:8080→      │                                       │
│  │   Tailscale /api)      │  ┌──────────────────────────────────┐  │
│  └────────────────────────┘  │  第三模型 (antigravity)           │  │
│                               │  Gemini 3 Pro High              │  │
│  Fallback 链:                 │  contextWindow: 1M              │  │
│  Claude → Gemini → Kimi      │  maxTokens: 8192                │  │
│                               └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        工具 & 外部服务层                              │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌────────────────────┐   │
│  │ Lark API │ │ Brave    │ │ Browser   │ │ 系统工具           │   │
│  │ (Bot+    │ │ Search   │ │ Use (MCP) │ │ (exec, read,      │   │
│  │  OAuth)  │ │          │ │           │ │  write, edit...)   │   │
│  └──────────┘ └──────────┘ └───────────┘ └────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        数据持久层                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  workspace/                                                  │  │
│  │  ├── SOUL.md, AGENTS.md, MEMORY.md, HEARTBEAT.md  (核心配置) │  │
│  │  ├── TOOLS.md                                (工具本地笔记)  │  │
│  │  ├── memory/                                  (每日记忆)      │  │
│  │  │   ├── YYYY-MM-DD.md                       (每日日志)      │  │
│  │  │   ├── research/                           (研究报告)      │  │
│  │  │   └── heartbeat-state.json → data/        (已移)         │  │
│  │  ├── data/                                    (运行数据)      │  │
│  │  │   ├── heartbeat-state.json                (心跳状态)      │  │
│  │  │   ├── lark-user-token.json                (OAuth token)  │  │
│  │  │   ├── backlog.md                          (任务队列)      │  │
│  │  │   ├── tracked-docs.json                   (监控文档列表)  │  │
│  │  │   ├── comment-state.json                  (评论处理状态)  │  │
│  │  │   ├── todo-state.json                     (TODO 状态)     │  │
│  │  │   ├── calendar-categories.md              (日历分类配色)  │  │
│  │  │   ├── important-dates.json                (纪念日)       │  │
│  │  │   └── quota-snapshots.jsonl               (用量快照)     │  │
│  │  ├── scripts/                                 (自动化脚本)    │  │
│  │  └── people/, projects/                       (人脉/项目)    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Lark Wiki 知识库                                            │  │
│  │  ├── Luna 数字员工协同 (7604126789916479197) — 公共            │  │
│  │  └── Carl 私人知识库 (7604150806383693538)   — 私人            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、定时任务体系

### 2.1 心跳驱动的 LLM 定时任务

> **架构选择原因**：OpenClaw 原生 cron 有 bug（`every` 类型 job 永远不执行），因此所有需要 LLM 的定时任务统一由心跳（5 分钟间隔）+ `sessions_spawn` 驱动。

| 任务名 | Key | 间隔 | 超时 | 说明 | 深夜规则 |
|--------|-----|------|------|------|----------|
| 定期检查 | `periodic` | 30 分钟 | 240s | 邮件 + 日历 + TODO + 邮件→日历自动同步 | 23:00-07:00 跳过 |
| 文档评论检查 | `comments` | 30 分钟 | 240s | 检查 Wiki 文档未解决评论 | 23:00-07:00 跳过 |
| 后台研究 | `research` | 5 分钟 | 1800s | 从 backlog.md 取下一个未完成任务做研究 | 24h 运行 |
| 每日日报 | `dailyReport` | 每天 04:00 SGT | 240s | 生成昨日日报，写入 Wiki | — |
| 早安提醒 | `morningGreeting` | 每天 07:00 SGT | 240s | 今日日程提醒 | — |

**执行流程**：
1. 心跳触发 → 读取 `data/heartbeat-state.json`
2. 计算每个任务距上次执行的时间差
3. 到期任务 → `sessions_spawn` 创建子任务
4. 立即更新 `heartbeat-state.json` 时间戳
5. 无到期任务 → 回复 `HEARTBEAT_OK`

**状态文件示例** (`data/heartbeat-state.json`)：
```json
{
  "lastChecks": {
    "periodic": 1770548062370,
    "comments": 1770548062370,
    "research": 1770548957969
  }
}
```

### 2.2 系统 crontab（纯脚本，不需要 LLM）

| 时间表达式 | 脚本 | 说明 |
|-----------|------|------|
| `0 * * * *` | `scripts/lark-token-refresh.py --check` | Lark OAuth token 刷新（每小时整点） |
| `5 * * * *` | `scripts/token-hourly-stats.py last` | Token 用量统计（每小时 :05） |
| `*/5 * * * *` | `scripts/cleanup-session-locks.sh` | 清理 session 锁文件（每 5 分钟） |

### 2.3 工作区脚本清单

| 脚本 | 用途 |
|------|------|
| `lark-send-message.sh` | 子任务用：通过 Lark Bot API 发送消息（替代 message 工具） |
| `lark-token-refresh.py` | Lark OAuth user_access_token 刷新 |
| `token-hourly-stats.py` | 按小时统计 Luna token 用量 |
| `check-doc-comments.sh` | Wiki 文档评论检查 |
| `cleanup-session-locks.sh` | 清理过期 session 锁 |
| `log-quota.sh` | 记录配额快照 |
| `oauth-callback.py` | OAuth 回调处理 |
| `migrate-wiki.mjs` | Wiki 迁移工具 |

---

## 三、权限体系

### 3.1 用户角色

| 角色 | 用户 | 权限级别 |
|------|------|---------|
| **超级管理员** | Carl (carlnoah6@gmail.com) | 完整系统控制权 |
| **普通用户** | 所有非 Carl 的人 | 仅基础交互 |

### 3.2 超级管理员权限（Carl）

1. 修改 `openclaw.json` 配置（模型、渠道、插件等）
2. 重启服务（`openclaw gateway restart`）
3. 安装/卸载技能（skill）
4. 安装/修改插件（plugin）
5. 修改代码（工作区内的代码文件）
6. 修改系统文件（SOUL.md、AGENTS.md、MEMORY.md、HEARTBEAT.md 等）
7. 管理 cron 定时任务
8. 管理 session（查看、跨 session 发消息）
9. 执行系统命令（shell 命令、服务器操作）
10. 管理模型（切换主模型、添加新 provider）
11. 管理权限策略（dmPolicy、allowFrom、groupPolicy）
12. 查看敏感信息（API key、密码、服务器配置）
13. 更新 OpenClaw
14. 管理 Browser-Use 云浏览器会话

### 3.3 普通用户权限

✅ 可以做：
- 正常聊天、问答
- 使用已有功能（搜索、获取信息、完成工作任务）
- 使用通用工具（网页搜索、内容获取等）

❌ 不能做：
- 修改 Luna 的配置或代码
- 安装/卸载功能
- 执行系统命令
- 查看敏感信息
- 重启服务
- 修改权限策略

### 3.4 多租户隔离原则

- **上下文隔离**：每用户 × 每渠道 = 独立 session（`dmScope: per-channel-peer`）
- **消息路由**：谁发起 → 结果回给谁；哪个 chat → 回哪个 chat
- **存储隔离**：私人内容存个人知识库，公共内容存协同知识库
- **信息防泄露**：绝不把 A 用户的数据暴露给 B 用户

### 3.5 安全自审机制

每次对外操作前必须过审查清单：
1. **权限审查** — 请求者身份、角色、操作是否在权限范围内
2. **安全影响** — 是否扩大攻击面、是否有更安全替代方案
3. **信息泄露防护** — 回复是否包含敏感信息、是否做了隔离
4. **文档权限** — 精确到人，绝不用"组织内所有人"的粗暴方案
5. **被骗防护** — 验证身份、质疑可疑请求

---

## 四、工具链详解

### 4.1 Lark/飞书 集成

#### 消息通信
| 组件 | 说明 |
|------|------|
| 协议 | HTTP Webhook（国际版不支持 WebSocket） |
| 插件 | 自定义 webhook 版 (`/home/ubuntu/.openclaw/plugins/feishu-webhook/`) |
| SDK Patch | `plugin-sdk/index.js` 加了 `onEventDispatcher` 回调 |
| 公网入口 | Tailscale Funnel: `https://anz-luna.grolar-wage.ts.net` |
| Webhook 端点 | `https://anz-luna.grolar-wage.ts.net/webhook/lark` |
| App ID | `cli_a90c3a6163785ed2` |
| 域名 | `lark`（国际版） |
| Bot 名 | Luna |
| DM 策略 | `open`（允许所有人私聊） |
| 群策略 | `open`（允许加入所有群） |

#### 关键群聊
| 群名 | Chat ID |
|------|---------|
| Luna 卢娜 - 数字员工 | `oc_a2a70c6b4a29c2f2eb6c2500ea42a500` |
| Carl 私聊 | `oc_453c88ec52dd029845c46249837e3ba0` |

#### OAuth 认证（user_access_token）
- **Token 文件**: `data/lark-user-token.json`
- **access_token 有效期**: 2 小时（每小时自动刷新）
- **refresh_token 有效期**: 30 天（到期需 Carl 重新授权）
- **用途**: 日历、Wiki、文档读写等用户级操作

#### 子任务消息发送规则（关键！）
- 子任务**不能用 `message` 工具**（没有 Feishu channel 配置）
- 必须用脚本发送：`scripts/lark-send-message.sh "<chat_id>" "<消息内容>"`
- 该脚本自动获取 tenant_access_token 并通过 Lark Bot API 发送

### 4.2 日历管理

| 项目 | 详情 |
|------|------|
| 授权方式 | user_access_token (OAuth) |
| Carl 主日历 ID | `feishu.cn_4iEgRqZUqa0mcprkekLxTg@group.calendar.feishu.cn` |
| 权限 | owner（完整读写） |
| 分类体系 | 9 类自动配色（详见 `data/calendar-categories.md`） |
| 功能 | 创建/修改/删除日程、时间追踪、历史查询、时间统计 |

### 4.3 Wiki 知识库

| 知识库 | Space ID | 用途 | 访问级别 |
|--------|----------|------|---------|
| Luna 数字员工协同 | `7604126789916479197` | 日报、Token统计、系统文档 | 公共 |
| Carl 私人知识库 | `7604150806383693538` | AI 研究、个人项目、私人任务 | 仅 Carl+Luna |

**重要节点**（Carl 私人知识库）：
- 🔬 AI 研究：`NRxIwuk5Mi0fyNkzhCWlSKxXgkh`
- 🔬 从头训练模型：`OZmqwn4yviwsY2k1JBblkgTYg5c`
- 🔬 AI 玩小丑牌：`HDiUwEllbiJIdskrKAZlojadgsc`

**权限边界**：只读写以上两个知识库，禁止触碰 Carl 的其他 5 个知识库。

**文档评论自动检查**：
- 被监控文档列表：`data/tracked-docs.json`
- 评论处理状态：`data/comment-state.json`
- 每次检查递归扫描整个 Wiki 空间，自动发现新文档

### 4.4 网页搜索 & 内容获取

| 工具 | Provider | 说明 |
|------|----------|------|
| `web_search` | Brave Search API | 最多 10 结果，缓存 60 分钟 |
| `web_fetch` | 内置 | HTML→Markdown 提取，免费优先使用 |
| Browser Use | MCP (Cloud) | 付费（按时长计费），**使用前需确认** |

### 4.5 API 代理（Token 用量追踪）

| 项目 | 详情 |
|------|------|
| 端口 | `localhost:8180` |
| 管理端点 | `GET /admin/usage/daily?date=YYYY-MM-DD` |
| 认证 | `Bearer sk-admin-luna2026` |
| 用途 | 查询外部用户（Jose、Alex 等）的 API 用量 |

**Luna 自身用量**不走代理统计，直接从 session 日志文件解析（更准确）。

### 4.6 MCP 工具后端

| 名称 | 命令 | 用途 |
|------|------|------|
| `browser-use-mcp` | `npx @browser-use/mcp-server` | 云浏览器自动化 |
| `lark-mcp` | `npx @larksuiteoapi/lark-mcp` | Lark API 的 MCP 封装 |

---

## 五、模型配置

### 5.1 模型列表

| 模型 | Provider | 别名 | 推理能力 | 上下文窗口 | 最大输出 |
|------|----------|------|---------|-----------|---------|
| `claude-opus-4-6-thinking` | antigravity | Claude | ✅ | 1M | 16384 |
| `gemini-3-pro-high` | antigravity | Gemini | ✅ | 1M | 8192 |
| `kimi-k2.5` | moonshot | Kimi | ❌ | 256K | 8192 |

### 5.2 模型策略

- **主模型**: `antigravity/claude-opus-4-6-thinking`
- **Fallback 链**: Claude → Gemini → Kimi
- **计费回退冷却**: 0.5 小时（antigravity），最大 6 小时
- **API 代理路由**: antigravity 通过 Tailscale 内网 (`anz-luna.grolar-wage.ts.net/api`)

---

## 六、网络架构

```
互联网
  │
  ▼
Tailscale Funnel (公网 HTTPS)
  │  https://anz-luna.grolar-wage.ts.net
  │
  ├── /webhook/lark     → Feishu webhook 插件
  ├── /api              → API 代理 (模型请求转发)
  └── /oauth/callback   → OAuth 回调处理
  │
  ▼
OpenClaw Gateway (localhost:18789)
  │  认证: password (Luna2026!@#)
  │  模式: local, bind: loopback
  │
  ▼
内部服务
  ├── API 代理 (localhost:8180) — Token 用量追踪
  └── OpenClaw 主进程 — 处理所有 agent 逻辑
```

---

## 七、已知限制 & Workaround

### 7.1 OpenClaw cron bug（严重）
- **问题**: `every` 类型的 cron job 永远不执行
- **根因**: `ensureLoaded` 中 `recomputeNextRuns` 在 `runDueJobs` 之前运行，每次重算都把 `nextRunAtMs` 推到未来
- **Workaround**: 所有需要 LLM 的定时任务改用心跳（5min）+ `sessions_spawn` 驱动
- **状态**: 未修复，等待 OpenClaw 上游更新

### 7.2 Lark 国际版不支持 WebSocket
- **问题**: 官方 `@openclaw/feishu` 插件仅支持 WebSocket 长连接
- **Workaround**: Fork 创建 webhook 版插件 (`/home/ubuntu/.openclaw/plugins/feishu-webhook/`)
- **副作用**: OpenClaw 更新后需要重新 patch SDK bundle (`plugin-sdk/index.js`)
- **备份**: 原始插件备份在 `/home/ubuntu/feishu-original-backup/`

### 7.3 子任务 message 工具不可用
- **问题**: `sessions_spawn` 创建的子任务没有 Feishu channel 配置
- **Workaround**: 子任务用 `scripts/lark-send-message.sh` 脚本直接发消息
- **注意**: Wiki 操作（curl + user_access_token）不受此限制影响

### 7.4 Main session 路由串台
- **问题**: main session 的 `deliveryContext.to` 被最后一个触发它的群绑定，多群场景会串台
- **Workaround**: 所有需要发到特定群的消息，子任务必须自己显式指定目标 chat_id
- **规则**: 心跳主 session 收到子任务回传后回复 `NO_REPLY`

### 7.5 OAuth refresh_token 过期
- **问题**: refresh_token 有效期 30 天，过期后需要 Carl 手动重新授权
- **Workaround**: 目前无自动化方案，到期提醒 Carl 点授权链接
- **监控**: 可在 token 刷新脚本中检测并预警

### 7.6 Browser Use 付费
- **问题**: 按使用时长计费
- **Workaround**: 优先用免费方式（`web_fetch`、`web_search`），只有确实读不到时才考虑
- **规则**: 使用前必须和调用者确认

### 7.7 Lark 文档修改的叠加问题
- **问题**: 早期修改文档时会在旧内容下追加新内容，导致重复
- **Workaround**: 先用 batch_delete 清空子 block，再写入新内容
- **API**: `DELETE /open-apis/docx/v1/documents/{doc}/blocks/{doc}/children/batch_delete`
- **规则**: 修改 = 更新，不是叠加！

---

## 八、配置变更流程（必须遵守）

修改 `openclaw.json` 时必须严格按以下步骤：

1. **修改前** — 读取当前配置，理解结构
2. **修改** — 编辑配置文件
3. **验证** — 运行 `openclaw doctor` 确认 Errors: 0
4. **重启** — 运行 `openclaw gateway restart` 使配置生效

**配置要点**：
- `auth.profiles` 只允许 `provider`、`mode`、`email` 字段，**不能放 `apiKey`**
- API key 放在 `models.providers.<name>.apiKey`
- 修改前先查看 config schema 确认字段合法

---

## 九、数据流示意

### 9.1 用户消息处理流

```
用户在 Lark 发消息
  → Lark 推送 webhook 到 Tailscale Funnel
  → Feishu webhook 插件接收
  → OpenClaw 路由到对应 session（per-channel-peer）
  → Agent 处理（可能调用工具: 搜索/日历/Wiki 等）
  → 结果通过 Lark Bot API 回复
```

### 9.2 心跳定时任务流

```
OpenClaw 每 5 分钟触发心跳
  → 读取 HEARTBEAT.md → 读取 heartbeat-state.json
  → 判断哪些任务到期
  → 到期任务: sessions_spawn 启动子任务
  → 子任务独立执行，用脚本发消息/用 API 写 Wiki
  → 更新 heartbeat-state.json
  → 主 session 收到回传 → 回复 NO_REPLY
```

### 9.3 Token 生命周期

```
Carl 首次授权 → OAuth 回调保存 token
  → access_token (2h) ← 每小时 crontab 自动刷新
  → refresh_token (30d) ← 到期需手动重新授权
```

---

## 十、文件结构速查

```
/home/ubuntu/.openclaw/
├── openclaw.json                    # 主配置文件
├── plugins/
│   └── feishu-webhook/              # 自定义 Lark webhook 插件
├── agents/main/sessions/*.jsonl     # Session 日志（含 token 用量）
├── subagents/*.jsonl                # 子任务日志
└── workspace/                       # 工作区（agent 的家）
    ├── SOUL.md                      # 人格定义
    ├── AGENTS.md                    # 行为准则
    ├── MEMORY.md                    # 长期记忆
    ├── HEARTBEAT.md                 # 心跳任务定义
    ├── TOOLS.md                     # 工具本地笔记
    ├── USER.md                      # 用户信息
    ├── data/
    │   ├── backlog.md               # 后台任务队列
    │   ├── heartbeat-state.json     # 心跳状态
    │   ├── lark-user-token.json     # OAuth token
    │   ├── tracked-docs.json        # 被监控文档列表
    │   ├── comment-state.json       # 评论处理状态
    │   ├── todo-state.json          # TODO 状态
    │   ├── calendar-categories.md   # 日历分类
    │   ├── important-dates.json     # 重要日期
    │   ├── quota-snapshots.jsonl    # 用量快照
    │   └── write_wiki.py            # Wiki 写入工具
    ├── scripts/
    │   ├── lark-send-message.sh     # 消息发送脚本
    │   ├── lark-token-refresh.py    # Token 刷新
    │   ├── token-hourly-stats.py    # 用量统计
    │   ├── check-doc-comments.sh    # 评论检查
    │   ├── cleanup-session-locks.sh # 锁清理
    │   ├── log-quota.sh             # 配额日志
    │   ├── oauth-callback.py        # OAuth 回调
    │   └── migrate-wiki.mjs         # Wiki 迁移
    └── memory/
        ├── YYYY-MM-DD.md            # 每日记忆
        └── research/                # 研究报告（15+ 份）
```

---

*文档结束。此文档仅供内部参考，不同步到 Wiki。*
