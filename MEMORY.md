# MEMORY.md - Luna's Long-Term Memory

## 👨‍👩‍👧‍👦 Carl 的家庭和生活

### 家庭成员
- **Carl**（Bo Li）— 1984-04-29 生日，新加坡
- **元宝**（李青舟）— 大儿子，2019-03-22 生日（快 7 岁），每周日 9:30 上架子鼓课
  - 学校: SAS (Singapore American School), 40 Woodlands St 41
  - 中文老师: 程玲燕 Lingyan Cheng (lcheng@sas.edu.sg), 教室 ES455
  - 会弹电子琴，喜欢音乐
- **朵朵**（李筱禾）— 小女儿，2021-05-16 生日（快 5 岁）

### 🎂 元宝 7 岁生日聚会（2026-03-29 周日上午，在家）
19 位嘉宾：鱼丸、米粒、天天、森宝、Apollo、Felix、Chris、星晨、DC、Oliver、Zaeer、David、Eddy、Yucheng、Yusen、Ryan、Seito、Nova、豆豆
- 详细名单: `data/yuanbao-birthday-party-2026.md`
- ⚠️ 当天晚上 20:00 还有汪苏泷演唱会

### 重要联系人（详细档案在 people/ 目录）
- **马原** — Carl 投资的公司创始人（多个公司和网站），约每 2 周见一次
  - 地点: The Cavendish, 85 Science Park Drive, S118259 + Kent Ridge Park 徒步
  - 孩子: 豆豆（在元宝生日邀请名单上）
  - 详见: `people/ma-yuan.md`
- **卢琦**（鱼丸妈妈）— Carl 的好友
  - 孩子: 鱼丸、森宝（都在元宝生日邀请名单上）
  - 详见: `people/lu-qi.md`
- **Junyi** — 朋友，一起看汪苏泷演唱会 3/29

### 即将到来的活动
- 2/11 🍻 和孙枢吃饭 Brewerkz East Coast Park
- 2/12 💎 NAFA 珠宝制作课程（首堂，每周四 19-22 到 4/2）
- 2/13 🎹 元宝春节表演《恭喜恭喜》@ SAS → 下午去机场
- 2/13-2/18 🧧 春节出行（不在新加坡，课外课/心理/普拉提全取消）
- 2/22 🎭 Charlie Cook's Favourite Book（儿童剧）
- 3/8 🎵 SSO Pops
- 3/9 🎵 SSO Chamber
- 3/26 🎵 Harry Potter 音乐会
- 3/29 🎂 元宝生日聚会（上午）+ 🎵 汪苏泷演唱会（晚上）
- 4/15 🎭 Les Misérables

### 重要日期提醒
- 记录在 `data/important-dates.json`，包含提前提醒天数
- 定期约见的人: `data/recurring-meetings.json`

### 每周日程 Review 流程
- 每周日 10:00 自动生成下周日程 Review
- 检查 `recurring-meetings.json` 里谁该约了
- 发给 Carl 确认 → 帮约时间 → 创建日历事件

## ⚠️ 核心工作原则

### 说一遍就够了——立刻固化到系统
- Carl 说的任何信息 → **立刻写入文件**（规则→MEMORY.md，流程→脚本，事件→memory/，人物→people/）
- **收到数据立刻写文件，零例外** — 不能只在对话中维护
- 如果 Carl 需要重复第二遍 = Luna 失职

### 独立验证，不盲信
- 做决定前先找 ground truth——查日志、跑代码、验证数据
- 用户报告可能有误，系统报错可能只是暂时的

### 改动前先确认
- 修改系统文件或代码前和 Carl 确认
- 内部探索（读文件、查日志）可以自主

### API Proxy 绝对不碰本地代码（2026-02-12 血的教训）
- **绝对禁止直接修改 `/home/ubuntu/api-proxy/` 下的任何文件**，包括 debug log
- **唯一流程**：GitHub branch → PR → CI → merge → 本地 `git pull` → `systemctl restart`
- **教训**：2/12 为加 debug log 直接改本地 → 撤回时 server.py 丢失 + admin.py 被覆盖 → API Proxy 完全 DOWN
- 排查时只能看日志（journalctl）和 curl 测试，**不碰源码**

### 批量行动，减少中断
- 攒一批改动一起做，不要改一个就重启一次

