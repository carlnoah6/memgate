# OpenClaw 社区 Skills 调研报告

**调研日期：** 2026-02-08  
**调研目的：** 评估 OpenClaw 社区可用 skills，对比 Luna 现有安装，识别有价值的新增候选

---

## 1. 生态概况

截至 2026 年 2 月 7 日，OpenClaw 的公共 skill 注册表 ClawHub 上共有 **5,705** 个社区构建的 skill。经过 VoltAgent 团队筛选（去除垃圾/重复/恶意/非英文），整理出 **2,999** 个有效 skill，覆盖 30+ 个类别。

OpenClaw 官方仓库自带 **53 个 bundled skills**，涵盖笔记、生产力、开发工具、音乐、智能家居、创意工具、语音、安全、AI 集成等多个领域。

**⚠️ 安全注意：** 社区中发现了 396 个被安全研究者标记为恶意的 skill（不含 VirusTotal 扫描的），还有 672 个加密/金融类 skill 被过滤。安装第三方 skill 前务必检查 VirusTotal 报告和源代码。

---

## 2. Luna 当前已安装 Skills

| Skill | 功能 |
|-------|------|
| github | GitHub CLI 交互（issue、PR、CI） |
| healthcheck | 安全审计和系统健康检查 |
| himalaya | IMAP/SMTP 邮件管理 |
| skill-creator | 创建自定义 skill 的指南 |
| tmux | 终端会话管理 |
| video-frames | 视频帧/片段提取 |
| weather | 天气查询（无需 API key） |
| browser-use | 浏览器自动化（managed skill） |

---

## 3. 推荐新增 Skills（按优先级排序）

### 🔴 高优先级推荐

#### 3.1 `summarize` — 内容摘要
- **功能：** 对 URL、PDF、YouTube 视频、音频文件生成结构化摘要；支持转录 YouTube 视频字幕
- **互补性：** ⭐⭐⭐⭐⭐ Luna 目前缺少快速摘要能力，Carl 经常需要消化长文档/视频，这是每日高频需求
- **安装难度：** 低，bundled skill，需要安装 `summarize` CLI（`brew install steipete/tap/summarize` 或 npm）
- **推荐等级：** 🔴 **高** — 社区排名 Top 5，241 次安装，几乎所有 power user 必装

#### 3.2 `gog` — Google Workspace 全家桶
- **功能：** 整合 Gmail、Google Calendar、Drive、Contacts、Sheets、Docs 的完整 CLI
- **互补性：** ⭐⭐⭐⭐⭐ 如果 Carl 使用 Google 生态，这是最高价值 skill。目前 himalaya 只能收发邮件，gog 涵盖日历、文件、表格等全套能力
- **安装难度：** 中，需要 Google OAuth 配置（约 15 分钟），通过 `brew install steipete/tap/gogcli` 安装
- **推荐等级：** 🔴 **高** — ClawHub 安装量第一（590 次），如果 Carl 用 Google 则必装
- **注意：** 与 himalaya 功能部分重叠（邮件部分），但 gog 更全面

#### 3.3 `clawhub` — Skill 包管理器
- **功能：** 从 clawhub.com 搜索、安装、更新、同步 skill 的 CLI 工具
- **互补性：** ⭐⭐⭐⭐ 让 Luna 自己能动态发现和安装新 skill，是 skill 管理的元工具
- **安装难度：** 低，`npm install -g clawhub` 即可
- **推荐等级：** 🔴 **高** — 基础设施级 skill，236 次安装

#### 3.4 `coding-agent` — AI 编码代理调度
- **功能：** 后台运行 Codex CLI、Claude Code、OpenCode 或 Pi Coding Agent，实现异步编码任务
- **互补性：** ⭐⭐⭐⭐ Carl 是开发者，可以通过消息给 Luna 下达编码任务，Luna 在后台用 AI 编码工具完成
- **安装难度：** 中，需要对应编码工具已安装（Claude Code 或 Codex 等）
- **推荐等级：** 🔴 **高** — 262 次安装，是"AI 指挥 AI"的核心能力

