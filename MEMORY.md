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

### 批量行动，减少中断
- 攒一批改动一起做，不要改一个就重启一次

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
- **循环事件跳过工具**: `python3 scripts/skip-recurring-dates.py <event_id_0> <skip_start> <skip_end>`
  - Lark 不支持删除虚拟循环实例（测试验证），UNTIL+重建是唯一方案
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

### 2026-02-11
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