### OpenClaw Session 管理（系统事实，不可想当然）
- **Session 状态由 `sessions.json` 驱动**，OpenClaw 从文件加载状态，不是纯内存缓存
- **清 session 两步走，无需重启**：
  1. 清空 `agents/main/sessions/<uuid>.jsonl`（transcript）
  2. 重置 `sessions.json` 中对应 session 的 `systemSent=false`、`totalTokens=0`
- **立即生效**——下次收到该 session 的消息时，OpenClaw 会重新初始化
- **绝不要因为"清了 session"就重启 gateway**，这是多余操作
- Lock 文件（`.jsonl.lock`）可能残留，手动 `rm` 即可
- 子任务 `totalTokens=0` = 从未启动，直接标记 failed

### ⚠️ 固化 = 代码，不是 prompt（2026-02-12 反复犯错的总结）

**核心原则**：凡是能用代码/脚本保证的流程，绝不依赖 LLM 自觉遵守。

**今天犯的所有错误都有同一个根因**——默认用"LLM 记住"而不是"代码强制"：

| 错误 | 我做了什么 | 应该怎么做 |
|------|-----------|-----------|
| 忘了用规划器 | 手动列步骤 | 查 planner.py，用代码流程 |
| 手编图标 | 凭记忆写 📍⏳ | 图标在 format_plan() 里写死，不该自编 |
| 主 session 做重活 | 自己 npm pack + 读源码 | replan 出去，代码调度保证 |
| 新需求没进规划器 | 直接讨论方案 | 先 replan，代码跟踪保证不丢 |
| watcher 重启放 HEARTBEAT.md | 写在 prompt 里靠自觉 | 写在 check-restart.sh 里代码执行 |

**检查清单（每次"固化"前自问）**：
1. 这个流程能不能用脚本/代码保证？→ 能就写代码
2. 如果 LLM 忘了这条规则，会出什么问题？→ 会出问题就不能靠 prompt
3. 有没有现成的代码流程可以复用？→ 有就用，不要自己发明

### 📋 规划器（planner.py）— 编排层（2026-02-12 review 后固化）

**定位**：建在 `task-manager.py` 之上的编排层，每个群聊最多一个活跃 planner，步骤和任务面板 1:1 映射。
**数据存储**：`data/planner/<chat_id后8位>.json`

**图标体系（代码写死在 `format_plan()` 中，禁止自编）**：

| 图标 | 含义 | 上下文 |
|------|------|--------|
| `📋` | Plan 标题 | `📋 Plan — <goal>` |
| `✅` | done | 已完成步骤（附 result summary，≤60 字符） |
| `🔄` | running | 执行中步骤（附耗时分钟数） |
| `❌` | failed | 失败步骤（附 error，≤60 字符） |
| `⬜` | pending | 待执行步骤 |
| (隐藏) | cancelled | cancelled 步骤不显示 |
| `🟢` / `✅` / `🚫` | list 命令 | active / completed / cancelled |

**10 个命令**：

| 命令 | 说明 |
|------|------|
| `init <chat_id> <goal> <steps_json>` | 创建计划，自动建第一步任务并标记 running |
| `show <chat_id>` | 显示计划状态（format_plan 格式） |
| `step-done <chat_id> <step_id> "结果"` | 标记完成 → 自动推进下一步 → 发 Lark 消息 |
| `step-fail <chat_id> <step_id> "错误"` | 标记失败，**不自动推进**（等人工介入） |
| `replan <chat_id> <new_steps_json>` | 替换 pending/failed 步骤，保留 done/running |
| `cancel <chat_id>` | 取消整个计划（running 任务也取消） |
| `advance <chat_id>` | 心跳推进：无 running 且有 pending → 启动下一步 |
| `check-advances` | 扫描所有活跃 planner，报告需要推进的（心跳用） |
| `list` | 列出所有 planner（active 优先） |
| `find-by-task <task_id>` | 反查某个 task 属于哪个 plan |

**steps_json 格式（init 和 replan 统一）**：
```json
[{"title": "步骤描述", "prompt": "子任务详细指令"}]
```
- 也支持内部 key：`{"desc": "...", "detail": "..."}`
- 优先级：`title` > `desc` > `"Step N"`（描述）；`prompt` > `detail` > `""`（详情）
- 代码通过 `normalize_step()` 统一映射，init 和 replan 行为完全一致
- ⚠️ 2/12 修复前 init 不支持 title/prompt，导致 desc 全部 fallback 到 "Step N"

