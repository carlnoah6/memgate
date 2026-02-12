# Code Review: 知识同步系统

## 📋 Review 范围

| 文件 | 行数 | 用途 |
|------|------|------|
| `knowledge-sync.py` | 963 | 知识同步总线 v2（变更检测 + diff + 广播 + watcher） |
| `auto-wiki-sync.py` | 208 | 本地 MD → Lark Wiki 自动同步 |
| `init-carl-knowledge.py` | 116 | Privacy Guard 知识库初始化 |
| `start-knowledge-watcher.sh` | 45 | 启动 watcher 守护进程 |
| `stop-knowledge-watcher.sh` | 33 | 停止 watcher 守护进程 |
| `sync_memgate_wiki.py` | 73 | MemGate README → Wiki（一次性） |
| `sync_model_arch_wiki.py` | 89 | Model Architecture → Wiki（一次性） |
| `sync_tokenizer_wiki.py` | 105 | Tokenizer MVP → Wiki（一次性） |
| `sync_wiki_release.py` | 78 | MemGate Release Note → Wiki（一次性） |
| `upload_wiki_content.py` | 113 | Data Pipeline → Wiki（一次性） |
| `write_wiki_content.py` | 133 | Data Processing 大纲 → Wiki（一次性） |
| `write-continuation.py` | 102 | 重启续接文件管理 |
| `check-continuation.py` | 62 | 重启后检查续接任务 |

**总计：~2120 行**

---

## 1. knowledge-sync.py — 应否拆分？

### 当前结构

963 行单文件，包含 7 个逻辑模块：
1. **配置**（WATCHED_FILES 字典 + 常量）~60 行
2. **状态管理**（load/save state）~30 行
3. **文件哈希 & diff**（md5/diff/summary）~180 行
4. **Session 发现**（get_active_sessions/is_group_session）~60 行
5. **广播**（inject_message/build_rich_notification）~80 行
6. **核心逻辑**（check_changes/build_broadcast_output）~100 行
7. **CLI 命令**（cmd_check/notify/status/init/diff/broadcast/watch + main）~400 行

### 评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 职责清晰度 | ⭐⭐⭐ | 每个函数职责单一，但文件级混合了 diff 引擎、网络通信、进程管理 |
| 可维护性 | ⭐⭐⭐ | 当前可读，但再增长 200 行就会变困难 |
| 可测试性 | ⭐⭐ | diff/summary 逻辑无法独立测试，因为都在同一个 import chain |
| 复用性 | ⭐⭐ | diff 逻辑和 session 发现逻辑可以被其他脚本复用 |

### 建议：适度拆分为 3 个模块

```
scripts/
  knowledge_sync/
    __init__.py           # CLI 入口
    config.py             # WATCHED_FILES, 常量, SGT, 路径
    differ.py             # file_md5, generate_diff_text, generate_diff_summary, extract_section_headers
    broadcaster.py        # get_active_sessions, inject_message, build_rich_notification
    state.py              # load_state, save_state
    commands.py           # cmd_check, cmd_notify, cmd_status, cmd_init, cmd_diff, cmd_broadcast, cmd_watch
  knowledge-sync.py       # 保留为 thin wrapper: from knowledge_sync import main; main()
```

**优先级：🟡 中** — 当前 963 行虽大但还在可控范围。如果需要新增监控文件类型、添加新广播通道（Telegram/Discord）、或增加 rate limiting，拆分将变得必要。

---

## 2. sync_*_wiki.py 系列 — 能否抽象？

### 问题分析

5 个文件（sync_memgate_wiki.py, sync_model_arch_wiki.py, sync_tokenizer_wiki.py, sync_wiki_release.py, upload_wiki_content.py）+ write_wiki_content.py，**总共 ~591 行**，全部做同一件事：

1. 读 token
2. 创建 Wiki 节点
3. 构建 Lark 文档 block 数组
4. POST 到 docx API

### 严重问题

| 问题 | 严重性 | 涉及文件 |
|------|--------|---------|
| **硬编码 token** | 🔴 **Critical** | `sync_memgate_wiki.py` — 明文 `u-4d_3ljMKN...` 直接写在代码里 |
| **硬编码 token** | 🔴 **Critical** | `upload_wiki_content.py` — 明文 `u-7OwU0AqF...` 直接写在代码里 |
| **代码重复率 >80%** | 🟡 Medium | 6 个文件都重复了 create_wiki_node + write_content 逻辑 |
| **混用 requests/urllib** | 🟢 Low | sync_wiki_release 用 urllib，其他用 requests，风格不统一 |
| **无错误重试** | 🟡 Medium | token 过期、网络错误都没有重试 |
| **一次性脚本留存** | 🟡 Medium | 这些是早期手动同步的产物，`auto-wiki-sync.py` + `md-to-lark-wiki.py` 已经替代了它们 |

### 建议

