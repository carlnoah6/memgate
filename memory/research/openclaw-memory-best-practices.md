# OpenClaw 内存管理最佳实践研究报告

**研究日期**: 2026-02-09
**研究者**: Luna (subagent)
**环境**: Ubuntu Linux x86_64, 8GB RAM, 187GB 可用磁盘, Node v22.22.0

---

## 目录

1. [当前环境诊断](#1-当前环境诊断)
2. [OpenClaw 内存管理功能全景](#2-openclaw-内存管理功能全景)
3. [memory_search 启用方案](#3-memory_search-启用方案)
4. [上下文注入机制详解](#4-上下文注入机制详解)
5. [推荐方案与实施步骤](#5-推荐方案与实施步骤)
6. [成本分析](#6-成本分析)
7. [具体配置建议](#7-具体配置建议)

---

## 1. 当前环境诊断

### 已确认的问题

| 问题 | 状态 | 原因 |
|------|------|------|
| MEMORY.md 截断 | ⚠️ 潜在风险 | 当前 5,997 chars，远低于 20,000 上限，暂不是问题 |
| memory_search 不可用 | ❌ 确认 | 无 OpenAI/Gemini API key，本地模型未构建 |
| people/data/ 不自动加载 | ❌ 设计如此 | 只有 7 个固定 bootstrap 文件会被注入 |
| Session 间信息丢失 | ⚠️ 部分缓解 | memory/ 文件持久化，但无法语义检索 |

### 当前配置分析

```json5
// 当前 openclaw.json 中的相关配置
{
  agents: {
    defaults: {
      workspace: "/home/ubuntu/.openclaw/workspace",
      compaction: { mode: "safeguard" },
      // 无 memorySearch 配置
      // 无 bootstrapMaxChars 覆盖（使用默认 20000）
    }
  }
  // 无 memory 配置
  // 无 hooks 配置
}
```

### 可用资源

- **antigravity proxy**: `https://anz-luna.grolar-wage.ts.net/api` — **不支持 embeddings endpoint**（已测试，返回 404）
- **node-llama-cpp**: v3.15.1 已安装，`@node-llama-cpp/linux-x64` 已安装
- **磁盘空间**: 187GB 可用（足够下载 GGUF 模型）
- **内存**: 7.6GB，可用 6.3GB（足够运行小型 embedding 模型）

---

## 2. OpenClaw 内存管理功能全景

### 2.1 文件系统内存（基础层）

OpenClaw 的内存是 **纯 Markdown 文件**，模型只"记住"写入磁盘的内容。

#### 双层结构

| 文件 | 用途 | 加载时机 | 当前大小 |
|------|------|----------|----------|
| `memory/YYYY-MM-DD.md` | 每日日志（追加写入） | 每次 session 开始读今天+昨天 | 4 个文件，共 ~28KB |
| `MEMORY.md` | 策展的长期记忆 | 仅在主 session 中加载 | 5,997 chars |

#### 上下文注入的 Bootstrap 文件（7 个固定文件）

| 文件 | 用途 | 注入方式 |
|------|------|----------|
| `AGENTS.md` | 操作指令、行为规则 | 每次 session 注入系统提示 |
| `SOUL.md` | 人格、语气、边界 | 每次 session 注入系统提示 |
| `USER.md` | 用户信息 | 每次 session 注入系统提示 |
| `IDENTITY.md` | Agent 名称和身份 | 每次 session 注入系统提示 |
| `TOOLS.md` | 本地工具笔记 | 每次 session 注入系统提示 |
| `HEARTBEAT.md` | 心跳运行清单 | 每次 session 注入系统提示 |
| `BOOTSTRAP.md` | 首次运行仪式 | 仅首次 |

**关键限制**: 
- 每个文件最大 `bootstrapMaxChars`（默认 20,000 chars）
- **不能添加自定义注入文件**——这 7 个是硬编码的
- 总计系统提示中的 Project Context 约 ~6,000 tokens（以当前文件大小计）

### 2.2 向量内存搜索（memory_search）

当启用时，OpenClaw 会对 `MEMORY.md` 和 `memory/*.md` 建立向量索引，支持语义搜索。

#### 提供的工具

| 工具 | 功能 |
|------|------|
| `memory_search` | 语义搜索，返回文件+行范围的片段（~700 chars） |
| `memory_get` | 读取特定内存文件的内容 |

#### 支持的 Embedding Provider

| Provider | 配置键 | 成本 | 前置条件 |
|----------|--------|------|----------|
| **OpenAI** | `provider: "openai"` | ~$0.02/M tokens | API key |
| **Gemini** | `provider: "gemini"` | 免费额度，之后 $0.00025/1K chars | API key |
| **Local (GGUF)** | `provider: "local"` | 免费 | node-llama-cpp 原生构建 |
| **自定义 OpenAI 兼容** | `provider: "openai"` + `remote.baseUrl` | 取决于服务 | 端点支持 `/v1/embeddings` |

#### 自动选择顺序

1. `local` — 如果 `memorySearch.local.modelPath` 已配置且文件存在
2. `openai` — 如果有 OpenAI key
3. `gemini` — 如果有 Gemini key
4. 禁用 — 如果都没有（**当前状态**）

### 2.3 QMD Backend（实验性）

QMD 是一个本地优先的搜索 sidecar，结合 BM25 + 向量 + 重排序。

#### 特点

- 完全本地运行（通过 Bun + node-llama-cpp）
- 自动从 HuggingFace 下载 GGUF 模型
- 支持额外路径索引
- 支持 session 历史索引
- SQLite 存储

#### 前置条件

- 需要安装 QMD CLI（`bun install -g github.com/tobi/qmd`）
- 需要 Bun 运行时
- 需要支持扩展的 SQLite

### 2.4 混合搜索（Hybrid Search）

结合向量相似度和 BM25 关键词搜索：

```json5
memorySearch: {
  query: {
    hybrid: {
      enabled: true,
      vectorWeight: 0.7,
      textWeight: 0.3,
      candidateMultiplier: 4
    }
  }
}
```

### 2.5 Session 内存搜索（实验性）

索引对话历史，可通过 `memory_search` 搜索：

```json5
memorySearch: {
  experimental: { sessionMemory: true },
  sources: ["memory", "sessions"]
}
```

### 2.6 自动内存刷新（Pre-compaction Flush）

当 session 接近自动压缩时，OpenClaw 触发一个静默的代理轮次，提醒模型写入持久记忆。

```json5
compaction: {
  reserveTokensFloor: 20000,
  memoryFlush: {
    enabled: true,
    softThresholdTokens: 4000,
    systemPrompt: "Session nearing compaction. Store durable memories now.",
    prompt: "Write any lasting notes to memory/YYYY-MM-DD.md; reply with NO_REPLY if nothing to store.",
  }
}
```

### 2.7 额外内存路径（extraPaths）

索引工作空间外的 Markdown 文件：

```json5
memorySearch: {
  extraPaths: ["../team-docs", "/srv/shared-notes/overview.md"]
}
```

### 2.8 Hooks 系统

可用于自动化内存相关操作：

| Hook | 功能 | 事件 |
|------|------|------|
| `session-memory` | /new 时保存 session 上下文到 memory/ | `command:new` |
| `command-logger` | 记录所有命令到审计日志 | `command` |
| `boot-md` | Gateway 启动时运行 BOOT.md | `gateway:startup` |
| `agent:bootstrap` | 在 bootstrap 文件注入前拦截和修改 | 自定义 |

### 2.9 Session 管理

- **压缩（Compaction）**: 摘要旧对话，保留近期消息
- **修剪（Pruning）**: 仅修剪旧工具结果，不重写历史
- **手动压缩**: `/compact` 命令
- **Session 重置**: `/new` 或 `/reset`

---

## 3. memory_search 启用方案

### 方案 A: 本地 GGUF 模型（推荐 ✅）

**可行性**: ✅ 高
**成本**: 免费（除了一次性下载 ~600MB）
**前置条件**: node-llama-cpp 原生构建

#### 步骤

1. **构建 node-llama-cpp 原生绑定**：
```bash
cd /home/ubuntu/.npm-global/lib/node_modules/openclaw
npx --yes node-llama-cpp download
```

2. **配置 openclaw.json**：
```json5
{
  agents: {
    defaults: {
      memorySearch: {
        provider: "local",
        // 默认模型: hf:ggml-org/embeddinggemma-300M-GGUF/embeddinggemma-300M-Q8_0.gguf (~600MB)
        // 自动下载到缓存目录
        fallback: "none"  // 不回退到远程
      }
    }
  }
}
```

3. **首次索引**：
```bash
openclaw memory index --verbose
```

#### 风险与注意

- node-llama-cpp 需要编译原生代码（需要 gcc/g++/cmake）
- 首次运行自动下载 ~600MB 的 embedding 模型
- 7.6GB RAM 应该足够运行 300M 参数的 embedding 模型
- x86_64 架构已有预编译的 `@node-llama-cpp/linux-x64` 包

### 方案 B: Gemini 免费 API Key

**可行性**: ✅ 高（需要注册 Google AI Studio）
**成本**: 免费额度内约 0（Gemini embeddings 免费额度很大）

#### 步骤

1. 在 https://aistudio.google.com/ 获取 API key
2. 配置：
```json5
{
  agents: {
    defaults: {
      memorySearch: {
        provider: "gemini",
        model: "gemini-embedding-001",
        remote: {
          apiKey: "YOUR_GEMINI_API_KEY"
        }
      }
    }
  }
}
```

#### 优势

- 最简单的配置
- Gemini embedding 免费额度非常大
- 不需要本地计算资源

#### 劣势

- 需要网络连接
- 数据发送到 Google
- 依赖第三方服务

### 方案 C: 通过 antigravity proxy 代理 OpenAI embeddings

**可行性**: ❌ 不可行
**原因**: 测试确认 antigravity proxy 不支持 `/v1/embeddings` endpoint（返回 404 not found）。Proxy 只支持 chat/completions。

### 方案 D: QMD Backend

**可行性**: ⚠️ 中等（需要额外安装 Bun + QMD）
**成本**: 免费

#### 步骤

1. 安装 Bun：
```bash
curl -fsSL https://bun.sh/install | bash
```

2. 安装 QMD：
```bash
bun install -g github.com/tobi/qmd
```

3. 配置：
```json5
{
  memory: {
    backend: "qmd",
    citations: "auto",
    qmd: {
      includeDefaultMemory: true,
      update: { interval: "5m", debounceMs: 15000 },
      limits: { maxResults: 6, timeoutMs: 4000 },
      paths: [
        { name: "people", path: "./people", pattern: "**/*.md" },
        { name: "data", path: "./data", pattern: "**/*.md" }
      ]
    }
  }
}
```

#### 优势

- 完全本地
- 结合 BM25 + 向量 + 重排序
- 可索引任意路径（不限于 memory/ 目录）
- 支持 session 历史索引

#### 劣势

- 需要安装 Bun（额外的运行时）
- 更复杂的设置
- 实验性功能

### 方案 E: 自建 OpenAI 兼容 embedding 服务

**可行性**: ⚠️ 中等
**成本**: 免费（本地运行）

可以用 Ollama 或 vLLM 本地部署 embedding 模型，然后通过 OpenAI 兼容 API 对接。

```json5
{
  agents: {
    defaults: {
      memorySearch: {
        provider: "openai",
        model: "nomic-embed-text",
        remote: {
          baseUrl: "http://localhost:11434/v1/",
          apiKey: "ollama"
        }
      }
    }
  }
}
```

---

## 4. 上下文注入机制详解

### 4.1 bootstrapMaxChars 调整

**当前值**: 20,000 chars（默认）
**当前 MEMORY.md**: 5,997 chars（远低于上限）

#### 增加的利弊

| 方面 | 增加到 40,000 | 增加到 100,000 |
|------|-------------|---------------|
| ✅ 优势 | 允许更大的 TOOLS.md/MEMORY.md | 几乎不会截断 |
| ❌ 劣势 | 每个文件多占 ~5K tokens | 每个文件多占 ~20K tokens |
| 💰 成本影响 | 适中（我们是 0 成本） | 高（消耗上下文窗口） |
| 🧠 上下文影响 | 可接受（1M 窗口） | 可接受但浪费 |

**建议**: 暂不调整。当前文件都在限制内。如果 MEMORY.md 增长到接近 20,000 chars 时，考虑将内容拆分到 memory/ 子文件，而不是增加限制。

### 4.2 自定义注入文件

**不可直接添加**。7 个 bootstrap 文件是硬编码在 OpenClaw 中的：
- `AGENTS.md`, `SOUL.md`, `TOOLS.md`, `IDENTITY.md`, `USER.md`, `HEARTBEAT.md`, `BOOTSTRAP.md`

#### 变通方案

1. **使用 AGENTS.md 或 TOOLS.md 作为载体**：将需要每次 session 加载的信息写入这些文件
2. **通过 `agent:bootstrap` hook 注入**：自定义 hook 可以修改 `context.bootstrapFiles` 数组
3. **使用 BOOT.md + boot-md hook**：Gateway 启动时自动执行指令
4. **使用 HEARTBEAT.md**：心跳运行时的检查清单

### 4.3 Compaction 和 Memory Flush 配置

当前配置：`compaction: { mode: "safeguard" }`

**推荐配置**：

```json5
{
  agents: {
    defaults: {
      compaction: {
        mode: "safeguard",
        memoryFlush: {
          enabled: true,
          softThresholdTokens: 4000,
        }
      }
    }
  }
}
```

### 4.4 通过 Hook 自动加载上下文

可以创建自定义 hook 在 `agent:bootstrap` 事件中注入额外文件：

```typescript
// hooks/extra-context/handler.ts
import type { HookHandler } from "../../src/hooks/hooks.js";

const handler: HookHandler = async (event) => {
  if (event.type !== "agent" || event.action !== "bootstrap") return;
  
  const { bootstrapFiles } = event.context;
  if (!bootstrapFiles) return;
  
  // 读取额外文件并注入
  const fs = await import("fs/promises");
  const extraContent = await fs.readFile(
    "/home/ubuntu/.openclaw/workspace/people/carl.md", "utf-8"
  ).catch(() => null);
  
  if (extraContent) {
    bootstrapFiles.push({
      name: "PEOPLE.md",
      content: extraContent,
      source: "extra-context hook"
    });
  }
};

export default handler;
```

**注意**: 这个方案较为复杂，需要了解 OpenClaw 内部 API 的具体类型定义。

---

## 5. 推荐方案与实施步骤

### 按优先级排序（从简到难）

#### 🟢 第一步：启用 session-memory hook（5 分钟）

```bash
openclaw hooks enable session-memory
openclaw gateway restart
```

**效果**: 每次 `/new` 重置 session 时，自动保存对话摘要到 `memory/` 目录。

#### 🟢 第二步：启用 memory flush（5 分钟）

在 `openclaw.json` 中添加：

```json5
{
  agents: {
    defaults: {
      compaction: {
        mode: "safeguard",
        memoryFlush: {
          enabled: true,
          softThresholdTokens: 4000
        }
      }
    }
  }
}
```

**效果**: Session 接近压缩前自动写入重要记忆。

#### 🟡 第三步：启用 memory_search（本地 GGUF）（30 分钟）

```bash
# 1. 确保编译工具链
sudo apt-get install -y build-essential cmake

# 2. 下载 node-llama-cpp 原生绑定
cd /home/ubuntu/.npm-global/lib/node_modules/openclaw
npx --yes node-llama-cpp download

# 3. 配置（见下方完整配置）

# 4. 索引
openclaw memory index --verbose

# 5. 测试搜索
openclaw memory search "Lark bot setup"
```

**效果**: 启用 `memory_search` 和 `memory_get` 工具，支持语义搜索所有记忆文件。

#### 🟡 第四步（备选）：获取 Gemini API Key（15 分钟）

如果本地 GGUF 有问题，这是最简单的远程替代方案：

1. 访问 https://aistudio.google.com/
2. 创建 API Key（免费）
3. 配置到 `openclaw.json`

#### 🟠 第五步：优化 MEMORY.md 结构（持续）

将 MEMORY.md 控制在 20,000 chars 以内：

- 将详细信息移到 `memory/reference/` 下的专题文件
- MEMORY.md 只保留高频访问的核心信息
- 定期在心跳中审查和精简

#### 🔴 第六步（可选）：QMD Backend（1-2 小时）

如果需要索引 memory/ 以外的目录（如 `people/`, `data/`），考虑 QMD。

---

## 6. 成本分析

| 方案 | 初始成本 | 持续成本 | 资源消耗 |
|------|----------|----------|----------|
| Session-memory hook | 免费 | 每次 /new 一次 LLM 调用（通过现有模型） | 极低 |
| Memory flush | 免费 | 每次压缩前一次 LLM 调用 | 极低 |
| Local GGUF embedding | 免费（下载 ~600MB） | CPU 时间（极低） | ~500MB RAM |
| Gemini embedding | 免费 | 免费额度内 $0 | 网络流量 |
| QMD | 免费（下载 Bun + QMD） | CPU 时间 | ~1GB RAM+磁盘 |

**总结**: 所有方案在我们的环境中都是 **零货币成本**，因为：
- 我们通过 antigravity proxy 使用 LLM，成本为 0
- 本地 GGUF 是免费的
- Gemini embedding 有很大的免费额度

---

## 7. 具体配置建议

### 推荐的 openclaw.json 增量配置

```json5
// 在现有 openclaw.json 中添加/修改以下内容：
{
  // === 方案 A: 本地 GGUF（推荐） ===
  agents: {
    defaults: {
      // ... 现有配置保持不变 ...
      
      // 添加 memorySearch 配置
      memorySearch: {
        provider: "local",
        // 使用默认的 embeddinggemma-300M-GGUF（~600MB，首次自动下载）
        fallback: "none",
        query: {
          hybrid: {
            enabled: true,
            vectorWeight: 0.7,
            textWeight: 0.3
          }
        },
        cache: {
          enabled: true,
          maxEntries: 50000
        }
      },
      
      // 修改 compaction 配置
      compaction: {
        mode: "safeguard",
        memoryFlush: {
          enabled: true,
          softThresholdTokens: 4000
        }
      }
    }
  },
  
  // 启用 hooks
  hooks: {
    internal: {
      enabled: true,
      entries: {
        "session-memory": { enabled: true },
        "command-logger": { enabled: true }
      }
    }
  }
}
```

```json5
// === 方案 B: Gemini 远程（备选） ===
{
  agents: {
    defaults: {
      memorySearch: {
        provider: "gemini",
        model: "gemini-embedding-001",
        remote: {
          apiKey: "YOUR_GEMINI_API_KEY"  // 从 aistudio.google.com 获取
        },
        query: {
          hybrid: {
            enabled: true,
            vectorWeight: 0.7,
            textWeight: 0.3
          }
        }
      }
    }
  }
}
```

```json5
// === 方案 C: QMD（高级，可索引任意路径） ===
{
  memory: {
    backend: "qmd",
    citations: "auto",
    qmd: {
      includeDefaultMemory: true,
      update: { interval: "5m", debounceMs: 15000 },
      limits: { maxResults: 6, timeoutMs: 4000 },
      scope: {
        default: "deny",
        rules: [{ action: "allow", match: { chatType: "direct" } }]
      },
      paths: [
        { name: "people", path: "/home/ubuntu/.openclaw/workspace/people", pattern: "**/*.md" },
        { name: "data", path: "/home/ubuntu/.openclaw/workspace/data", pattern: "**/*.md" }
      ],
      sessions: {
        enabled: true,
        retentionDays: 30
      }
    }
  }
}
```

### MEMORY.md 管理最佳实践

1. **保持精简**: MEMORY.md 只存放最重要、最常需要的信息
2. **结构化**: 使用清晰的标题和分类
3. **定期清理**: 通过心跳定期审查，移除过期信息
4. **分层存储**:
   - `MEMORY.md` → 高频核心信息（<15,000 chars 目标）
   - `memory/reference/*.md` → 详细参考资料
   - `memory/YYYY-MM-DD.md` → 每日日志
   - `people/*.md` → 人物信息（需要 memory_search 才能被检索）
   - `data/*.md` → 数据和配置参考

### 信息持久化策略

| 信息类型 | 存储位置 | 加载方式 |
|----------|----------|----------|
| 核心偏好/决策 | MEMORY.md | 自动注入系统提示 |
| 每日事件 | memory/YYYY-MM-DD.md | 手动/指令读取，memory_search |
| 人物信息 | people/*.md | memory_search 或手动 read |
| 技术参考 | memory/reference/*.md | memory_search 或手动 read |
| 工具配置 | TOOLS.md | 自动注入系统提示 |
| 行为规则 | AGENTS.md | 自动注入系统提示 |

---

## 附录 A：关键发现总结

1. **antigravity proxy 不支持 embeddings** — 这排除了最方便的远程方案，但本地 GGUF 是完全可行的替代
2. **node-llama-cpp 已预安装** — `@node-llama-cpp/linux-x64@3.15.1` 已存在，可能只需要下载 GGUF 模型
3. **Bootstrap 文件列表是硬编码的** — 不能通过配置添加额外的注入文件，但可以通过 hook 实现
4. **QMD 是唯一能索引 memory/ 以外路径的方案**（通过 `qmd.paths`），内置方案只支持 `extraPaths` 添加额外 Markdown 路径
5. **Session memory search 是实验性的** — 但对于跨 session 回忆对话内容非常有用
6. **Memory flush 默认未启用** — 但配置简单，应该立即启用
7. **Hybrid search（BM25 + vector）** — 默认关闭但建议启用，对精确匹配（ID、代码符号）很有帮助

## 附录 B：验证步骤

启用后，用以下命令验证：

```bash
# 检查内存状态
openclaw memory status --deep

# 深度检查 + 索引
openclaw memory status --deep --index --verbose

# 测试搜索
openclaw memory search "Lark bot"

# 检查上下文大小
# 在聊天中发送: /context list
```

## 附录 C：参考文档路径

- 内存概念: `/home/ubuntu/.npm-global/lib/node_modules/openclaw/docs/concepts/memory.md`
- 上下文: `/home/ubuntu/.npm-global/lib/node_modules/openclaw/docs/concepts/context.md`
- 工作空间: `/home/ubuntu/.npm-global/lib/node_modules/openclaw/docs/concepts/agent-workspace.md`
- Session: `/home/ubuntu/.npm-global/lib/node_modules/openclaw/docs/concepts/session.md`
- 压缩: `/home/ubuntu/.npm-global/lib/node_modules/openclaw/docs/concepts/compaction.md`
- 系统提示: `/home/ubuntu/.npm-global/lib/node_modules/openclaw/docs/concepts/system-prompt.md`
- Hooks: `/home/ubuntu/.npm-global/lib/node_modules/openclaw/docs/hooks.md`
- CLI Memory: `/home/ubuntu/.npm-global/lib/node_modules/openclaw/docs/cli/memory.md`
- 配置参考: `/home/ubuntu/.npm-global/lib/node_modules/openclaw/docs/gateway/configuration.md`