**关键机制**：
- **自动推进**：`step-done` → 创建下一步任务 → tm_add+tm_start → 发 Lark 状态 → schedule_advance
- **失败不推进**：`step-fail` 停在原地，需人工 replan 或 advance
- **Spawn prompt**：`build_spawn_prompt()` 自动附加 Planner Callback footer（step-done/step-fail 回调）
- **Lark 通知**：step-done / step-fail / replan / cancel / advance 都自动发 `format_plan()` 到群聊
- **Cron + Pending fallback**：schedule_advance 先试 `openclaw cron add`，失败则写 `data/planner-pending/<hash>.json`，由 check-advances（心跳调用）拾取
- **check-advances 安全**：只有无 running 步骤且有 pending 步骤时才报 advances_needed（2/12 修复了 pending 文件路径的误判 bug）

**与任务面板集成**：
- `init` → tm_add + tm_start（第一步）
- `step-done` → tm_complete → tm_add + tm_start（下一步）
- `step-fail` → tm_fail
- `cancel` → tm_cancel（running 任务）
- 每个步骤的 task_id 存在 step JSON 中

**使用原则**：
- 任何多步项目都用规划器，不要手动管理状态或图标
- 项目进行中 Carl 提新需求 → **立刻 replan**，不在主 session 做重活
- replan 保留 done/running，只替换 pending/failed/cancelled
- 绝不在主 session 做调查/分析（违反 OS 模式 <10 秒原则）

**历史教训**：
- 2/12：init 不支持 title/prompt → desc 全部是 "Step N"（已修复：normalize_step）
- 2/12：check-advances pending 文件路径不检查 has_running → 误报（已修复）
- 2/12：step-done 后 auto-advance 创建任务但不 spawn（cron 不可用 + pending 要等心跳）
- 2/12：子任务搞混 task_id（t008 vs t009），因为 desc 都是 "Step N" 无法区分

### 📢 知识同步总线（2026-02-12 上线）
- **定位**：文件变更自动广播到所有活跃 session，保持多 session 认知同步
- **核心脚本**：`scripts/knowledge-sync.py`
- **命令**：
  - `check` — 检测文件变更，输出 JSON
  - `broadcast [--dry-run]` — 检测变更 → 生成带 diff 的通知 → `openclaw agent --session-id` 直接注入
  - `watch` — 启动 inotifywait 文件监听守护进程（写入即触发）
  - `notify <file> <summary>` — 手动通知
  - `status` / `diff <file>` / `init` — 辅助命令
- **启动/停止**：`bash scripts/start-knowledge-watcher.sh` / `bash scripts/stop-knowledge-watcher.sh`
- **日志**：`data/knowledge-watcher.log`
- **状态文件**：`data/knowledge-sync-state.json`（md5 + 内容快照）
- **监控文件**：SOUL.md（🔴高）、MEMORY.md（🟡中）、TOOLS.md / HEARTBEAT.md（🟢低）
- **机制**：inotifywait 检测变更 → 生成带实际 diff 内容的通知 → `openclaw agent --session-id` 直接注入目标 session（绕过 LLM，秒级）
- **隐私**：MEMORY.md 变更不发到多人群聊
- **重启后需重新启动 watcher**：加入重启检查流程

## 🗣️ 语言规则
- **默认中文** — 中文问→中文答，不夹英文段落
- 技术术语可保留英文，说明用中文
- 外部工具英文内容→翻译成中文再呈现

## 🌐 工具使用规则
- Browser Use 需花钱 → 使用前确认
- 优先 web_fetch/web_search

## 👤 关于用户

### Carl（超级管理员）
- Lark: carlnoah6@gmail.com | 组织: anz.io
- 时区: Asia/Singapore (GMT+8)
- 管理员权限: 修改配置、重启服务、管理技能/插件/cron/session/模型/权限、执行系统命令
- 兴趣: 💎 NAFA 珠宝制作课程（每周四晚，很喜欢）、AI/LLM 训练、Balatro