#### 3.5 `session-logs` — 会话日志搜索
- **功能：** 使用 jq 搜索和分析历史会话日志，回溯之前的对话内容
- **互补性：** ⭐⭐⭐⭐ Luna 目前的记忆依赖 MEMORY.md 和日记文件，session-logs 可以搜索原始对话记录，大幅增强上下文回忆能力
- **安装难度：** 低，bundled skill，依赖 jq（通常已安装）
- **推荐等级：** 🔴 **高** — 184 次安装，是 power user 的记忆增强工具

### 🟡 中优先级推荐

#### 3.6 `gemini` — Gemini 大模型集成
- **功能：** 调用 Gemini CLI 进行代码审查、计划审查或大上下文（>200k token）处理
- **互补性：** ⭐⭐⭐⭐ 当 Luna 主模型（Claude）遇到超长上下文任务时，可以调 Gemini 3 Pro 作为补充
- **安装难度：** 低，`brew install gemini-cli` 或 npm 安装，需要 Gemini API key
- **推荐等级：** 🟡 **中** — 202 次安装，适合需要跨模型协作的场景

#### 3.7 `nano-banana-pro` — Gemini 图像生成/编辑
- **功能：** 使用 Gemini 3 Pro Image 生成和编辑图片，支持文字生图和图片编辑
- **互补性：** ⭐⭐⭐ Luna 目前没有图像生成能力，这是创意工作的有力补充
- **安装难度：** 低，需要 Gemini API key（配置中已有条目但 key 是 test）
- **推荐等级：** 🟡 **中** — 216 次安装，需要有效的 Gemini API key

#### 3.8 `notion` — Notion 集成
- **功能：** 通过 API 创建和管理 Notion 页面、数据库和块
- **互补性：** ⭐⭐⭐ 如果 Carl 使用 Notion，可以让 Luna 直接操作任务板和笔记
- **安装难度：** 中，需要 Notion API token 配置
- **推荐等级：** 🟡 **中** — 207 次安装，取决于 Carl 是否使用 Notion

#### 3.9 `blogwatcher` — RSS/博客监控
- **功能：** 监控博客和 RSS/Atom feeds 的更新
- **互补性：** ⭐⭐⭐ 可以配合 cron 实现信息聚合，为 Carl 提供行业动态摘要
- **安装难度：** 低，CLI 安装
- **推荐等级：** 🟡 **中** — 164 次安装，适合信息追踪场景

#### 3.10 `mcporter` — MCP 服务器集成
- **功能：** 配置、认证和调用 MCP (Model Context Protocol) 服务器/工具
- **互补性：** ⭐⭐⭐ MCP 是 AI 工具生态的热门标准，安装后可以扩展连接各种外部服务
- **安装难度：** 中，需要理解 MCP 协议
- **推荐等级：** 🟡 **中** — 223 次安装，是通向更广阔工具生态的桥梁

#### 3.11 `nano-pdf` — PDF 编辑
- **功能：** 用自然语言指令编辑 PDF 文件
- **互补性：** ⭐⭐⭐ 处理文档的常见需求
- **安装难度：** 低，CLI 安装
- **推荐等级：** 🟡 **中** — 211 次安装

#### 3.12 `model-usage` — 模型用量追踪
- **功能：** 总结每个模型的使用量和成本数据
- **互补性：** ⭐⭐⭐ 帮助 Carl 了解 API 费用分布
- **安装难度：** 低
- **推荐等级：** 🟡 **中** — 170 次安装

#### 3.13 `review-pr` / `prepare-pr` / `merge-pr` — PR 工作流三件套
- **功能：** 结构化的 PR 审查 → 准备 → 合并流程
- **互补性：** ⭐⭐⭐ 和 github skill 互补，提供更精细的 PR 工作流
- **安装难度：** 低，bundled skill
- **推荐等级：** 🟡 **中** — 较新的 skill，安装量 38-44

### 🟢 低优先级 / 按需安装

#### 3.14 `obsidian` — Obsidian 笔记
- **功能：** 操作 Obsidian vault（Markdown 笔记）
- **互补性：** ⭐⭐ 仅在 Carl 使用 Obsidian 且 vault 可被 Luna 访问时有价值
- **推荐等级：** 🟢 **低** — 取决于个人工具链

