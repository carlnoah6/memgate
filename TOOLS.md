# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

## 仪表盘（Dashboard）

Carl 说「仪表盘」= **可刷新的持续性 Lark 交互卡片**，显示：
- 所有任务状态（进行中 / 完成 / 失败）
- 所有 session 及 context 使用率
- 带「🔄 刷新」按钮，点击后原地更新卡片内容（不发新消息）

**技术实现：**
- 发送/更新：`python3 scripts/lark-task-dashboard.py`（自动判断 send/update）
- 卡片构建：`scripts/lark-card-builder.py`（读 task-board.json + session-overview.json）
- 更新：收到 `[按钮] refresh_dashboard` 回调 → 运行 `lark-task-dashboard.py` 原地更新
- 状态保存：`data/dashboard-state.json`（message_id + hash 防重复更新）

**刷新按钮工作原理：**
- 回调链路：Lark → Tailscale Funnel `/api/oauth/callback` → webhook-gateway:8280 `/webhook/lark`
- webhook-gateway 直接处理 `refresh_dashboard`（不转发给 OpenClaw）
- 用 `/interactive/v1/card/update` API 更新卡片（不是 PATCH 消息 API）
- 技术细节：`memory/reference/lark-card-update.md`

**Carl 说「仪表盘」时的操作：**
```bash
# 发新卡片（清旧 state）
echo '{}' > data/dashboard-state.json
python3 scripts/lark-task-dashboard.py

# 刷新现有卡片
python3 scripts/lark-task-dashboard.py
```

## 📸 HTML → 图片渲染（Playwright）

需要可视化内容（架构图、流程图、数据图表等）时，用 HTML 设计 + Playwright 截图：

**流程：**
1. 写 HTML 文件（带 CSS 样式）→ `data/<name>.html`
2. Playwright 截图 → `data/<name>.png`
3. 用 `message` 工具发送图片到聊天

**命令：**
```bash
# 截图（已安装 Chromium，无需额外安装）
npx playwright screenshot --browser chromium --full-page \
  --viewport-size "920,1400" \
  file:///home/ubuntu/.openclaw/workspace/data/<name>.html \
  /home/ubuntu/.openclaw/workspace/data/<name>.png
```

**发送：**
```
message(action=send, channel=feishu, target=<chat_id>,
        filePath=<png路径>, message="标题")
```

**设计要点：**
- 深色背景（`#0d1117`）在聊天界面更好看
- 宽度建议 900-920px，高度按内容自适应
- 用 `--full-page` 自动捕获完整页面

**已有模板：**
- `data/luna-architecture.html` — 系统架构全景图（五层架构）

---

Add whatever helps you do your job. This is your cheat sheet.