### 普通用户
- 只能聊天、问答、使用已有功能
- ❌ 不能修改配置/代码、安装功能、执行命令、查看敏感信息

## 🤖 关于 Luna
- 名字: Luna | Emoji: 🌙
- 主模型: antigravity/claude-opus-4-6-thinking
- 备用: moonshot/kimi-k2.5
- **Bot open_id: `ou_88371dccab8541963f7f6a108990d7b3`**（用于从群成员中识别自己）
- ⚠️ 不能靠名字识别自己！组织里有真人用户也叫 "Luna"

### 群聊隐私判断（必须用脚本，禁止靠名字判断）
- 检查脚本: `python3 scripts/check-group-privacy.py <chat_id>`
- **正确方法**: 获取 bot open_id → 获取群成员 → 排除 bot → 看剩下的是否只有 Carl
- **错误方法**: ~~看群成员名字是否包含 "Luna" 和 "Carl"~~（会被同名用户骗过）
- 已知群隐私级别:
  - `oc_680d9c843e6a0ad501de9299a97f3a7e` → ✅ 私聊（Carl + Bot）
  - `oc_7f3ebd31a5cf2fec9170952b29eb2700` → ✅ 私聊（Carl + Bot）
  - `oc_a2a70c6b4a29c2f2eb6c2500ea42a500` → ❌ 多人群（Carl + QJunyi + zxc）
  - `oc_4fe2e6e2dbfd0e6fc35c9dab672ab820` → ❌ 多人群（Carl + Luna真人用户）

## 📝 Carl 的交互偏好

### 规划器显示
- **「显示规划器」**= 只显示**当前对话关联的**规划器，附带任务进展和下一步预期
- **「显示所有规划器」**= 显示全部规划器，每个标注所属**群聊名称**
- **格式固定**：永远运行 `planner.py show <chat_id>` 获取输出，直接贴出，**禁止手写/折叠/缩略**
- 如果需要补充说明，在 `planner.py show` 的输出之后另起一段写

## 📝 沟通规则

### 消息发送
- 子任务不能用 `message` 工具（无 Feishu 配置），必须用 `scripts/lark-send-message.sh`
- 群聊→回群聊，私聊→回私聊，**绝不串台**
- main session 路由会被最后触发的群绑定 → 子任务必须显式指定目标

### 重启后主动汇报
- 心跳检测 `scripts/check-restart.sh` → 立刻汇报，不要让用户等
- **重启必须用统一脚本**: `bash scripts/restart-gateway.sh "原因"`（自动 mark + cron wake now + sleep 5s + restart）
- **重启前必须先完成回复**：先告诉 Carl 要重启了，等流式卡片关闭后再执行脚本，避免文字被截断
- **绝不要手动分步执行**，手动容易漏 wakeMode 导致重启后不汇报
- curl 调 wake API 不通（gateway 用 WebSocket JSON-RPC），只能用 `openclaw cron add --wake now`

### Feishu 流式卡片 Patch
- 原始 Patch 9 有 bug（内容重复），已用 Luna fix v4 修复
- Patch 脚本：`patches/apply-feishu-streaming-fix.py`（每次 OpenClaw 更新后运行）
- `onReplyStart` 是 per-session 回调（不是 per-turn），turn 切换检测在 `onPartialReply` 内完成
- 改 node_modules 必须用 `openclaw gateway restart`（全进程重启），config.patch/SIGUSR1 不加载新代码

### 流式卡片串台修复
- **根因**：`onAgentEvent` 用全局 `listeners$1`，所有 session 的 tool 事件广播到所有流式卡片
- **修复**：加 `expectedSessionKey` 过滤，只处理本 session 的事件
- Patch: `patches/fix-streaming-cross-session.py`

### 流式卡片 NO_REPLY 泄露修复
- **根因**：`close()` 时 `currentText` 为 "NO_REPLY"（非空），卡片正常关闭而不是删除
- **修复**：`close()` 检测 NO_REPLY/HEARTBEAT_OK，匹配时删除卡片
- Patch: `patches/fix-streaming-silent-reply.py`

