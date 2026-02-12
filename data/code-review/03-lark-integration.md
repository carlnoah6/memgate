# Code Review: Lark/飞书集成模块

**审查日期**: 2026-02-12  
**审查范围**: 23 个脚本，覆盖消息、日历、Wiki、卡片、OAuth  
**严重性标签**: 🔴 Critical | 🟡 Major | 🟢 Minor | 💡 Suggestion

---

## 一、总览

| 分类 | 文件数 | 总行数(approx) | 主要问题 |
|------|--------|----------------|----------|
| 消息发送 | 4 (lark-send-message.sh, send-confirm-card.sh, send-diagram.sh, md-to-lark-post.py) | ~400 | 凭据硬编码, 重复 token 获取 |
| 日历 | 4 (calendar-today, calendar-create, calendar-fix-colors, skip-recurring-dates) | ~500 | 混用 urllib/requests/curl |
| Wiki/文档 | 6 (md-to-lark-wiki, md-to-email-text, rewrite-lark-doc, rewrite-wiki-1b-token, sync-md-to-wiki, sync-tracked-docs) | ~900 | 两个 rewrite 高度重复 |
| 卡片/看板 | 3 (lark-card-builder, lark-task-card, lark-task-dashboard) | ~550 | 功能重叠 |
| 认证 | 2 (lark-token-refresh, oauth-callback) | ~150 | token 明文存储 |
| 工具/调试 | 4 (lark-lookup-chat, get-source-chat, debug-group-members, check-group-privacy) | ~300 | 凭据管理不一致 |

---

## 二、公共逻辑抽象分析

### 2.1 Token 获取：12+ 份重复实现 🔴

**当前状态**: 几乎每个脚本都有自己的 token 获取逻辑，存在两种 token 类型：

| Token 类型 | 用途 | 获取方式 | 使用文件数 |
|-----------|------|---------|-----------|
| `tenant_access_token` | Bot 级别操作(发消息、查群) | POST `/auth/v3/tenant_access_token/internal` | 8 |
| `user_access_token` | 用户级别操作(日历、Wiki) | 从 `lark-user-token.json` 读取 | 8 |

**重复代码示例** — 以下函数在不同文件中几乎一字不差出现 8 次：

```python
# 出现在: lark-task-card.py, lark-task-dashboard.py, get-source-chat.py,
#         check-group-privacy.py, lark-lookup-chat.py, lark-send-message.sh(内联Python),
#         send-confirm-card.sh(curl), send-diagram.sh(curl)
def get_tenant_token():
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["tenant_access_token"]
```

同样，`get_token()`（读用户 token 文件）出现 6 次：

```python
# 出现在: lark-calendar-today.py, lark-calendar-create.py, 
#         lark-calendar-fix-colors.py, skip-recurring-dates.py,
#         rewrite-wiki-1b-token.py, sync-tracked-docs.py
def get_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)["access_token"]
```

**建议**: 创建 `scripts/lark_common.py` 共享模块：

```python
# scripts/lark_common.py
"""Lark API 公共工具模块"""

import json, os, urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
TOKEN_FILE = WORKSPACE / "data" / "lark-user-token.json"
SECRETS_FILE = WORKSPACE / "data" / "lark-secrets.json"
BASE_URL = "https://open.larksuite.com/open-apis"

def _load_credentials():
    """从 secrets 文件加载凭据（不硬编码）"""
    if SECRETS_FILE.exists():
        with open(SECRETS_FILE) as f:
            creds = json.load(f)
        return creds["app_id"], creds["app_secret"]
    # 回退到环境变量
    app_id = os.environ.get("LARK_APP_ID")
    app_secret = os.environ.get("LARK_APP_SECRET")
    if app_id and app_secret:
        return app_id, app_secret
    raise RuntimeError("No Lark credentials found in secrets file or env vars")

def get_tenant_token() -> str:
    app_id, app_secret = _load_credentials()
    req = urllib.request.Request(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    token = data.get("tenant_access_token")
    if not token:
        raise RuntimeError(f"Failed to get tenant token: {data}")
    return token

def get_user_token() -> str:
    with open(TOKEN_FILE) as f:
        return json.load(f)["access_token"]

def lark_api(method, path, body=None, token=None, token_type="tenant",
             retries=3, timeout=15):
    """统一 API 调用封装，含重试和速率限制处理"""
    if token is None:
        token = get_tenant_token() if token_type == "tenant" else get_user_token()
    # ... retry logic, rate limit handling ...
```

### 2.2 API 调用方式混乱 🟡