**短期（推荐立即执行）**：
1. **删除硬编码 token** — `sync_memgate_wiki.py` 和 `upload_wiki_content.py` 中的明文 token 必须清除
2. **归档这 6 个一次性脚本** — 移到 `scripts/archive/` 或直接删除。它们已被 `auto-wiki-sync.py` 取代

**如果要保留**（不推荐，因为 auto-wiki-sync 已经做了）：
```python
# scripts/wiki_sync_base.py — 通用基类
class WikiSyncer:
    def __init__(self, space_id, parent_node_token, title):
        self.token = self._load_token()
        ...
    
    def _load_token(self):
        with open("data/lark-user-token.json") as f:
            return json.load(f)["access_token"]
    
    def create_node(self) -> str: ...
    def write_blocks(self, obj_token, blocks): ...
    def sync_markdown(self, filepath): ...
    def sync_code(self, filepath, language=16): ...
```

**优先级：🔴 高**（因为硬编码 token），🟡 中（代码重复）

---

## 3. auto-wiki-sync.py — 质量评估

### 优点
- ✅ 设计清晰：注册 → 检查变更 → 按需同步
- ✅ hash-based 变更检测，避免无谓同步
- ✅ 每个文件同步后立即保存进度（partial progress）
- ✅ 支持项目分组和自动创建 Wiki 节点
- ✅ Rate limiting（`time.sleep(1)`）

### 问题

| 问题 | 严重性 | 说明 |
|------|--------|------|
| 无 token 刷新集成 | 🟡 Medium | `ensure_token()` 检查但不阻断，token 过期后同步静默失败 |
| 正则解析输出 | 🟡 Medium | `sync_file()` 用正则从子进程输出提取 node/obj token，脆弱 |
| 无并发控制 | 🟢 Low | 多个进程同时运行可能竞争 wiki-sync.json |
| import re 在函数内 | 🟢 Low | `sync_file()` 内部 `import re`，应移到顶部 |

### 建议
- `md-to-lark-wiki.py` 应输出结构化 JSON（`--json` flag），而不是让调用者正则解析 stdout
- Token 过期时应 fail fast + 明确报错，而不是继续同步然后得到 400/401

---

## 4. Watcher 可靠性评估

### start/stop 脚本

**优点**：
- ✅ PID 文件管理正确（检查 stale PID、`kill -0` 验证）
- ✅ stop 有 graceful 等待 + force kill fallback
- ✅ 自动安装 inotify-tools
- ✅ 状态初始化（init if not exists）

**问题**：

| 问题 | 严重性 | 说明 |
|------|--------|------|
| **nohup 后台启动不可靠** | 🟡 Medium | `nohup ... &` 在 SSH 断开、shell 退出时可能被清理。没有 systemd unit |
| **无自动重启** | 🟡 Medium | watcher 崩溃后不会自动恢复，依赖心跳检测（check-restart.sh → start-knowledge-watcher.sh） |
| **日志无 rotation** | 🟡 Medium | `>> LOG_FILE` 持续追加，长期运行会膨胀 |
| **PID 文件竞态** | 🟢 Low | start 时 `sleep 1` 后检查，极端情况下进程启动慢可能误判 |

### knowledge-sync.py watch 命令

**优点**：
- ✅ inotifywait 事件驱动（不是轮询），CPU 开销极低
- ✅ 监听目录级 `close_write,moved_to`，覆盖编辑器的 unlink+create 保存方式
- ✅ 3 秒 debounce 避免重复触发
- ✅ broadcast 以子进程异步执行，不阻塞 watcher 主循环
- ✅ SIGTERM/SIGINT 优雅退出
- ✅ inotifywait 崩溃后自动重启（`while running` 循环 + 5 秒延迟）

**问题**：

| 问题 | 严重性 | 说明 |
|------|--------|------|
| **只监听工作区根目录** | 🟡 Medium | 如果 WATCHED_FILES 扩展到子目录（如 `memory/xxx.md`），需要加 `-r` 或监听多个目录 |
| **broadcast 子进程不追踪** | 🟡 Medium | `subprocess.Popen()` fire-and-forget，如果广播失败无人知晓 |
| **debounce 不够精确** | 🟢 Low | 3 秒窗口 + 0.5 秒等待在实际使用中够用，但理论上多文件同时修改只处理第一个 |
| **inotifywait 缓冲区溢出** | 🟢 Low | 极端情况下（大量文件变更）inotifywait 事件队列可能溢出，但工作区只有 7 个文件无此风险 |

### 建议
1. **短期**：添加日志 rotation（`logging.handlers.RotatingFileHandler`，max 5MB × 3 文件）
2. **中期**：考虑 systemd user service 替代 nohup（更可靠的进程管理）
3. **低优先级**：broadcast 子进程输出重定向到日志而非 /dev/null，方便排查失败

---

## 5. 错误恢复机制评估