### Lark 卡片按钮（交互式确认）
- 脚本：`scripts/send-confirm-card.sh <chat_id> "<标题>" "<内容>" "按钮文字:value" ...`
- 用户点击后 Luna 收到: `[按钮] <value>`
- 架构：Lark → `/api/oauth/callback`（api-proxy）→ 转发到 `/webhook/lark`（OpenClaw）→ 合成消息
- 卡片用 v1 schema（无 `"schema": "2.0"`），v2 不支持 `action` tag
- 「回调配置」和 OAuth 共用 URL，不能改

### 文档操作
- 修改 Wiki 后必须附链接: `https://fg9w9yu3odc.sg.larksuite.com/wiki/{node_token}`
- 修改 = 更新（替换），不是追加
- Wiki 共享文档：子任务不触碰，主流程统一"清空+重写"

### 其他
- 写入记忆后必须告知: 「📝 已更新 `文件名`：内容摘要」
- 子任务 prompt 必须用文件（`data/<task>-prompt.md`），不要临时编
- 日报三渠道: Lark 聊天 + Wiki + 邮件
- 每日复盘（`DAILY-REVIEW.md`）是日报的前置流程
- 日期/时间必须用代码验证，绝不心算
- 长任务必须给进度反馈
- 重启前必须检查子任务

## 📅 Lark 日历
- 查日历用: `python3 scripts/lark-calendar-today.py YYYY-MM-DD`
- Token: `data/lark-user-token.json`（2h 有效，每小时刷新）
- 日历功能: 日程管理 + 时间追踪 + 历史查询 + 时间统计
- **10 色分类体系**（2026-02-10 确定，见 `data/calendar-categories.md`）
  - 🔵 蓝 `-11631619` 💻 工作 | 🟠 橙 `-30720` 📅 会议 | 🩵 青绿 `-16722247` 📖 学习
  - 💜 靛蓝 `-10392859` 🧠 心理 | 🩷 粉 `-963671` 👶 家庭 | 🟡 黄 `-14838` 🍻 社交
  - 🟢 绿 `-13318364` 🏃 运动 | 🟣 紫 `-3066159` 🎮 休闲 | 🔘 灰 `-6511959` 🏠 生活 | 🔴 红 `-562844` 🔴 重要
- 人脉管理: `people/` | 项目追踪: `projects/` | 重要日期: `data/important-dates.json`
- **循环事件操作经验**（2026-02-12 实战总结）：
  - **Lark 不支持直接删除虚拟循环实例**（DELETE 会 404），这是 API 限制
  - **删除 master event（`_0`）= 删除整个系列**，包括所有历史记录，不可恢复
  - **跳过某天的正确方式**：截断（UNTIL）+ 重建，不是删除
    1. 给原事件加 `UNTIL=跳过日前一天` → 保住历史 A
    2. 新建循环事件从跳过日之后的第一个匹配日开始 → 恢复 C D E...
    3. 结果：两个独立系列，中间跳过了 B
  - **工具**: `python3 scripts/skip-recurring-dates.py <event_id_0> <skip_start> <skip_end>`
  - **特殊情况**：如果 UNTIL 本身就是今天（最后一次），直接删 master 即可（没有未来要保留的）
  - 详见 `memory/reference/technical-details.md`

## 📚 Wiki & Lark
- Luna 协同知识库: Space `7604126789916479197`（公共内容）
- Carl 私人知识库: Space `7604150806383693538`（私人任务）
- 其他知识库**禁止触碰**
- 详细技术信息: `memory/reference/technical-details.md`

## 🏢 多租户原则
- 上下文隔离、消息路由、存储隔离、不泄露
- 谁发起→结果回给谁；私聊→私人库；群聊→协同库
- 安全 > 便利，权限精确到人

## 📝 重要事件

### 2026-02-10 (续)
- **MemGate 开源项目上线** — Privacy Guard 发布为独立开源项目
  - GitHub: https://github.com/carlnoah6/memgate (carlnoah6 账号)
  - 网站: https://carlnoah6.github.io/memgate/ (GitHub Pages)
  - 域名: memgate.ai（因价格原因暂不购买，使用 GitHub Pages）
  - 定位: 平台无关的 AI agent 知识隔离层
  - main 分支有 PR 保护，开发流程：branch → PR → merge → `bash scripts/memgate-sync.sh`
