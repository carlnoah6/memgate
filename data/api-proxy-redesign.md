# API Proxy 重构方案：多模型网关 + 用量追踪

> **日期**: 2026-02-12
> **目标**: 删除 fallback 机制和格式转换代码，将 API Proxy 简化为**多模型网关 + 用量追踪**

---

## 一、现有架构分析

### 1. fallback.json — Tier 结构与 Fallback 逻辑

**结构**：
```json
{
  "enabled": true,
  "health_poll_interval_seconds": 30,
  "min_remaining_fraction": 0.05,
  "tiers": [
    { "name": "Claude Opus 4.6", "model": "claude-opus-4-6-thinking", "type": "antigravity", "health_key": "..." },
    { "name": "Gemini 3 Pro High", "model": "gemini-3-pro-high", "type": "antigravity", "health_key": "..." },
    { "name": "Gemini 3 Pro Image", "model": "gemini-3-pro-image", "type": "antigravity", "health_key": "..." },
    { "name": "GLM-4 Plus", "model": "glm-4-plus", "type": "external", "base_url": "...", "format": "openai" },
    { "name": "GLM-5", "model": "glm-5", "type": "external", "base_url": "...", "format": "openai" },
    { "name": "Kimi 8k", "model": "moonshot-v1-8k", "type": "external", "base_url": "...", "format": "openai" }
  ]
}
```

**Tier 类型**：
- `antigravity`/`upstream`：通过统一 upstream（`http://localhost:8080`）转发的模型，有 `/health` 健康检查
- `external`：直接调用外部 API 的模型（GLM、Kimi），自带 `base_url` 和 `format`

**Fallback 逻辑（`src/fallback.py`）**：
1. **HealthCache** — 定期（30s）轮询 upstream `/health`，缓存各模型的 `remainingFraction` 配额
2. **Proactive Fallback（`pick_tier`）** — 请求前检查：如果目标模型配额 < 5%，按 tier 顺序找下一个可用模型
3. **Reactive Fallback（`_try_reactive_fallback`）** — 请求后检查：upstream 返回 429/503 或配额相关错误时，遍历 tier 列表找替代

### 2. proxy.py — 格式转换代码（OpenAI ↔ Anthropic）

**三个核心函数**：

| 函数 | 用途 | 行数 |
|------|------|------|
| `anthropic_to_openai(body)` | Anthropic Messages 请求体 → OpenAI Chat Completions 请求体 | ~50行 |
| `openai_to_anthropic(resp_data)` | OpenAI 非流式响应 → Anthropic Messages 响应 | ~45行 |
| `openai_stream_to_anthropic_stream()` | OpenAI SSE 流 → Anthropic SSE 流（异步生成器） | ~80行 |

**转换细节**：
- 请求：Anthropic 的 `system`（str/list）→ OpenAI 的 `messages[0].role=system`；content block 数组 → 纯文本；参数映射（`max_tokens`、`stop_sequences→stop`）
- 响应：`choices[0].message.content` → `content[{type:"text"}]`；`reasoning_content` → `thinking` block；`finish_reason` → `stop_reason` 映射
- 流式：逐块转换 SSE 事件，包括 `message_start` / `content_block_start` / `content_block_delta` / `message_stop` 完整协议

### 3. app.py — 路由和代理逻辑

**路由表**：

| 方法 | 路径 | 功能 | 认证 |
|------|------|------|------|
| POST | `/v1/messages` | Anthropic Messages API 代理 | API Key |
| POST | `/v1/chat/completions` | OpenAI Chat Completions API 代理 | API Key |
| GET | `/v1/models` | 列出可用模型（有重复定义！） | API Key |
| ANY | `/v1/{path:path}` | Catch-all 透传到 upstream | API Key |
| POST | `/admin/keys` | 创建 API Key | Admin Key |
| GET | `/admin/keys` | 列出所有 Key | Admin Key |
| GET | `/admin/keys/{key}/usage` | 查看 Key 用量 | Admin Key |
| POST | `/admin/keys/{key}/disable` | 禁用 Key | Admin Key |
| POST | `/admin/keys/{key}/enable` | 启用 Key | Admin Key |
| DELETE | `/admin/keys/{key}` | 删除 Key | Admin Key |
| GET | `/admin/usage` | 总用量 | Admin Key |
| GET | `/admin/usage/daily` | 每日用量 | Admin Key |
| GET | `/admin/usage/hourly` | 每小时用量 | Admin Key |
| GET | `/admin/fallback` | Fallback 状态 | Admin Key |
| GET | `/health` | 健康检查 | 无 |

**核心流程（`_handle_request_logic`）**：
1. 解析请求体，提取 `model` 和 `stream` 标志
2. 识别 `client_format`（`"anthropic"` 或 `"openai"`）基于入口路由
3. **Proactive fallback**：调用 `pick_tier()` 检查配额，可能更换模型或跳转 external tier
4. 如果是 upstream tier：构建代理请求 → 转发到 `UPSTREAM` → 用量追踪
5. 如果是 external tier：调用 `call_external_tier()`，内含格式转换（Anthropic 客户端请求 → OpenAI external → 转回 Anthropic 响应）
6. **Reactive fallback**：upstream 失败时在 `_handle_stream` / `_handle_non_stream` 中触发

