# Code Review #05 — 日报与统计引擎

> 审查时间: 2026-02-12 09:12 SGT
> 审查文件: daily-report-engine.py (1126L), token-hourly-stats.py (495L), deliver-daily-report.sh (140L), log-quota.sh (41L)
> 总计: 1802 行

---

## 总体评估

**架构**: daily-report-engine.py 的四阶段流水线设计（采集→分析→组装→交付）是清晰合理的，类的职责划分基本到位。但 1126 行单文件过大，应拆分。

**最大风险**: 密钥硬编码（20+ 个文件重复同一组 APP_ID/APP_SECRET），一旦任一文件泄露即全面暴露。

**死代码**: log-quota.sh 写入的 `quota-snapshots.jsonl` 没有任何消费者，属于残留代码。

---

## 1. daily-report-engine.py — 逐项审查

### 1.1 安全问题

• **[🔴高] 密钥硬编码** (L29-30)
  ```python
  API_KEY = "REDACTED_LUNA_KEY"
  ADMIN_KEY = "sk-admin-luna2026"
  ```
  这是全系统性问题——同一组 APP_ID/APP_SECRET 在 20+ 个脚本中重复硬编码。应提取到单一配置文件（如 `data/secrets.json` 或环境变量），所有脚本统一读取。

• **[🟡中] LLM 调用无输入消毒** (L75-97)
  `call_llm()` 将文件内容直接拼入 prompt。如果被审查的代码文件包含 prompt injection 内容（如 `"""Ignore previous instructions..."""`），理论上可污染 LLM 输出。风险较低（内部系统），但 Code Review 场景下值得注意。

### 1.2 逻辑缺陷

• **[🟡中] LLM_MODEL_HEAVY 定义但未使用** (L31)
  ```python
  LLM_MODEL_HEAVY = "claude-opus-4-6-thinking"  # Code Review 用重模型
  ```
  注释说 Code Review 用重模型，但 `_review_files()` 和所有 LLM 调用都用默认的 `LLM_MODEL`（flash）。要么删掉，要么实际使用。

• **[🟡中] CODE_EXTS 不包含 .md 但 _section_code_review 检查 .md** (L411-416)
  ```python
  doc_files = [p for p in all_files if os.path.splitext(p)[1] in {".md"}]
  ```
  `CODE_EXTS` = `{".py", ".sh", ".js", ".ts", ".json", ...}`，不含 `.md`。所以 `modified_files` 永远不会包含 `.md` 文件，`doc_files` 永远为空。这个统计是死代码。

• **[🟡中] validate_and_fix 章节检测脆弱** (L557-561)
  ```python
  required_sections = ["每日复盘", "Code Review", "时间分配", ...]
  for section in required_sections:
      if section not in self.report:
  ```
  用中文子串匹配检测章节存在性。如果 LLM 在反思中提到"Code Review"，会误判为该章节已存在。应检查章节标题格式（如 `## 2. 🔍 每日 Code Review`）。

• **[🟢低] _skipped_files 跨类传递** (L234, L432)
  `LLMAnalyzer._review_files()` 动态设置 `self._skipped_files`，然后 `ReportAssembler` 通过 `getattr(self.analysis, '_skipped_files', [])` 读取。这破坏了封装，应作为 `LLMAnalyzer` 的公开属性。

### 1.3 性能问题

• **[🟡中] 7 天 Token 用量串行 HTTP 请求** (L287-299)
  ```python
  for i in range(6, -1, -1):
      url = f"{API_PROXY}/admin/usage/daily?date={d_str}"
      req = urllib.request.Request(url, ...)
      with urllib.request.urlopen(req, timeout=10) as resp: ...
  ```
  7 个串行 HTTP 请求，每个 10s 超时，最坏情况 70 秒。可改为：
  - API 代理支持批量查询（`?start=2026-02-05&end=2026-02-12`）
  - 或使用 `concurrent.futures.ThreadPoolExecutor` 并行

