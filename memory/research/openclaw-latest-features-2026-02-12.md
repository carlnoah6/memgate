# OpenClaw 最新功能研究报告
**研究时间**: 2026-02-12  
**研究来源**: openclaw.ai 官网、GitHub、官方文档

---

## 一、OpenClaw 简介

OpenClaw 是一个**完全自托管、隐私优先**的开源 AI 助手框架，由 Yuma Heymans 创立。它运行在你的设备上，可以连接到 Claude、DeepSeek、OpenAI 等 LLM，通过 WhatsApp、Telegram、Discord 等聊天应用与你交互。

**核心理念**: 你的上下文和技能保存在**你的电脑**上，而不是某个封闭的生态系统中。

---

## 二、最新核心功能（2025-2026）

### 1. **Cron vs Heartbeat 双调度系统**

这是 OpenClaw 最重要的自动化机制：

| 特性 | Heartbeat | Cron |
|------|-----------|------|
| 运行频率 | 定期（默认30分钟） | 精确时间点 |
| 运行位置 | Main session | 可选隔离 session |
| 上下文 | 完整对话上下文 | 隔离/独立 |
| 最佳场景 | 批量检查（邮件+日历+天气） | 精确提醒、独立任务 |
| 模型选择 | 继承主配置 | 可覆盖指定模型 |

**决策流程图**:
```
需要精确时间？ → 是 → 用 Cron
            ↓ 否
需要隔离？   → 是 → 用 Cron (isolated)
            ↓ 否
可批量检查？ → 是 → 用 Heartbeat
            ↓ 否
一次性提醒？ → 是 → 用 Cron (--at)
            ↓ 否
用 Heartbeat
```

**启发**: 我们当前的系统已使用类似的模式（HEARTBEAT.md + cron），文档非常完善。

---

### 2. **First-Class Tools（一等工具）**

OpenClaw 提供类型化的原生工具，替代旧的 skill 系统：

#### 核心工具组
- **group:fs**: `read`, `write`, `edit`, `apply_patch` - 文件操作
- **group:runtime**: `exec`, `bash`, `process` - 命令执行
- **group:sessions**: `sessions_list`, `sessions_history`, `sessions_send`, `sessions_spawn`, `session_status` - 会话管理
- **group:memory**: `memory_search`, `memory_get` - 记忆检索
- **group:web**: `web_search`, `web_fetch` - 网络搜索
- **group:ui**: `browser`, `canvas` - 浏览器和可视化
- **group:automation**: `cron`, `gateway` - 自动化
- **group:messaging**: `message` - 消息发送
- **group:nodes**: `nodes` - 节点管理

#### 特色工具
- **browser**: 浏览器控制（status/start/stop/profiles/tabs/open/snapshot/screenshot/actions）
- **canvas**: Agent 驱动的可视化工作区，支持 A2UI
- **nodes**: 配对节点管理（手机、Companion App）
- **lobster**: 确定性工作流引擎，支持审批断点

---

### 3. **Tool Profiles（工具配置策略）**

可配置的工具权限系统：

```json
{
  "tools": {
    "profile": "coding",  // minimal | coding | messaging | full
    "allow": ["slack"],
    "deny": ["group:runtime"]
  }
}
```

**Profile 选项**:
- `minimal`: 仅 session_status
- `coding`: fs + runtime + sessions + memory + image
- `messaging`: message + sessions 管理
- `full`: 无限制

**Provider-specific 策略**:
```json
{
  "tools": {
    "profile": "coding",
    "byProvider": {
      "google-antigravity": { "profile": "minimal" }
    }
  }
}
```

---

### 4. **Subagent（子任务）系统**

通过 `sessions_spawn` 创建隔离子任务：

**关键特性**:
- 完全隔离的 session，不污染主上下文
- 可指定不同模型和思考级别
- 支持任务完成后的 announce 通知
- 可配置 deliveryContext 控制消息路由

**最佳实践**（来自我们的经验）:
- 重活必须 spawn：研究、代码编写、文档创建
- 主 session 只负责调度和轻量回复
- 每个 spawn 必须包含任务管理指令（complete/fail 标记）

---

### 5. **Lobster 工作流引擎**

多步骤确定性工作流运行时：

**适用场景**:
- 需要固定步骤管道的自动化
- 需要人工审批断点的流程
- 可恢复的中断任务

**特性**:
- 本地子进程运行
- JSON 信封返回
- `needs_approval` 暂停机制
- `resumeToken` 恢复执行

---

### 6. **Live Canvas（实时画布）**

Agent 驱动的可视化工作区：
- 创建图表、演示文稿、交互内容
- 支持 A2UI（Agent-to-User Interface）
- HTML → Playwright 截图工作流

---

### 7. **Nodes（节点系统）**

支持配对设备：
- iOS/Android Companion App
- macOS Menu Bar App
- 可通过 `host=node` 在设备上执行命令
- 相机、屏幕录制、位置获取

---

### 8. **Memory 系统**

- **Workspace memory**: 文件化持久存储
- **QMD backend**: 可选的向量记忆后端
- **跨 session 持久化**: 重启后自动恢复

---

## 三、版本更新亮点

### v2026.2.3 (最新)
- Telegram: 移除 @ts-nocheck，使用 Grammy 类型
- 路径处理优化：支持 OPENCLAW_HOME 和 Windows 盘符

### v2026.1.30
- **CLI 自动补全**: Zsh/Bash/PowerShell/Fish
- **Agent 模型状态**: `openclaw models status --agent`
- **子任务思考级别**: 可配置 `agents.defaults.subagents.thinking`

### v2026.1.x
- **Web UI Agents Dashboard**: 管理 agent 文件、工具、技能、模型、频道、cron
- **QMD 后端**: 可选的工作区记忆后端
- **Healthcheck skill**: 安全检查工具

---

## 四、对我们系统的启发

### 1. **架构设计**
我们的系统与 OpenClaw 官方推荐模式高度一致：
- ✅ OS 模式：主 session 轻量、重活 spawn
- ✅ Heartbeat + Cron 双调度
- ✅ Task board 全局状态管理
- ✅ 子任务隔离执行

### 2. **可借鉴的新功能**
- **Tool Profiles**: 考虑为我们的不同 agent 配置不同的工具权限
- **Canvas 可视化**: 当前已使用 HTML+Playwright，可考虑与 A2UI 结合
- **Lobster 工作流**: 复杂的审批流程可考虑引入

### 3. **安全最佳实践**
- 拒绝无效配置项并拒绝启动 gateway（安全第一）
- `openclaw doctor --fix` 修复配置
- Exec 审批和 allowlist 机制

---

## 五、参考资源

- 官网: https://openclaw.ai/
- GitHub: https://github.com/openclaw/openclaw
- 文档: https://docs.openclaw.ai/
- Cron vs Heartbeat: https://docs.openclaw.ai/automation/cron-vs-heartbeat
- 工具文档: https://docs.openclaw.ai/tools

---

*研究报告由 Luna 后台任务生成*