**三种 HTTP 客户端混用**:

| 方式 | 使用文件 | 问题 |
|------|---------|------|
| `urllib.request` (stdlib) | 大多数 .py 文件 | 错误处理冗长 |
| `requests` 库 | skip-recurring-dates.py, rewrite-lark-doc.py, rewrite-wiki-1b-token.py | 额外依赖但更简洁 |
| `curl` via `subprocess` | lark-calendar-today.py, lark-calendar-create.py, lark-calendar-fix-colors.py, shell scripts | 解析复杂, 安全隐患 |

**特别问题**: `lark-calendar-today.py` 使用 `subprocess.run(["curl", ...])` 调用 API，但同文件又用 Python 处理 JSON。这完全没必要——既然已经是 Python 脚本，应该直接用 urllib/requests。

**建议**: 统一使用 `urllib.request`（零依赖）或统一使用 `requests`（更简洁）。不要混用。

### 2.3 BASE URL 硬编码 🟢

`https://open.larksuite.com/open-apis` 在 15+ 处硬编码。应提取为常量并集中管理。注意如果切换到飞书国内版（`open.feishu.cn`），需要修改所有文件。

---

## 三、错误处理健壮性

### 3.1 Token 过期无自动刷新 🔴

**问题**: 多个脚本读取 `lark-user-token.json` 中的 `access_token`，但 user token 有效期仅 2 小时。如果 token 过期：
- `lark-calendar-today.py`: API 返回错误，`sys.exit(1)` — 没有尝试刷新
- `md-to-lark-wiki.py`: 同样直接失败
- `rewrite-wiki-1b-token.py`: 有 5 次重试但不包含 token 刷新

**唯一的刷新机制**: `lark-token-refresh.py` 存在，但需要外部调用（cron 或心跳）。没有脚本内置"检测过期→自动刷新→重试"逻辑。

**建议**: 在 `lark_common.get_user_token()` 中加入过期检测：

```python
def get_user_token(auto_refresh=True):
    token_data = json.load(open(TOKEN_FILE))
    if auto_refresh:
        mtime = os.path.getmtime(TOKEN_FILE)
        expires_in = token_data.get("expires_in", 7200)
        if time.time() - mtime > expires_in - 300:  # 5分钟缓冲
            _refresh_user_token(token_data["refresh_token"])
            token_data = json.load(open(TOKEN_FILE))
    return token_data["access_token"]
```

### 3.2 网络错误处理不一致 🟡

| 文件 | 网络错误处理 |
|------|------------|
| `lark-send-message.sh` (内联 Python) | ✅ try/except, 区分 HTTPError |
| `lark-calendar-today.py` | ❌ curl 子进程失败只检查 JSON parse |
| `lark-calendar-fix-colors.py` | ❌ `get_events()` 的 `except: return []` 吞掉所有错误 |
| `oauth-callback.py` | ❌ `exchange_code` 无 try/except, 网络错误导致 500 |
| `rewrite-wiki-1b-token.py` | ✅ 5 次重试 + 速率限制处理 |
| `md-to-lark-wiki.py` | ✅ HTTPError 捕获但无重试 |
| `sync-tracked-docs.py` | ⚠️ 单个 `try/except` 但不重试 |

**最差案例 — `lark-calendar-fix-colors.py:get_events()`**:

```python
def get_events(days=30):
    # ...
    try:
        return json.loads(res.stdout).get("data", {}).get("items", [])
    except:
        return []  # 🔴 吞掉所有异常！调用者永远不知道失败了
```

**建议**: 所有 API 调用应该：
1. 捕获特定异常（不用裸 `except`）
2. 记录错误信息到 stderr
3. 关键操作应有重试（参考 `rewrite-wiki-1b-token.py` 的实现）

### 3.3 `oauth-callback.py` 安全性 🟡

- HTTP server 绑定 `127.0.0.1:8190`（本地 OK）
- 没有 CSRF 保护（`state` 参数验证）
- `exchange_code` 网络错误会导致未处理异常 → HTTP 500
- POST handler 忽略所有请求体内容

### 3.4 `lark-token-refresh.py` 基于 mtime 计算过期 🟢

```python
mtime = os.path.getmtime(TOKEN_FILE)
expires_in = token_data.get("expires_in", 7200)
expires_at = mtime + expires_in
```

这依赖文件修改时间，在某些情况下不可靠（如文件被 touch、复制等）。建议在 token 文件中保存 `"saved_at": timestamp`。

---

## 四、rewrite-lark-doc.py vs rewrite-wiki-1b-token.py 🔴 高度重复