• **[🟡中] JSONL 全量扫描** (L315-360)
  `_collect_session_logs()` 遍历所有 `.jsonl` 文件的每一行，即使文件可能积累到数万行。没有利用时间戳排序特性做早退优化，也没有跳过明显超出日期范围的文件（如检查 mtime）。

• **[🟢低] cleanup-task-chats 通过 importlib 动态加载** (L589-600)
  ```python
  _spec = importlib.util.spec_from_file_location(
      "cleanup_task_chats",
      os.path.join(os.path.dirname(__file__), "cleanup-task-chats.py"),
  )
  ```
  用 `importlib` 加载带连字符文件名的脚本，不如改名为 `cleanup_task_chats.py` 后正常 import，或直接 subprocess 调用。

### 1.4 拆分方案

当前 1126 行全在一个文件，建议拆为 5 个模块：

```
scripts/daily_report/
├── __init__.py          # 空
├── config.py            # 常量、路径、模型配置（~30 行）
├── collector.py         # DataCollector 类（~250 行）
├── analyzer.py          # LLMAnalyzer 类（~200 行）
├── assembler.py         # ReportAssembler + ReportDelivery（~300 行）
├── utils.py             # log, call_llm, run_cmd, read_file（~60 行）
└── __main__.py          # main() 入口（~50 行）
```

**拆分优先级**：
1. **config.py 最先拆** — 所有密钥、路径、常量集中管理，解决硬编码散布问题
2. **collector.py** — 最独立，无 LLM 依赖，可单独测试
3. **analyzer.py** — LLM 调用集中，便于切换模型或 mock 测试
4. **assembler.py** — 纯文本拼接，容易测试

**入口保持 `daily-report-engine.py`**（向后兼容）：
```python
from daily_report.__main__ import main
main()
```

---

## 2. token-hourly-stats.py — 逐项审查

### 2.1 安全问题

• **[🔴高] APP_SECRET 硬编码** (L29-30)
  ```python
  APP_ID = "cli_a90c3a6163785ed2"
  APP_SECRET = "***LARK_SECRET_REMOVED***"
  ```
  同上，全系统性问题。

### 2.2 逻辑缺陷

• **[🟡中] 端口不一致** (L32 vs L398)
  ```python
  ACCOUNT_LIMITS_URL = "http://localhost:8080/account-limits..."  # L32
  # ...
  resp = httpx.get(f"http://localhost:8180/admin/usage/hourly...",  # L398
  ```
  同一文件内用两个不同端口（8080 = api-proxy 的另一个？8180 = 同 daily-report-engine 的 API_PROXY）。应统一为常量。daily-report-engine.py 统一用 8180，这里 8080 可能是旧配置。

• **[🟡中] 混用 requests 和 httpx** (L1, L394)
  主体用 `requests`，但 `main()` 的 `last` 模式中 import `httpx`（L394）。选一个。如果 `httpx` 只用一处，改为 `requests` 即可。

• **[🟡中] scan_sessions 无增量机制**
  每次调用都全量扫描所有 JSONL 文件。对于 `last` 模式（每小时跑一次），大部分文件的大部分行都在时间窗口之外。
  **改进方案**：
  - 检查文件 mtime，跳过今天未修改的文件
  - 记录上次扫描位置（文件 offset），下次从断点继续

• **[🟢低] dedup 模式清空 600 行** (L462)
  ```python
  clear_count = max(len(rows), 600)
  clear_rows = [[""] * max_cols] * clear_count
  ```
  创建 600×11 的空数组通过 API 写入。如果表格增长，600 可能不够。应该用 `len(rows)` 而不是 `max(len(rows), 600)`——如果原始行数 < 600，多清也无害但浪费 API 调用。

• **[🟢低] 每日汇总的主会话/子任务分列不准** (L339)
  ```python
  row_data = [[target_date_str, inp, out, tot, cnt, cnt, 0, ""]]
  ```
  `cnt`（总请求数）直接填入"主会话"列，"子任务"永远是 0。从小时明细表求和时丢失了来源信息。

