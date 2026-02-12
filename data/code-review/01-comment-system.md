# Code Review: 文档评论系统

> 审查日期: 2026-02-12
> 审查范围: 14 个评论相关脚本
> 结论: **12 个可安全删除**，保留 2 个（1 个需重写）

---

## 一、文件清单与功能摘要

| # | 文件名 | 语言 | 行数 | 功能 | Token 来源 | doc 标识 | 并发 |
|---|--------|------|------|------|------------|----------|------|
| 1 | `check-comments.py` | Python | 78 | 扫描新评论 | subprocess+curl | `doc['id']` | ❌ |
| 2 | `check-comments-batch.py` | Python | 62 | 扫描新评论（并发） | requests | `doc['node_token']` | ✅ 10 workers |
| 3 | `check-new-comments.py` | Python | 60 | 扫描新评论 | sys.argv[1] | `doc['id']` | ❌ |
| 4 | `check_comments_batch.py` | Python | 56 | 扫描新评论 | requests | `doc['id']` | ❌ |
| 5 | `check_comments_temp.py` | Python | 60 | 扫描新评论 | ⚠️ **硬编码** | `doc['id']` | ❌ |
| 6 | `fetch_new_comments.py` | Python | 68 | 扫描新评论 | requests | `doc['id']` | ❌ |
| 7 | `list-pending-comments.py` | Python | 65 | 扫描新评论 | requests | `doc['node_token']` | ❌ |
| 8 | `scan-comments.py` | Python | 78 | 扫描新评论 | ⚠️ **硬编码** | `doc['id']` | ❌ |
| 9 | `scan-new-comments.py` | Python | 72 | 扫描新评论 | sys.argv[1] | `node_token` 或 `id` | ❌ |
| 10 | `scan_comments.py` | Python | 62 | 扫描新评论 | requests | `doc['id']` | ❌ |
| 11 | `scan_new_comments.py` | Python | 78 | 扫描新评论（并发） | requests | `doc['node_token']` | ✅ 20 workers |
| 12 | `temp-check-comments.py` | Python | 55 | 扫描新评论 | sys.argv[1] | `doc['id']` | ❌ |
| 13 | `check-doc-comments.sh` | Bash+Python | 72 | 扫描新评论 | curl | `doc['id']` | ❌ |
| 14 | `process-comment-done.sh` | Bash+Python | 138 | **删除已完成评论对应的文档 block** | user token | doc_id 参数 | ❌ |

---

## 二、重复分析

### 核心发现：13/14 个脚本做同一件事

除 `process-comment-done.sh` 外，**其余 13 个脚本功能完全相同**：

```
读取 tracked-docs.json → 获取 Lark tenant token → 调用 comments API → 对比 comment-state.json → 输出新评论 JSON
```

差异仅在于：
- Token 获取方式（自动获取 vs 命令行参数 vs 硬编码）
- 使用 `doc['id']` 还是 `doc['node_token']` 作为 API 标识符
- 是否使用 `concurrent.futures` 并发
- 路径是相对还是绝对
- 错误处理粒度

### 重复分组

#### 🔴 Group A: 硬编码 Token（必须立即删除 — 安全风险）
| 文件 | 问题 |
|------|------|
| `check_comments_temp.py` | 硬编码 `t-g2062a693CDQ...` |
| `scan-comments.py` | 硬编码 `t-g2062a7EMQBQ...` |

> ⚠️ **安全警告**：这些文件包含明文 tenant access token。虽然 token 会过期，但这是极差的安全实践。

#### 🟡 Group B: 名字含 "temp" 的临时文件
| 文件 | 问题 |
|------|------|
| `check_comments_temp.py` | 文件名含 "temp"，硬编码 token |
| `temp-check-comments.py` | 文件名含 "temp"，state 检查逻辑有 bug |

#### 🟠 Group C: 近乎完全相同的并发版本
| 文件 | Workers | 差异 |
|------|---------|------|
| `check-comments-batch.py` | 10 | 原版 |
| `scan_new_comments.py` | 20 | 几乎逐行复制，仅改了 workers 数 |

#### 🔵 Group D: 命名冲突（下划线 vs 连字符）
| 连字符版 | 下划线版 | 实质差异 |
|----------|----------|----------|
| `check-comments-batch.py` | `check_comments_batch.py` | 并发 vs 顺序 |
| `scan-new-comments.py` | `scan_new_comments.py` | 参数来源不同 |

#### ⬜ Group E: Shell wrapper（不必要的复杂度）
| 文件 | 问题 |
|------|------|
| `check-doc-comments.sh` | Bash 获取 token → 内嵌 Python → 用 urllib（不用 requests），完全多余 |

### 唯一不同的脚本