### 4.1 对比分析

| 特性 | rewrite-lark-doc.py | rewrite-wiki-1b-token.py |
|------|-------------------|------------------------|
| 目标文档 | `GtIudQ8sPoCtBVxc47olz1dPgMb` | 同一个 |
| 源文件 | 同一个 `.md` 文件 | 同一个 |
| HTTP 库 | `requests` | `requests` |
| 重试逻辑 | ❌ 无 | ✅ 5 次重试 + 429 处理 |
| 表格支持 | ❌ 转为段落/列表（降级） | ✅ 真正的 Lark Table (block_type 31) |
| 删除旧内容 | 逐个删除（慢） | 批量删除（快） |
| 代码块处理 | 转为 quote blocks | 跳过（不显示） |
| `parse_inline` | 支持 bold, italic, code, strikethrough | 只支持 bold |
| 行数 | ~250 | ~300 |
| 可通用化 | ❌ 硬编码 DOC_ID + 源文件 | ❌ 同样硬编码 |

### 4.2 重复代码

两个文件共享以下几乎相同的函数：
- `parse_inline` / `parse_text_with_bold` — 不同名但功能重叠
- `make_heading` / `make_heading_block`
- `make_paragraph` / `make_text_block`  
- `make_bullet` / `make_bullet_block`
- `make_divider` / `make_divider_block`
- `write_blocks` — 批量写入逻辑

### 4.3 建议

**保留 `rewrite-wiki-1b-token.py`**（功能更完整），**废弃 `rewrite-lark-doc.py`**。

更进一步，将两者的通用逻辑提取到 `md-to-lark-wiki.py`（已有的转换器），使其成为唯一的 "MD → Lark DocX" 工具。`rewrite-wiki-1b-token.py` 可以简化为：

```python
# 只需调用已有工具
subprocess.run([
    "python3", "md-to-lark-wiki.py", DOC_ID,
    "--file", SOURCE_FILE
])
```

但目前 `md-to-lark-wiki.py` 不支持 table blocks（block_type 31），需要移植 `rewrite-wiki-1b-token.py` 的 `create_table` 逻辑过去。

---

## 五、Sync 系列脚本统一可能性

### 5.1 现有脚本职责

| 脚本 | 方向 | 职责 |
|------|------|------|
| `sync-md-to-wiki.py` | 本地 MD → Wiki | 检测 MD 变更，推送到 Wiki 文档 |
| `sync-tracked-docs.py` | Wiki → 本地 JSON | 扫描 Wiki 空间，发现新文档加入监控列表 |
| `md-to-lark-wiki.py` | 本地 MD → Wiki | 核心转换+上传引擎 |
| `rewrite-lark-doc.py` | 本地 MD → 特定文档 | 专用于一个文档 |
| `rewrite-wiki-1b-token.py` | 本地 MD → 特定文档 | 专用于同一个文档（带 table） |

### 5.2 统一建议

**层次化重构**:

```
Layer 1: lark_common.py          — Token + API 调用基础设施
Layer 2: lark_docx.py            — MD → DocX blocks 转换（合并 md-to-lark-wiki + rewrite 的解析逻辑）
Layer 3: sync-md-to-wiki.py      — 编排层：hash 检测 + 调用 Layer 2
         sync-tracked-docs.py    — 编排层：Wiki 空间扫描（保持独立，职责不同）
```

**具体操作**:
1. `md-to-lark-wiki.py` 增加 table 支持（从 `rewrite-wiki-1b-token.py` 移植）
2. `rewrite-lark-doc.py` 废弃 → 用 `md-to-lark-wiki.py <doc_id> --file <path>` 替代
3. `rewrite-wiki-1b-token.py` 简化为调用 `md-to-lark-wiki.py` 的 thin wrapper（或直接废弃）
4. `sync-md-to-wiki.py` 保持为编排脚本
5. `sync-tracked-docs.py` 保持独立（职责不同：读 Wiki → 写本地 JSON）

### 5.3 `md-to-lark-post.py` vs `md-to-lark-wiki.py` vs `md-to-email-text.py` 💡

三个 MD 转换器各自独立实现了 `parse_inline`，但目标格式不同：
- `md-to-lark-post.py` → Lark Post JSON（消息富文本）
- `md-to-lark-wiki.py` → Lark DocX blocks（文档块）
- `md-to-email-text.py` → 纯文本

由于目标格式完全不同，共享代码的收益有限。**保持独立是合理的**，但建议各自在文件头注明与其他转换器的区别。

---

## 六、安全性分析