### 2.3 错误处理

• **[🟡中] get_tenant_token 无重试无错误传播** (L41-46)
  ```python
  def get_tenant_token():
      r = requests.post(..., json={...})
      return r.json().get("tenant_access_token")
  ```
  如果请求失败、返回非 200、或 JSON 解析失败，会静默返回 `None`。调用方检查了 `if not token`，但错误信息丢失。

• **[🟢低] scan_sessions 吞掉所有异常** (L88)
  ```python
  except Exception:
      pass
  ```
  文件读取失败完全静默，可能掩盖权限问题或编码错误。

---

## 3. deliver-daily-report.sh — 逐项审查

### 3.1 安全问题

• **[🟢低] 无敏感信息硬编码**
  Chat ID 和 Space ID 是标识符非密钥，可接受。

### 3.2 逻辑缺陷

• **[🟡中] 邮件 MIME 构造不完整** (L113-126)
  ```bash
  cat <<MIMEEOF
  From: Luna <luna@openclaw.local>
  To: $EMAIL
  Subject: $SUBJECT
  MIMEEOF
  ```
  - `Subject` 含中文和 emoji，未做 RFC 2047 编码（`=?UTF-8?B?...?=`）。部分邮件客户端可能乱码
  - `From` 地址 `luna@openclaw.local` 不是真实域名，可能被 spam filter 拦截
  - heredoc 和 `cat` 拼接的方式，MIME header 和 body 之间的空行由 heredoc 尾部换行保证，比较脆弱

• **[🟡中] `set -e` 与错误继续冲突** (L36)
  脚本开头 `set -e`，但 Wiki/Email 步骤失败后仍想继续。实际上 `if cat ... | script 2>&1; then` 的模式可以 catch 错误，但如果 `cat` 本身失败（文件被删），`set -e` 会直接退出，后续渠道全部跳过。

• **[🟢低] Wiki 成功检测逻辑** (L97)
  ```bash
  if echo "$WIKI_OUTPUT" | grep -q "^OK:"; then
  ```
  依赖 `md-to-lark-wiki.py` 的输出格式以 `OK:` 开头。如果脚本输出格式变更，这里会静默失败。

### 3.3 改进建议

• 用 Python 替代 shell 做邮件发送（proper MIME encoding）
• 或直接在 daily-report-engine.py 的 `ReportDelivery.deliver()` 中集成所有 4 个渠道，去掉 shell 脚本中间层

---

## 4. log-quota.sh — 逐项审查

### 4.1 核心问题：疑似死代码

• **[🔴高] 输出文件无消费者**
  ```bash
  LOG_FILE="$LOG_DIR/quota-snapshots.jsonl"
  ```
  写入 `data/quota-snapshots.jsonl`，但：
  - `daily-report-engine.py` 读的是 `data/quota-snapshots/YYYY-MM-DD.json`（目录，不是 JSONL）
  - `token-hourly-stats.py` 的 `save_quota_snapshot()` 也写入 `data/quota-snapshots/` 目录
  - 全仓库 `grep "quota-snapshots.jsonl"` 只有 `log-quota.sh` 自身
  
  **结论**：`log-quota.sh` 是早期残留代码，`token-hourly-stats.py` 的 `save_quota_snapshot()` 已完全替代其功能。
  **建议**：确认后删除。检查是否有 cron/heartbeat 还在调用它。

### 4.2 其他问题