#### 3.15 `bird` — X/Twitter CLI
- **功能：** 读推文、搜索、管理书签、获取趋势
- **互补性：** ⭐⭐ 社交媒体监控，需要 cookie 认证
- **推荐等级：** 🟢 **低** — 安全风险较高（Very High）

#### 3.16 `sag` — ElevenLabs TTS
- **功能：** 高质量文本转语音
- **互补性：** ⭐⭐ 语音输出，适合讲故事场景
- **推荐等级：** 🟢 **低** — 需要 ElevenLabs API key

#### 3.17 `openai-whisper` — 本地语音转文字
- **功能：** 本地运行 Whisper 模型进行语音转文字（无需 API key）
- **互补性：** ⭐⭐ 音频转录需求
- **推荐等级：** 🟢 **低** — 适合有音频处理需求时安装

#### 3.18 `spotify-player` — Spotify 控制
- **功能：** 终端 Spotify 播放/搜索
- **互补性：** ⭐ 纯便利性
- **推荐等级：** 🟢 **低**

---

## 4. 社区第三方亮点 Skills（ClawHub/awesome-openclaw-skills）

从 2,999 个 awesome list skills 中筛选的有趣项目：

| 类别 | Skill | 功能 | 注意事项 |
|------|-------|------|----------|
| 编码 | `coding-agent` | 调度多种 AI 编码助手 | 已列入高推荐 |
| 研究 | `cellcog` | DeepResearch Bench 2026年2月排名第一 | 新兴项目，待观察 |
| 可视化 | `ec-excalidraw` | 生成手绘风格图表和架构图 | 适合技术文档 |
| 编排 | `ec-task-orchestrator` | 自主多代理任务编排 | 复杂场景使用 |
| DevOps | `docker-sandbox` | Docker 沙箱环境管理 | 安全执行需求 |
| 编码 | `perry-workspaces` | Docker 隔离工作空间管理 | 适合多项目场景 |
| 安全 | `skill-vetting` | 安装前审查 skill 安全性 | 基础设施级 skill |
| 记忆 | `cognitive-memory` | 类人多存储记忆系统 | 增强长期记忆 |

⚠️ **第三方 skill 安全提醒：** 社区 skill 未经官方审核，建议安装前：
1. 在 ClawHub 查看 VirusTotal 报告
2. 审查源代码（可用 Claude Code 辅助检查）
3. 优先选择 awesome-openclaw-skills 列表中的 skill

---

## 5. 实施建议

### 第一批（建议立即安装）
1. **`summarize`** — 日常最高频需求
2. **`clawhub`** — skill 管理基础设施
3. **`session-logs`** — 增强 Luna 记忆能力

### 第二批（按需安装）
4. **`gog`** — 如果 Carl 使用 Google 生态
5. **`coding-agent`** — 如果需要后台编码能力
6. **`gemini`** — 跨模型协作场景

### 安装方式
```bash
# 方式 1：通过 ClawHub CLI
npx clawhub@latest install <skill-slug>

# 方式 2：手动复制到 skills 目录
# 全局：~/.openclaw/skills/<skill-name>/
# 工作区：<workspace>/skills/<skill-name>/
```

### 配置建议
考虑使用 `skills.allowBundled` 白名单模式控制哪些 bundled skill 被加载，避免不需要的 skill 污染上下文：
```json
{
  "skills": {
    "allowBundled": [
      "github", "healthcheck", "himalaya", "skill-creator",
      "tmux", "video-frames", "weather",
      "summarize", "clawhub", "session-logs"
    ]
  }
}
```

---

## 6. 总结

OpenClaw 的 skill 生态已经相当成熟（5,700+ skills），但也伴随着安全风险（396 个已知恶意 skill）。Luna 当前安装的 8 个 skill 覆盖了基本功能，但在以下方面有明显缺口：

- **内容摘要**：缺少 `summarize`（每日必用级别）
- **Skill 管理**：缺少 `clawhub`（自举能力）
- **历史搜索**：缺少 `session-logs`（记忆增强）
- **办公集成**：如果用 Google 生态，缺少 `gog`

建议优先补齐第一批 3 个 skill，再根据 Carl 的实际需求评估后续安装。