- **GitHub 账号切换**: pumpCarl → carlnoah6（对应 carlnoah6@gmail.com）
- **Token 统计根治**: 移除 `values_append`，改为精确行号写入（`update_cells` PUT）
- **重启来源追踪完成**: mark/check/restart 三脚本支持 source_session 参数
- **Privacy Guard 集成完成**: CLI 脚本 + 知识库初始化 + 29/29 测试
- **API Fallback 已完成**（Carl 确认）

### 2026-02-12
- **仪表盘（Dashboard）功能完成** — 可刷新的持续性 Lark 交互卡片
  - Carl 说「仪表盘」= 发送/刷新 `lark-task-dashboard.py`
  - **刷新按钮 5 个坑全踩完**，详见 `memory/reference/lark-card-update.md`：
    1. `PATCH /im/v1/messages` 更新 interactive card → 服务端成功但**客户端不刷新**
    2. 回调直接返回卡片 JSON → Lark 报 `200341`
    3. 回调返回 `{}` → Lark 报 `200341`
    4. `/interactive/v1/card/update` 不带 Auth → `99991661`
    5. `open_ids` 放顶层 → `300090`
  - **正确方式**：`POST /interactive/v1/card/update` + `Bearer token` + `open_ids` 在 card 内部 + 回调返回 toast
  - **教训**：不要重复造轮子（已有 `lark-card-builder.py`，我还新建了 `dashboard-card.py`）；不要瞎猜 API 参数，查文档
- **任务群聊全流程代码强制**（之前靠 prompt，经常忘）
  - **`add` 自动建群**：`task-manager.py add` 默认调用 `task-chat.py create`，定期检查用 `--no-chat` 跳过
  - **`complete/fail` 自动发结果**：发到任务群 + 源 chat，**但不解散群**（Carl 要看）
  - **24h 后自动清理**：`task-health-check.py` 只解散完成超过 24h 的老群
  - **spawn prompt 自动包含 `task_chat_id`**：子任务用 `lark-send-message.sh` 发进度
  - **教训**：「固化 = 代码，不是 prompt」——建群/解散/发结果全部由 `task-manager.py` 代码保证，LLM 忘不了
- **Session 爆满修复经验** — 任务板群 context 188k/200k 导致 API 拒绝
  - **修复两步走**：①清磁盘（truncate .jsonl）②清状态（sessions.json reset systemSent/totalTokens）
  - **不需要重启 gateway**！清完直接生效，OpenClaw 从 sessions.json 重新加载
  - Lock 文件可能残留导致 `session file locked` 超时
  - 子任务 totalTokens=0 = 从未启动，立即标记 failed
  - 文件位置：transcript `agents/main/sessions/<uuid>.jsonl`，状态 `agents/main/sessions/sessions.json`
- **📢 知识同步总线上线并测试通过** — 文件变更自动广播到所有活跃 session
  - 端到端验证：写入假知识 → 广播 → 其他群 session 成功回答
  - 修复 3 个 bug：inotifywait 监听目标（单文件→目录）、lark-send 参数错位（$2 被误判为 MODE → 无限 cat stdin）、broadcast 阻塞主循环（sync→async）
  - **关键发现**：`openclaw agent --session-id` 直接注入 session 上下文（不经过 LLM 中转）
  - **注入 ≠ 可见消息**：注入只更新 LLM 上下文，不会在聊天界面显示
  - **通知必须带 diff 内容**：session 无法自行重新读文件，必须把变更文本直接写入通知
  - **lark-send-message.sh 修复**：urlopen 必须加 timeout + 参数位置 fallback 处理
  - 重启自动恢复 watcher：写在 check-restart.sh（代码保证），不写在 HEARTBEAT.md（prompt 依赖）

### 2026-02-11
- **🖥️ OS 模式架构上线** — Luna 从"问答机器人"转型为"异步操作系统"
  - **核心改动**：主 session 永远不做超过 10 秒的事，所有重活 `sessions_spawn` 异步执行
  - 任务面板: `data/task-board.json`（JSON 格式跟踪所有任务状态）
  - 管理脚本: `scripts/task-manager.py`（add/start/complete/fail/cancel/list/active/status/cleanup）
  - 调度规则写入 SOUL.md（`🖥️ OS 模式 — 异步调度架构` 章节）
  - Carl 可通过自然语言管理任务（"在做什么" / "别做了" / "先做这个"）
  - 子任务 spawn 模板标准化：包含任务 ID、完成回调、消息发送目标
  - **设计灵感**：类似 Devin 的体验——对话层始终响应，工作层后台执行