• **[🟡中] Shell 变量注入风险** (L10-30)
  ```bash
  QUOTA_JSON=$(curl -s 'http://localhost:8080/account-limits?format=json' 2>/dev/null)
  python3 -c "... data = json.loads('''$QUOTA_JSON''') ..."
  ```
  将 curl 输出存入 shell 变量，再用 Python 三引号字符串解析。如果 JSON 中包含 `'''` 或 shell 特殊字符（`$`, `` ` ``），会导致解析失败或命令注入。应改为管道：`curl ... | python3 -c "import sys; data = json.load(sys.stdin)"`。

• **[🟢低] 只读第一个 account** (L22)
  ```python
  account = data['accounts'][0]
  ```
  假设单 account。如果 API 返回多 account，其余被忽略。

---

## 5. 跨模块分析

### 5.1 数据流图

```
                    ┌─────────────────────┐
                    │  API Proxy (:8180)   │
                    │  /admin/usage/daily  │
                    └──────────┬──────────┘
                               │
               ┌───────────────┼────────────────┐
               ▼               ▼                ▼
     daily-report-engine    token-hourly-stats   log-quota.sh
     (读 7 天 token 用量)   (读小时模型用量)      (❌ 死代码)
               │               │
               │               ▼
               │     quota-snapshots/YYYY-MM-DD.json
               │               │
               └───────────────┘
                       │
                       ▼
              daily-report-engine
              (读配额快照)
                       │
                       ▼
              deliver-daily-report.sh
              (Lark + Wiki + Email)
```

### 5.2 重复代码

| 模式 | 出现位置 | 建议 |
|------|----------|------|
| 密钥硬编码 | 20+ 个文件 | 提取到 `scripts/config.py` 或 `data/secrets.json` |
| Lark tenant_token 获取 | token-hourly-stats, cleanup-task-chats, 等 | 提取到共享模块 |
| JSONL session 扫描 | daily-report-engine, token-hourly-stats | 提取到 `scripts/session_scanner.py` |
| 时区 SGT 定义 | 每个文件各定义一次 | 放入共享 config |

### 5.3 配额数据碎片化

当前有 3 种配额数据存储：
1. `data/quota-snapshots/YYYY-MM-DD.json` — token-hourly-stats.py 写，daily-report-engine.py 读 ✅
2. `data/quota-snapshots.jsonl` — log-quota.sh 写，无人读 ❌（删除）
3. Lark 表格 HOURLY_SHEET 的配额列 — token-hourly-stats.py 写，人工查看 ✅

简化为：本地 JSON（自动化消费）+ Lark 表格（人工查看），删掉 JSONL。

---

## 6. 优先级排序的改进建议

### P0 — 安全
1. **密钥集中管理**：创建 `scripts/shared_config.py`，所有密钥从环境变量或 `data/secrets.json` 读取，全部脚本统一 import
2. 将 `data/secrets.json` 加入 `.gitignore`

### P1 — 清理
3. **删除 log-quota.sh**（确认无 cron 调用后）
4. **删除 `LLM_MODEL_HEAVY`** 或实际在 Code Review 中使用
5. **修复 `.md` 统计死代码**：要么把 `.md` 加入 `CODE_EXTS`，要么删除 `doc_files` 计数

### P2 — 拆分 daily-report-engine.py
6. 按上述方案拆为 `scripts/daily_report/` 包（5 个模块）
7. 保持 `daily-report-engine.py` 作为入口 shim

### P3 — 性能
8. **Token 用量批量获取**：API 代理增加 `?start=&end=` 参数，一次返回 7 天数据
9. **JSONL 扫描优化**：mtime 预过滤 + 文件 offset 记录
10. **统一 HTTP 库**：token-hourly-stats.py 去掉 httpx，统一用 requests

### P4 — 健壮性
11. **validate_and_fix 改用正则匹配章节标题**
12. **deliver-daily-report.sh 邮件编码修复**（或迁移到 Python）
13. **get_tenant_token 加重试 + 错误日志**

---

## 缺陷统计

| 严重程度 | 数量 | 分布 |
|----------|------|------|
| 🔴 高 | 3 | 密钥硬编码(×2), 死代码(×1) |
| 🟡 中 | 12 | 逻辑缺陷(6), 性能(3), 错误处理(2), 安全(1) |
| 🟢 低 | 6 | 代码质量(4), 健壮性(2) |
| **总计** | **21** | |

---

*Review generated by Luna code review engine*