### write-continuation.py + check-continuation.py

**优点**：
- ✅ 干净的 JSON 持久化（重启不丢状态）
- ✅ retry 计数 + max_retries 防止无限循环
- ✅ bump_retry() 超过上限自动清理文件
- ✅ 支持 chat_id 和 source_session 路由
- ✅ CLI 和 Python import 双模式

**问题**：

| 问题 | 严重性 | 说明 |
|------|--------|------|
| **单文件单任务** | 🟡 Medium | 只能有一个 continuation，多个任务需要重启续接时后者覆盖前者 |
| **steps 是纯文本** | 🟢 Low | 没有结构化步骤，依赖 LLM 理解自然语言指令 |
| **无锁** | 🟢 Low | 并发读写 restart-continuation.json 理论上有竞态，但实际只有心跳读 |

### knowledge-sync.py 的错误恢复

| 场景 | 处理方式 | 评分 |
|------|---------|------|
| inotifywait 崩溃 | while 循环自动重启（5s 延迟） | ✅ 好 |
| 广播失败 | 日志记录，继续处理其他 session | ✅ 好 |
| 状态文件损坏 | 回退到空状态（不崩溃） | ✅ 好 |
| token 过期导致 inject 失败 | 日志记录 stderr，返回 False | ⚠️ 没有重试 |
| 目标文件被删除 | 记录 "deleted" 变更类型 | ✅ 好 |
| openclaw sessions CLI 超时 | 30 秒超时 + 异常捕获 → 返回空列表 | ✅ 好 |

### init-carl-knowledge.py 的问题

| 问题 | 严重性 | 说明 |
|------|--------|------|
| **无幂等性** | 🟡 Medium | 每次运行先 `unlink()` 全部再重建，如果中途失败数据全丢 |
| **硬编码数据** | 🟢 Low | 所有知识条目硬编码在脚本里，与 USER.md/people/ 同步靠人工 |
| **无增量更新** | 🟡 Medium | 新增知识必须改代码，没有从源文件自动提取的机制 |

---

## 6. 总结 & 优先级排序

### 🔴 必须修复（安全问题）

1. **删除硬编码 token** — `sync_memgate_wiki.py` 第 7 行、`upload_wiki_content.py` 第 7 行
   - 即使是过期 token 也不应留在代码里（尤其如果代码进 git）
   - 修复方式：替换为 `data/lark-user-token.json` 读取，或直接删除这两个脚本

### 🟡 建议改进

2. **归档 6 个一次性 sync 脚本**（~590 行 → 0 行活跃代码）
   - 移到 `scripts/archive/` 并在 README 说明"仅供参考，已被 auto-wiki-sync.py 取代"
   - 净减 ~590 行维护负担

3. **knowledge-sync.py 添加日志 rotation**
   - `knowledge-watcher.log` 无限增长
   - 一行修复：`RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)`

4. **continuation 系统支持多任务**
   - 改为 `data/continuations/` 目录，每个任务一个 JSON 文件（带 UUID 文件名）
   - check-continuation 遍历目录返回所有待执行任务

### 🟢 可选优化

5. **knowledge-sync.py 模块化拆分** — 当前不急，增长到 1200+ 行时再做
6. **auto-wiki-sync.py 的 md-to-lark-wiki.py 输出结构化** — 消除正则解析
7. **systemd user service 替代 nohup** — 更可靠的 watcher 进程管理
8. **init-carl-knowledge.py 改为从 USER.md 自动提取** — 消除硬编码知识

### 代码质量评分

| 组件 | 质量 | 说明 |
|------|------|------|
| knowledge-sync.py | ⭐⭐⭐⭐ | 架构清晰，功能完整，只是略大 |
| auto-wiki-sync.py | ⭐⭐⭐⭐ | 设计合理，增量同步做得好 |
| start/stop-watcher.sh | ⭐⭐⭐⭐ | 健壮的 PID 管理 |
| write/check-continuation.py | ⭐⭐⭐⭐ | 简洁有效，retry 机制好 |
| sync_*_wiki.py 系列 | ⭐⭐ | 一次性脚本，硬编码 token，应归档 |
| init-carl-knowledge.py | ⭐⭐⭐ | 功能达标但缺乏幂等性和自动化 |

### 总体评价

知识同步系统的**核心组件（knowledge-sync.py + auto-wiki-sync.py + watcher）质量良好**，架构合理，错误处理到位。主要问题集中在：

1. **历史遗留**：6 个一次性 sync 脚本是早期手动操作的产物，已被自动化流程取代，应归档清理
2. **安全隐患**：2 个文件硬编码了 Lark user token（虽然可能已过期）
3. **运维**：日志无 rotation、watcher 依赖 nohup 而非 systemd

建议的行动顺序：先清 token（5 分钟）→ 归档旧脚本（10 分钟）→ 加日志 rotation（5 分钟）→ 其他按需。