**关键依赖链**：
```
app.py → fallback.py（pick_tier, health_cache, load_fallback_config）
app.py → proxy.py（anthropic_to_openai, openai_to_anthropic, openai_stream_to_anthropic_stream）
app.py → usage.py（record_usage）
app.py → auth.py（require_api_key）
fallback.py → config.py（FALLBACK_CONFIG_FILE, UPSTREAM, GLM_API_KEY, KIMI_API_KEY）
```

### 4. 现有问题

1. **`/v1/models` 定义了两次** — 函数 `list_models` 和 `get_models`，FastAPI 只会用第一个
2. **格式转换有损** — `anthropic_to_openai` 会丢弃 `tool_use`、`tool_result`、`image` blocks
3. **Fallback 跨格式** — Anthropic 请求可能被 fallback 到 OpenAI 格式的 external tier，导致语义损失
4. **config.py 重复变量** — `GLM_API_KEY` 和 `KIMI_API_KEY` 各定义了两次
5. **单一 UPSTREAM** — 所有 antigravity 模型共享一个 upstream URL，不灵活

---

## 二、新架构设计

### 核心理念

**API Proxy = 多模型网关 + 用量追踪**

- 每个模型有自己的 upstream URL、API Key、原生格式
- 请求按 `model` 字段路由到对应后端，**不做任何格式转换**
- 客户端必须使用目标模型的原生格式

### 模型注册表

三个独立模型，各走原生格式：

| 模型 ID | 上游 URL | 格式 | API Key |
|---------|---------|------|---------|
| `claude-opus-4-6-thinking` | `https://anz-luna.grolar-wage.ts.net/api` | Anthropic Messages | `REDACTED_LUNA_KEY` |
| `deepseek-chat` | `https://api.deepseek.com/v1` | OpenAI Chat Completions | `REDACTED_DEEPSEEK_KEY` |
| `kimi-k2.5` | `https://api.moonshot.cn/v1` | OpenAI Chat Completions | `REDACTED_KIMI_KEY` |

### 新路由设计

| 方法 | 路径 | 功能 | 目标模型 |
|------|------|------|---------|
| POST | `/v1/messages` | Anthropic Messages 透传 | claude-opus-4-6-thinking |
| POST | `/v1/chat/completions` | OpenAI Chat Completions 透传 | deepseek-chat / kimi-k2.5（按 body.model） |
| GET | `/v1/models` | 返回全部 3 个可用模型 | — |
| — | `/admin/*` | 管理接口（不变） | — |
| GET | `/health` | 健康检查 | — |

### 路由逻辑

```
POST /v1/messages
  → 从 body 提取 model
  → 查 models_registry，确认是 anthropic 格式
  → 透传到 upstream（添加 upstream API Key）
  → 记录用量 → 返回原始响应

POST /v1/chat/completions
  → 从 body 提取 model
  → 查 models_registry，确认是 openai 格式
  → 透传到 upstream（添加 upstream API Key）
  → 记录用量 → 返回原始响应

GET /v1/models
  → 返回 models_registry 中所有模型的静态列表
```

### 新配置文件（替代 fallback.json）

**`models.json`**：
```json
{
  "models": [
    {
      "id": "claude-opus-4-6-thinking",
      "name": "Claude Opus 4.6 Thinking",
      "format": "anthropic",
      "base_url": "https://anz-luna.grolar-wage.ts.net/api",
      "api_key_env": "CLAUDE_API_KEY",
      "auth_header": "x-api-key",
      "chat_endpoint": "/v1/messages"
    },
    {
      "id": "deepseek-chat",
      "name": "DeepSeek Chat",
      "format": "openai",
      "base_url": "https://api.deepseek.com/v1",
      "api_key_env": "DEEPSEEK_API_KEY",
      "auth_header": "authorization_bearer",
      "chat_endpoint": "/chat/completions"
    },
    {
      "id": "kimi-k2.5",
      "name": "Kimi K2.5",
      "format": "openai",
      "base_url": "https://api.moonshot.cn/v1",
      "api_key_env": "KIMI_API_KEY",
      "auth_header": "authorization_bearer",
      "chat_endpoint": "/chat/completions"
    }
  ]
}
```

### `/v1/models` 响应示例

```json
{
  "object": "list",
  "data": [
    {
      "id": "claude-opus-4-6-thinking",
      "object": "model",
      "created": 1739347200,
      "owned_by": "anthropic",
      "format": "anthropic"
    },
    {
      "id": "deepseek-chat",
      "object": "model",
      "created": 1739347200,
      "owned_by": "deepseek",
      "format": "openai"
    },
    {
      "id": "kimi-k2.5",
      "object": "model",
      "created": 1739347200,
      "owned_by": "moonshot",
      "format": "openai"
    }
  ]
}
```

---