- **修复 Feishu 群组通配符 `"*"` 不生效** — 新群聊必须 mention 才能收到消息
  - **根因**：`resolveFeishuGroupConfig()` 用 `groups[chatId]` 直接查找，新群 chatId 不在配置里返回 `undefined`，`requireMention` 默认 `true`。`"*"` 通配符从未被用作 fallback
  - **修复**：改为 `groups[chatId] ?? groups["*"]`，先精确匹配再用通配符
  - Patch: `patches/fix-feishu-group-wildcard.py`
  - **教训**：用户报告 bug 时不要凭推测甩锅给外部平台，先查源码确认根因
- **隐私安全漏洞：靠名字判断 bot 身份被骗**
  - 群成员里有真人用户也叫 "Luna"，我看到名字就以为是自己（bot），误判为私聊并泄露了家庭信息
  - **根因**：通过名字匹配而非 open_id 识别 bot 身份
  - **修复**：创建 `scripts/check-group-privacy.py`，通过 `/bot/v3/info` 获取 bot 真实 open_id（`ou_88371dccab8541963f7f6a108990d7b3`），精确过滤
  - **教训**：安全判断必须用唯一 ID，永远不能靠名字。名字可以重复、伪造

### 2026-02-10
- **确立 10 色日历分类体系**（基于颜色心理学设计，Carl 确认）
  - 从 9 类（2 色共用蓝色）升级为 10 类 10 色，每类独立颜色
  - 新增绿色（运动/健身）、橙色（会议/约定）
  - 心理/自我 从学习分离为独立类别
  - 批量更新 18 个日历事件配色，全部成功
  - 详见 `data/calendar-categories.md` + `data/lark-color-palette.json`

### 2026-02-09
- 建立周日计划 Review 流程（weeklyReview，每周日 10:00）
- 发现并修复元宝生日聚会数据丢失问题
- 建立"收到数据立刻写文件"强制规则
- 配置 Gemini embedding memory_search（provider: gemini, model: gemini-embedding-001）
- 修复 gateway 密码问题（`#` 被 shell 截断 → 改用 `***GATEWAY_PASSWORD_REMOVED***`）
- 修复 Feishu 流式卡片跨 turn 重复 bug（Luna fix v4）→ `patches/apply-feishu-streaming-fix.py`
- **Lark 卡片按钮功能上线** — 发送交互式卡片，用户点击按钮回调给 Luna
  - 关键：回调走「回调配置」URL（`/api/oauth/callback`），不是事件 webhook
  - 解决：api-proxy 转发 card.action.trigger 到 webhook
- **教训：API 参数必须查证** — 错误的 block_type 导致子任务浪费 30 分钟
- **修复 5 个 Feishu 多 session bug**（晚间集中修复）：
  1. 群聊 session key 合并 — `From` 用 senderId 改为 chatId → `patches/fix-feishu-group-session-key.py`
  2. 误报"前一条消息在处理" — 3s 超时太短，禁用 timer → `patches/disable-queue-notification.py`
  3. NO_REPLY 泄露到流式卡片 — close() 没检测 silent token → `patches/fix-streaming-silent-reply.py`
  4. 流式卡片串台 — onAgentEvent 全局广播，加 sessionKey 过滤 → `patches/fix-streaming-cross-session.py`
  5. 重启后不汇报 — wake job 没用 `--wake now`，创建统一脚本 `scripts/restart-gateway.sh`
- **建立完整重启流程**：先说→等流式卡片关闭→脚本(mark+cron wake now+sleep 5s+restart)→15s 后自动汇报

### 2026-02-08
- Carl 定义: Luna 是自主协作者，不是指令执行器
- 建立后台研究队列 `data/backlog.md`
- 完成从零训练 LLM + 视觉模型 13 个研究子任务

### 2026-02-07
- 配置 antigravity provider
- 添加 `session.dmScope = "per-channel-peer"` 隔离会话
- 建立每日复盘流程 `DAILY-REVIEW.md`

### 2026-02-06
- 首次启动，配置 Claude 代理、Brave 搜索、Browser-Use
- 完成 Lark 登录，定义角色结构