### 6.1 🔴 凭据硬编码在 12+ 个文件中

**这是最严重的安全问题。** `APP_ID` 和 `APP_SECRET` 以明文形式出现在以下文件中：

```
scripts/lark-send-message.sh        (export 到环境变量)
scripts/lark-token-refresh.py       (Python 常量)
scripts/oauth-callback.py           (Python 常量)
scripts/lark-task-card.py           (Python 常量)
scripts/lark-task-dashboard.py      (Python 常量)
scripts/lark-lookup-chat.py         (Python 常量)
scripts/send-confirm-card.sh        (curl -d 中)
scripts/send-diagram.sh             (curl -d 中)
scripts/get-source-chat.py          (Python 常量)
scripts/check-group-privacy.py      (Python 常量)
scripts/skip-recurring-dates.py     (不含，但用 user token)
```

**唯一例外**: `debug-group-members.py` 尝试从 `data/lark-secrets.json` 或环境变量读取，是正确做法。但这个模式没有推广到其他文件。

**风险**:
- 如果代码仓库公开（或泄露），APP_SECRET 立即暴露
- 任何能读取工作目录的进程都能获取凭据
- `lark-send-message.sh` 通过 `export` 暴露到子进程环境变量，可能被其他工具记录

**修复方案**:

```bash
# 1. 创建统一 secrets 文件
cat > data/lark-secrets.json << 'EOF'
{
  "app_id": "cli_a90c3a6163785ed2",
  "app_secret": "***LARK_SECRET_REMOVED***"
}
EOF
chmod 600 data/lark-secrets.json

# 2. 加入 .gitignore
echo "data/lark-secrets.json" >> .gitignore
echo "data/lark-user-token.json" >> .gitignore

# 3. 所有脚本改为通过 lark_common.py 获取凭据
```

### 6.2 🟡 User Token 明文存储

`data/lark-user-token.json` 包含 `access_token` 和 `refresh_token`，明文存储无文件权限限制。

**建议**:
- `chmod 600 data/lark-user-token.json`
- 在 `lark-token-refresh.py` 的 `save_token()` 中设置文件权限：
  ```python
  os.chmod(TOKEN_FILE, 0o600)
  ```

### 6.3 🟡 Shell 脚本中的命令注入风险

`send-confirm-card.sh` 将用户输入直接拼接到 Python 命令中：

```bash
CARD_JSON=$(python3 -c "..." "$TITLE" "$CONTENT" "$BUTTONS")
```

虽然 `$TITLE` 和 `$CONTENT` 通过 `sys.argv` 传递（相对安全），但 `$BUTTONS` 是经过 `split(':')` 处理的用户输入。如果按钮 label 或 value 包含特殊字符，可能导致 JSON 注入。

`send-diagram.sh` 的 curl 命令中直接嵌入 `$CHAT_ID` 和 `$IMAGE_KEY`：
```bash
-d "{\"receive_id\": \"$CHAT_ID\", ...}"
```
如果 `$CHAT_ID` 包含 `"` 或 `\`，JSON 会被破坏。建议用 Python/jq 构建 JSON。

### 6.4 🟢 OAuth State 参数缺失

`oauth-callback.py` 不验证 OAuth `state` 参数，存在 CSRF 风险。由于只监听 `127.0.0.1`，实际风险较低，但仍建议加上。

### 6.5 🟡 CARL_OPEN_ID 硬编码

`check-group-privacy.py` 硬编码了 Carl 的 `open_id`：
```python
CARL_OPEN_ID = "ou_35f664e694dd100adf97b867e68e1d3a"
```
应该移到配置文件中。

---

## 七、lark-task-card.py vs lark-task-dashboard.py 功能重叠 🟡

两个脚本功能高度重叠：

| 特性 | lark-task-card.py | lark-task-dashboard.py |
|------|------------------|----------------------|
| 发送新卡片 | ✅ `send` | ✅ `send_new_card` |
| 更新卡片 | ✅ `update` | ✅ `update_card` |
| 自动模式 | ✅ `auto` | ✅ (默认行为) |
| 卡片内容 | 任务看板 | 任务面板 + Session 概览 |
| 状态缓存 | `task-card-state.json` | `dashboard-state.json` |
| 卡片构建 | 内联 `build_card()` | 调用 `lark-card-builder.py` |
| 目标群聊 | 参数传入 | 硬编码 `CHAT_ID` |

**建议**: 合并为一个脚本，通过参数选择内容模式（简版 board vs 完整 dashboard）。

---

## 八、其他发现

### 8.1 `lark-calendar-today.py` 的 RRULE 解析 🟢

自行实现了 RRULE 解析器（约 100 行），支持 WEEKLY/DAILY/MONTHLY/YEARLY。这是一个潜在的 bug 源，因为 iCalendar RRULE 规范非常复杂（EXDATE、COUNT、WKST 等都未处理）。

**建议**: 考虑使用 `python-dateutil` 的 `rrule` 模块（如果可以添加依赖），或在文件头明确标注已知限制。

### 8.2 `lark-card-builder.py` 调用外部脚本 🟢

`build_card()` 在每次构建卡片时通过 `subprocess.run` 调用 `session-overview.py`，增加了延迟。可以考虑在心跳中预刷新数据，构建卡片时只读 JSON。

### 8.3 `skip-recurring-dates.py` 是唯一使用 `requests` 的日历脚本 🟢

其他日历脚本用 `curl` 或 `urllib`，此脚本用 `requests`。应统一。

### 8.4 `md-to-lark-post.py` 将 `\`code\`` 渲染为 bold 🟢