**`process-comment-done.sh`** — 功能完全不同！
- 用途：根据评论 quote 找到文档中对应的 block，然后删除该 block
- 流程：获取 block → quote 匹配 → 删除 block → 验证删除
- 使用 user_access_token（不是 tenant token）
- 有 4 步验证流程，代码质量较高
- **应该保留**

---

## 三、代码质量评估

### 3.1 共性问题（几乎所有脚本都有）

| 问题 | 严重性 | 涉及文件数 |
|------|--------|-----------|
| **API Secret 明文硬编码** | 🔴 高 | 10/14（app_id + app_secret 直接写在代码中） |
| **无分页处理** | 🟡 中 | 13/14（Lark API 默认 page_size=20，最多 50，超过会丢失评论） |
| **doc 标识符混乱** | 🟡 中 | 所有（有的用 `doc['id']`，有的用 `doc['node_token']`，没有统一） |
| **无重试机制** | 🟡 中 | 所有（网络错误直接跳过） |
| **state 检查逻辑不一致** | 🟡 中 | 多个（有的按 doc 分组检查，有的扁平化所有 ID） |
| **无日志记录** | 🟢 低 | 大部分（仅 print/stderr，无结构化日志） |

### 3.2 各文件具体问题

#### `check-comments.py`
- ❌ 用 `subprocess.check_output` 执行 curl 获取 token（Python 中完全不必要）
- ❌ 不保存 state（只读）
- ⚠️ 使用 `doc['id']` 作为 API token

#### `check-comments-batch.py`
- ✅ 并发处理（ThreadPoolExecutor）
- ✅ 函数结构良好
- ❌ 解析 content 时 bare except：`except: content = "[Complex Content]"`
- ⚠️ 使用 `doc['node_token']`

#### `check-new-comments.py`
- ✅ Token 通过参数传入（较安全）
- ✅ `load_json` helper 函数
- ⚠️ 注释中对 `node_token` vs `id` 的困惑表明开发者自己也不确定

#### `check_comments_batch.py`
- ❌ 使用相对路径 `data/...`（依赖 cwd）
- ❌ 全局 `token` 变量与函数内 `token` 参数命名冲突
- ❌ `FileNotFoundError` 用 `sys.exit(1)` 但无信息

#### `check_comments_temp.py`
- 🔴 **硬编码过期 token**
- ❌ 扁平化 state（所有 doc 的 comment_id 合并到一个 set），如果不同 doc 有相同 comment_id 会误判
- ❌ 名称含 "temp"，明显是临时调试文件

#### `fetch_new_comments.py`
- ✅ **本组中代码质量最高**
- ✅ 良好的错误处理（`resp.raise_for_status()`）
- ✅ 结构清晰、函数分离
- ❌ 仍然硬编码 app_id/secret

#### `list-pending-comments.py`
- ✅ 自动创建 state 文件（如不存在）
- ❌ 使用 `doc['node_token']` 但注释自相矛盾
- ❌ 变量命名 `token` 被复用（tenant token 变量覆盖）

#### `scan-comments.py`
- 🔴 **硬编码过期 token**
- ✅ 有函数结构和 stderr 分离
- ✅ 过滤了权限错误（code 1061001）
- ⚠️ 注释中大量困惑文字

#### `scan-new-comments.py`
- ✅ 参数传入 token
- ✅ Fallback：`doc.get('node_token') or doc.get('id')`
- ❌ State 类型检查是临时修补：`if isinstance(state, list): state = {}`

#### `scan_comments.py`
- ❌ `comment_id in comment_state` 检查的是 dict keys（顶层 doc ID），不是 comment ID 列表 — **逻辑 Bug**
- ❌ 无函数结构

#### `scan_new_comments.py`
- ⚠️ 与 `check-comments-batch.py` 几乎逐行相同，仅 `max_workers=20`
- ✅ 多了外层 try-except 返回 error JSON

#### `temp-check-comments.py`
- ❌ 名称含 "temp"
- ❌ 使用相对路径
- ❌ `processed_comments = set(state.keys())` — 检查 doc token 而非 comment ID — **逻辑 Bug**

#### `check-doc-comments.sh`
- ❌ Bash + 内嵌 Python 混合体（不必要的复杂度）
- ❌ 使用 `urllib.request` 而非 requests
- ✅ 解析 reply_list 提取评论文本（其他脚本没做到）

#### `process-comment-done.sh` ✅
- ✅ 功能独特：删除已完成评论对应的 block
- ✅ 4 步验证流程（获取→匹配→删除→验证）
- ✅ 良好的错误码和帮助信息
- ✅ 支持模糊匹配（前20字符前缀匹配）
- ⚠️ 使用 user_access_token（从文件读取，较安全）
- ⚠️ 内嵌 Python heredoc 不够优雅，但可维护

---

