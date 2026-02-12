# SysMonitor 代码审查报告

**日期**: 2026-02-11  
**审查者**: Luna (subagent t122)  
**文件**: `inspect_session.py`, `task-dashboard.py`, `task-health-check.py`

---

## 1. 代码审查结果

### 1.1 `inspect_session.py` — 核心探测引擎

| 严重性 | 问题 | 行号 | 说明 |
|--------|------|------|------|
| 🟡 中等 | 路径遍历风险 | `get_session_file()` | session_id 未做任何清洗，直接拼接到路径。攻击者可传入 `../../etc/passwd` 读取任意 `.jsonl` 文件。建议：验证 session_id 只含合法字符（UUID 格式 `[a-f0-9-]`） |
| 🟡 中等 | `tail_jsonl` 内存整文件读取 | `tail_jsonl()` | `deque(f, maxlen=lines)` 会**逐行遍历整个文件**才取最后 N 行。对 1MB+ 的 session 文件（实测有 600KB+），每次调用都全文扫描。建议：使用 `seek` 从文件尾部反向读取 |
| 🟡 中等 | 时间戳解析不一致 | `analyze_session()` | 代码先用 `last_msg.get("timestamp")` 获取**根级** timestamp（ISO 字符串如 `"2026-02-09T06:01:29.509Z"`），但 `elif` 分支按 epoch-ms 处理。实际上根级 timestamp 都是 ISO 字符串，`message.timestamp` 才是 epoch-ms。当前逻辑用根级 timestamp，但如果它碰巧是整数就按 ms 解析——这在当前数据中不会出错，但逻辑不清晰 |
| 🟢 建议 | 裸 `except` | 多处 | 多处使用 `except:` 而非 `except Exception:`，会吞掉 `KeyboardInterrupt`、`SystemExit` 等 |
| 🟢 建议 | 未使用的 import | 顶部 | `glob` 被 import 但未使用 |
| 🟢 建议 | `from collections import deque` 位置 | 第32行 | 应移到文件顶部 |
| 🟢 建议 | 硬编码阈值 | 状态判断 | 60s/600s 状态阈值硬编码在函数体中，不可配置 |

**总体评价**: 核心逻辑正确，代码简洁。主要风险是路径遍历和大文件性能。

### 1.2 `task-dashboard.py` — 任务看板

| 严重性 | 问题 | 行号 | 说明 |
|--------|------|------|------|
| 🟡 中等 | 相对路径 `TASK_BOARD` | 第7行 | `Path("data/task-board.json")` 使用相对路径，取决于 `cwd`。如果从其他目录运行会找不到文件。`task-health-check.py` 用了绝对路径，这里应该保持一致 |
| 🟡 中等 | `"No Key"` 分支缺少描述截断 | `generate_dashboard()` | 当 `session_key` 为空时，直接打印 `task['description']` 而不截断，但有 `session_key` 的分支会截断到 30 字符。行为不一致 |
| 🟢 建议 | `load_board()` 无错误处理 | `load_board()` | 如果 JSON 损坏会抛未捕获的异常 |
| 🟢 建议 | 输出格式耦合 | `generate_dashboard()` | Markdown 表格直接 print，不适合非终端消费（如飞书消息）。可分离数据收集和格式化 |
| 🟢 建议 | 整数除法精度丢失 | token 显示 | `total_tokens // 1000` 对小于 1000 的值显示为 `0k` |

**总体评价**: 功能完整但有路径一致性问题。代码紧凑，作为内部工具可以接受。

### 1.3 `task-health-check.py` — 健康检查

| 严重性 | 问题 | 行号 | 说明 |
|--------|------|------|------|
| 🔴 严重 | `datetime.fromisoformat` 清理逻辑缺失 | 清理段落 | `datetime.fromisoformat(t["completed"])` 在 Python 3.10 之前不支持 `+08:00` 时区后缀，但当前 Python 3.12 已修复。不过如果 `completed` 字段格式意外（如 `Z` 结尾），会直接抛异常，导致**整个清理逻辑崩溃**，所有老任务永远不会清理 |
| 🟡 中等 | `task-chat.py` 的 `subprocess` 调用 | dissolve 逻辑 | 每次心跳都会对所有已完成的带 `task_chat_id` 的任务调用 dissolve，即使已经 dissolve 过。虽然设置了 `t["task_chat_id"] = None`，但只有在 `stale` 或 `cleaned` 变化时才 save —— 如果只有 dissolve 发生但没有 stale/cleaned，board 不会保存，下次还会重复 dissolve |
| 🟡 中等 | `inspect_session` 返回错误时的处理 | `check_health()` | 当 `inspect_session.analyze_session()` 返回 `{"error": ...}` 时，`age_seconds` 默认为 0，任务被认为活跃——即使 session 文件根本不存在。应视为异常信号 |
| 🟢 建议 | `sys.path.append` 可能冲突 | 第16行 | 如果 `scripts/` 目录中有与标准库同名的模块，会导致 import 冲突 |
| 🟢 建议 | 时区处理 | 多处 | SGT 偏移量硬编码为 +8，如果服务器时区变化需要手动修改 |