```python
elif m.group(2):  # `code`
    elements.append({"tag": "text", "text": m.group(2), "style": ["bold"]})
```

Lark Post 格式不支持 inline code 样式，当前用 bold 替代。这是可接受的降级，但应在注释中说明。

---

## 九、重构优先级建议

### P0 — 立即修复 🔴

1. **凭据集中化**: 创建 `data/lark-secrets.json`，所有脚本通过 `lark_common.py` 读取
2. **Token 文件权限**: `chmod 600` 所有敏感文件
3. **废弃 `rewrite-lark-doc.py`**: 功能完全被 `rewrite-wiki-1b-token.py` 覆盖

### P1 — 短期改进 🟡

4. **创建 `lark_common.py`**: Token 获取、API 调用、重试逻辑
5. **统一 HTTP 客户端**: 全部使用 `urllib.request`（或全部 `requests`）
6. **user token 自动刷新**: 在读取 token 时检测过期并自动调用 refresh
7. **合并 `lark-task-card.py` 和 `lark-task-dashboard.py`**

### P2 — 中期优化 💡

8. **`md-to-lark-wiki.py` 增加 table 支持**: 移植 `rewrite-wiki-1b-token.py` 的 table 逻辑
9. **日历脚本去掉 curl 调用**: 改为纯 Python urllib
10. **Shell 脚本改写为 Python**: `send-confirm-card.sh`, `send-diagram.sh` 转为 Python 以避免 JSON 注入风险
11. **`lark-calendar-today.py` RRULE 限制文档化**: 明确标注不支持 EXDATE、COUNT 等

---

## 十、依赖关系图

```
lark_common.py (建议新建)
  ├── get_tenant_token()
  ├── get_user_token()
  └── lark_api()

消息链路:
  lark-send-message.sh ── md-to-lark-post.py
  send-confirm-card.sh
  send-diagram.sh ── get-source-chat.py

日历链路:
  lark-calendar-today.py
  lark-calendar-create.py
  lark-calendar-fix-colors.py
  skip-recurring-dates.py

Wiki 链路:
  sync-md-to-wiki.py ── md-to-lark-wiki.py
  sync-tracked-docs.py
  rewrite-lark-doc.py ⚠️ 废弃
  rewrite-wiki-1b-token.py

卡片链路:
  lark-task-dashboard.py ── lark-card-builder.py ── session-overview.py
  lark-task-card.py ── task_engine.py

认证链路:
  oauth-callback.py → data/lark-user-token.json
  lark-token-refresh.py → data/lark-user-token.json

工具链路:
  lark-lookup-chat.py
  debug-group-members.py
  check-group-privacy.py
```

---

## 十一、总结

| 维度 | 评分 | 说明 |
|------|------|------|
| 功能完整性 | ⭐⭐⭐⭐⭐ | 覆盖消息、日历、Wiki、卡片、OAuth 全链路 |
| 代码复用 | ⭐⭐ | 大量重复的 token/API 代码 |
| 错误处理 | ⭐⭐⭐ | 部分脚本有重试，部分吞异常 |
| 安全性 | ⭐⭐ | 凭据硬编码是最大隐患 |
| 可维护性 | ⭐⭐⭐ | 每个脚本独立可理解，但整体不一致 |
| 一致性 | ⭐⭐ | 3 种 HTTP 客户端、2 种 token 获取、混合语言 |

**核心改进方向**: 提取 `lark_common.py` + 凭据集中管理 → 可以消除 60%+ 的重复代码和最大的安全隐患。这是 ROI 最高的单一重构。