## 四、合并方案

### 最终保留 2 个脚本

#### 1. `check-comments.py` — 统一的评论扫描器（需重写）

整合所有扫描脚本的优点：

```
来自 check-comments-batch.py   → 并发执行架构
来自 fetch_new_comments.py     → 错误处理最佳实践
来自 scan-comments.py          → stderr 日志分离、权限错误过滤
来自 check-doc-comments.sh     → reply_list 内容解析
来自 scan-new-comments.py      → doc token fallback 逻辑
```

**重写要点：**
```python
# 1. 配置集中化
CONFIG = {
    "tracked_docs": os.environ.get("TRACKED_DOCS", "/path/to/tracked-docs.json"),
    "comment_state": os.environ.get("COMMENT_STATE", "/path/to/comment-state.json"),
    "app_id": os.environ.get("LARK_APP_ID"),       # 不再硬编码
    "app_secret": os.environ.get("LARK_APP_SECRET"), # 不再硬编码
}

# 2. 支持分页
def get_all_comments(file_token, token):
    """分页获取所有评论"""
    all_items = []
    page_token = None
    while True:
        params = {"file_type": "docx", "page_size": 50}
        if page_token:
            params["page_token"] = page_token
        # ...
        if not data.get("data", {}).get("has_more"):
            break
        page_token = data["data"].get("page_token")
    return all_items

# 3. 并发 + 重试
# 4. 结构化输出 (JSON to stdout, logs to stderr)
# 5. 可选：更新 state 文件 (--update-state flag)
```

#### 2. `process-comment-done.sh` — 保留原样

功能独特（写操作），代码质量可接受，目前无需改动。

---

## 五、可安全删除的文件

### 🔴 立即删除（安全风险 + 明显临时文件）

| 文件 | 删除理由 |
|------|----------|
| `check_comments_temp.py` | 硬编码 token + "temp" 命名 |
| `temp-check-comments.py` | "temp" 命名 + 逻辑 Bug |
| `scan-comments.py` | 硬编码 token |

### 🟡 合并后删除（功能重复）

| 文件 | 删除理由 |
|------|----------|
| `check-comments-batch.py` | 被统一版取代 |
| `check-new-comments.py` | 被统一版取代 |
| `check_comments_batch.py` | 被统一版取代，相对路径有问题 |
| `fetch_new_comments.py` | 被统一版取代（最佳实践已吸收） |
| `list-pending-comments.py` | 被统一版取代 |
| `scan-new-comments.py` | 被统一版取代 |
| `scan_comments.py` | 被统一版取代，有逻辑 Bug |
| `scan_new_comments.py` | check-comments-batch.py 的近乎复制品 |
| `check-doc-comments.sh` | Bash wrapper 不必要，Python 版更好 |

### ✅ 保留

| 文件 | 理由 |
|------|------|
| `check-comments.py` | 重写为统一版评论扫描器 |
| `process-comment-done.sh` | 功能独特（block 删除），代码质量可接受 |

---

## 六、删除命令（供执行参考）

```bash
# Step 1: 先备份到 trash
cd /home/ubuntu/.openclaw/workspace

# 立即删除（安全风险）
trash scripts/check_comments_temp.py
trash scripts/temp-check-comments.py
trash scripts/scan-comments.py

# 合并后删除（功能重复）
trash scripts/check-comments-batch.py
trash scripts/check-new-comments.py
trash scripts/check_comments_batch.py
trash scripts/fetch_new_comments.py
trash scripts/list-pending-comments.py
trash scripts/scan-new-comments.py
trash scripts/scan_comments.py
trash scripts/scan_new_comments.py
trash scripts/check-doc-comments.sh
```

---

## 七、额外建议

1. **API Secret 应移至环境变量或 secrets 文件**：当前 `app_id`/`app_secret` 在 10+ 个文件中明文出现
2. **统一 doc 标识符**：确认 Lark API 应使用 `doc['id']`（obj_token）还是 `doc['node_token']`，在代码中统一
3. **添加分页支持**：当前所有脚本只取第一页（最多 50 条评论），超过会遗漏
4. **考虑添加 state 自动更新**：当前扫描脚本只读 state，不写 state，需要另外的机制更新
5. **process-comment-done.sh 可考虑改写为 Python**：消除 Bash+heredoc Python 的混合，提高可维护性

---

## 总结

| 指标 | 值 |
|------|---|
| 审查文件总数 | 14 |
| 功能重复文件 | 12（86%） |
| 有安全问题的文件 | 3（硬编码 token） |
| 有逻辑 Bug 的文件 | 3 |
| 建议保留 | 2（check-comments.py 需重写 + process-comment-done.sh） |
| 建议删除 | 12 |
| 冗余度 | **极高**（同一功能写了 13 遍） |