**总体评价**: 整体设计良好，自动化检测和清理逻辑实用。主要风险是 ISO 时间解析异常可能阻断清理流程，以及 dissolve 重复调用。

---

## 2. 测试方案

### 测试用例总览 (46 个测试)

| 类别 | 测试数 | 覆盖范围 |
|------|--------|----------|
| `tail_jsonl` | 10 | 正常文件、空文件、空行、损坏 JSON、全损坏、不存在、单行、超额请求、Unicode、大文件 |
| `get_session_file` | 5 | 直接 UUID、完整 session key、不存在、空字符串、feishu 格式 key |
| `analyze_session` | 9 | Running/Stalled/Dead 状态、不存在、空文件、列表内容提取、ISO/数字时间戳、usage 位置 |
| Task Dashboard | 5 | 无文件加载、正常加载、无活跃任务、无 key 任务、描述截断（bug 文档化） |
| Task Health Check | 9 | 空面板、活跃任务、不活跃超时、绝对超时、无 session 文件、清理旧任务、条件保存、已完成跳过、无 started 字段 |
| 集成测试 | 3 | 真实 session 分析、真实 task-board 加载、真实 JSONL tail |
| 边界情况 | 5 | 路径遍历、时间戳为0、缺失时间戳、toolResult 内容、仅 header 的 session |

### 详细测试文件
`tests/test_sysmonitor.py` — 完整的 pytest 测试套件

---

## 3. 测试执行结果

```
46 passed, 0 failed, 11 warnings in 0.15s
```

**通过率: 100%** (46/46)

⚠️ **注意**: 11 个 DeprecationWarning 来自测试代码中使用了 `datetime.utcnow()` 和 `datetime.utcfromtimestamp()`（Python 3.12 已弃用）。不影响测试正确性。

### 发现的 Bug（通过测试发现）

1. **`task-dashboard.py` 描述截断不一致** — `"No Key"` 分支不截断描述，但有 session_key 的分支截断到 30 字符。测试 `test_dashboard_description_truncation` 文档化了此行为。

---

## 4. 改进建议（按优先级排序）

### P0 — 应尽快修复

1. **`task-health-check.py` 清理逻辑异常处理**
   - 问题：`datetime.fromisoformat(t["completed"])` 可能因格式问题抛异常，阻断所有清理
   - 修复：用 try/except 包裹，异常时跳过该任务或保留

2. **`inspect_session.py` 路径遍历防护**
   - 问题：恶意 session_id 可读取任意 `.jsonl` 文件
   - 修复：验证 session_id 匹配 UUID 格式 `^[a-f0-9-]+$`
   - 影响：内部工具风险较低，但作为防御性编程应修复

### P1 — 近期修复

3. **`task-dashboard.py` 使用绝对路径**
   - 将 `Path("data/task-board.json")` 改为绝对路径，与 health-check 保持一致

4. **`task-health-check.py` dissolve 保存逻辑**
   - 在 dissolve 成功后也触发 board 保存，避免重复调用

5. **`task-health-check.py` 处理 inspect 错误**
   - 当 analyze_session 返回 error 时，应视为异常（而非活跃）

### P2 — 改进建议

6. **`inspect_session.py` 大文件性能优化**
   - 对大文件使用 seek 从尾部读取，而非全文遍历

7. **统一裸 `except` 为 `except Exception`**

8. **移除未使用的 import（`glob`）**

9. **将 `from collections import deque` 移到文件顶部**

10. **描述截断逻辑统一**（dashboard "No Key" 分支也应截断）

---

## 5. 安全评估摘要

| 维度 | 评级 | 说明 |
|------|------|------|
| 安全性 | ⚠️ 中等 | 路径遍历风险存在但影响有限（内部工具） |
| 健壮性 | ✅ 良好 | 大多数边界情况有处理，主要风险在 ISO 时间解析 |
| 正确性 | ✅ 良好 | 日志解析逻辑正确，状态判断合理 |
| 性能 | ⚠️ 中等 | `tail_jsonl` 全文扫描对大文件有性能影响 |
| 代码质量 | ✅ 良好 | 代码简洁清晰，少量风格问题 |
| 依赖 | ✅ 优秀 | 仅使用标准库，无外部依赖 |

**总体评级: B+** — 作为内部监控工具，代码质量良好，核心逻辑正确。建议优先修复 P0 级别的两个问题。
