# MEMORY.md - Luna's Long-Term Memory

## 👨‍👩‍👧‍👦 Carl 的家庭和生活

### 家庭成员
- **Carl**（Bo Li）— 1984-04-29 生日，新加坡
- **元宝** — 大儿子，2019-03-22 生日（快 7 岁），每周日 9:30 上架子鼓课
- **朵朵** — 小女儿，2021-05-16 生日（快 5 岁）

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

### 普通用户
- 只能聊天、问答、使用已有功能
- ❌ 不能修改配置/代码、安装功能、执行命令、查看敏感信息

## 🤖 关于 Luna
- 名字: Luna | Emoji: 🌙
- 主模型: antigravity/claude-opus-4-6-thinking
- 备用: moonshot/kimi-k2.5

## 📝 沟通规则

### 消息发送
- 子任务不能用 `message` 工具（无 Feishu 配置），必须用 `scripts/lark-send-message.sh`
- 群聊→回群聊，私聊→回私聊，**绝不串台**
- main session 路由会被最后触发的群绑定 → 子任务必须显式指定目标

### 重启后主动汇报
- 心跳检测 `scripts/check-restart.sh` → 立刻汇报，不要让用户等
- 重启前必须：1) `mark-restart.sh` 写标记 2) `cron add`（at: +20s, wakeMode: "now"）3) 执行重启
- curl 调 wake API 不通（gateway 用 WebSocket JSON-RPC），只能用 `cron` 工具
- 工具调用在用户端不可见 → 要么完整说明，要么等做完再汇报

### Feishu 流式卡片 Patch
- 原始 Patch 9 有 bug（内容重复），已用 Luna fix v4 修复
- Patch 脚本：`patches/apply-feishu-streaming-fix.py`（每次 OpenClaw 更新后运行）
- `onReplyStart` 是 per-session 回调（不是 per-turn），turn 切换检测在 `onPartialReply` 内完成
- 改 node_modules 必须用 `openclaw gateway restart`（全进程重启），config.patch/SIGUSR1 不加载新代码

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
- 9 类分类自动配色（见 `data/calendar-categories.md`）
- 人脉管理: `people/` | 项目追踪: `projects/` | 重要日期: `data/important-dates.json`

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