## 三、文件改动清单

### 🗑️ 删除的文件

| 文件 | 原因 |
|------|------|
| `src/fallback.py` | 整个 fallback 机制删除（HealthCache、pick_tier、load_fallback_config） |
| `src/proxy.py` | 整个格式转换代码删除（anthropic_to_openai、openai_to_anthropic、openai_stream_to_anthropic_stream） |
| `fallback.json` | fallback 配置不再需要 |
| `fallback.json.example` | 同上 |
| `tests/test_fallback.py` | 测试 fallback 逻辑的测试删除 |
| `tests/test_dual_format.py` | 测试双格式转换的测试删除 |

### ✏️ 需要重写的文件

#### `src/config.py`
- **删除**：`FALLBACK_CONFIG_FILE`、`GLM_API_KEY`、`KIMI_API_KEY`（及重复定义）、`UPSTREAM`
- **新增**：`MODELS_CONFIG_FILE` 指向 `models.json`
- **新增**：`CLAUDE_API_KEY`、`DEEPSEEK_API_KEY`、`KIMI_API_KEY` 环境变量
- **新增**：`load_models_config()` 函数，加载模型注册表

#### `src/app.py`（**大幅重写**）
- **删除所有 import**：`fallback`（health_cache, load_fallback_config, pick_tier）、`proxy`（所有格式转换函数）
- **删除**：`call_external_tier()` 函数（~60行）— 包含格式转换逻辑
- **删除**：`_try_reactive_fallback()` 函数（~50行）— reactive fallback
- **删除**：`_handle_request_logic()` 中的 proactive fallback 分支
- **删除**：`_handle_stream()` 中的 fallback 检测和触发逻辑
- **删除**：`_handle_non_stream()` 中的 fallback 检测和触发逻辑
- **删除**：`proxy_catchall` 路由（不再需要 upstream 透传）
- **删除**：重复的 `/v1/models` 路由定义
- **重写**：`lifespan()` — 不再创建单一 upstream client，改为按模型创建多个 httpx.AsyncClient
- **重写**：`POST /v1/messages` — 从 body 取 model → 查 registry → 直接透传到对应 upstream（Anthropic 格式）
- **重写**：`POST /v1/chat/completions` — 从 body 取 model → 查 registry → 直接透传到对应 upstream（OpenAI 格式）
- **重写**：`GET /v1/models` — 只返回 models.json 中定义的静态模型列表
- **保留**：Admin 路由不变
- **新增**：模型路由逻辑 — `_get_model_config(model_id)` 查模型注册表
- **新增**：通用透传函数 `_proxy_to_upstream(model_config, request, body, key_info, is_stream)` — 按模型 config 构建 upstream 请求

#### `src/admin.py`
- **删除**：`admin_fallback_status()` 函数（~30行）
- **删除**：`from .fallback import health_cache, load_fallback_config`
- **修改**：`/admin/fallback` 路由从 app.py 中移除
- **可选新增**：`/admin/models` 端点显示模型注册表和健康状态

#### `src/health.py`
- **删除**：`from .fallback import load_fallback_config`
- **重写**：返回简单健康状态 + 已注册模型列表（不再引用 fallback tier 数量）

#### `src/usage.py`
- **无改动**：用量追踪逻辑完全保留，与模型注册表解耦

#### `src/auth.py`
- **无改动**：认证层完全保留

### 📝 新增的文件

| 文件 | 功能 |
|------|------|
| `models.json` | 模型注册表配置（替代 fallback.json） |
| `src/router.py`（可选） | 模型路由逻辑，从 `models.json` 查找目标 upstream 并构建请求 |

### 🔧 可能需要改动的文件

| 文件 | 改动 |
|------|------|
| `docker-compose.yml` | 更新环境变量（新增 CLAUDE/DEEPSEEK/KIMI API Key），volume 挂载 models.json 替代 fallback.json |
| `.github/workflows/deploy.yml` | 如果部署脚本引用 fallback.json，需更新 |
| `tests/test_integration.py` | 更新集成测试，移除 fallback 相关测试 |
| `tests/test_server.py` | 更新服务器测试 |
| `README.md` | 更新架构说明、路由文档、配置说明 |

---

## 四、改动总结

| 类别 | 数量 | 细节 |
|------|------|------|
| 删除文件 | 6 | fallback.py, proxy.py, fallback.json, fallback.json.example, test_fallback.py, test_dual_format.py |
| 重写文件 | 3 | app.py（大幅）, config.py（中等）, health.py（小） |
| 修改文件 | 4 | admin.py, README.md, docker-compose.yml, 测试文件 |
| 新增文件 | 1-2 | models.json, 可选 router.py |
| 不变文件 | 2 | auth.py, usage.py |
| 删除代码量 | ~400行 | proxy.py 全部（~175行）+ fallback.py 全部（~120行）+ app.py 中 fallback 相关（~100行） |
| 新增代码量 | ~150行 | 通用透传逻辑 + 模型路由 + models.json 加载 |

**净效果：代码减少约 250 行，架构大幅简化。**
