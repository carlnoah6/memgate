# Balatro AI 方案研究报告：Coder 全家桶（路线 A）

> 研究日期：2026-02-08
> 研究员：Luna Research Subagent

---

## 目录

1. [方案概述](#方案概述)
2. [架构图](#架构图)
3. [组件详解](#组件详解)
   - [BalatroBot（游戏 Mod）](#1-balatrobot游戏-mod)
   - [BalatroLLM（LLM 驱动的 Bot）](#2-balatrollmllm-驱动的-bot)
   - [BalatroBench（排行榜）](#3-balatrobench排行榜)
4. [完整部署步骤](#完整部署步骤)
5. [接入自定义 API 代理](#接入自定义-api-代理)
6. [各 LLM 效果对比](#各-llm-效果对比)
7. [Token 消耗估算](#token-消耗估算)
8. [推荐配置](#推荐配置)
9. [已知限制和风险](#已知限制和风险)
10. [常见问题与排坑](#常见问题与排坑)

---

## 方案概述

Coder 公司开发了一整套用 LLM 自动玩 Balatro 的工具链，由三个项目组成：

| 项目 | 功能 | 仓库 |
|------|------|------|
| **BalatroBot** | Balatro 游戏 Mod，暴露 JSON-RPC 2.0 HTTP API | [coder/balatrobot](https://github.com/coder/balatrobot) |
| **BalatroLLM** | 连接 LLM 和 BalatroBot API 的 Bot 客户端 | [coder/balatrollm](https://github.com/coder/balatrollm) |
| **BalatroBench** | 排行榜网站，对比各 LLM 玩 Balatro 的效果 | [coder/balatrobench](https://github.com/coder/balatrobench) |

核心思路：
- BalatroBot 作为 Mod 注入 Balatro 游戏，将游戏状态通过 HTTP API 暴露出来
- BalatroLLM 读取游戏状态 → 构建 prompt → 发给 LLM → 将 LLM 的 tool call 转为游戏操作
- 整个决策链路：**游戏状态 → Jinja2 模板渲染 → LLM 推理 → Function Calling → JSON-RPC 操作**

这是一个 fork 项目，原始版本来自 [besteon/balatrobot](https://github.com/besteon/balatrobot)，Coder 做了大量改进。

---

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Balatro Game (Steam)                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Lovely Injector → Steamodded → BalatroBot Mod (Lua)  │  │
│  │                                                        │  │
│  │  暴露 JSON-RPC 2.0 API (HTTP POST)                     │  │
│  │  端口: 127.0.0.1:12346                                 │  │
│  └──────────────────────┬─────────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────┘
                          │ HTTP (JSON-RPC 2.0)
                          │
┌─────────────────────────┼───────────────────────────────────┐
│                   BalatroLLM (Python)                         │
│  ┌──────────────────────┴──────────────────────────────┐    │
│  │  Bot Loop (bot.py)                                   │    │
│  │  1. 调用 gamestate 获取状态                           │    │
│  │  2. Jinja2 渲染 STRATEGY + GAMESTATE + MEMORY        │    │
│  │  3. 加载 TOOLS.json（可用操作）                        │    │
│  │  4. 发送给 LLM API                                   │    │
│  │  5. 解析 LLM 的 tool call 响应                        │    │
│  │  6. 转为 JSON-RPC 调用 BalatroBot                     │    │
│  │  7. 循环直到 GAME_OVER                                │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────┴──────────────────────────────┐    │
│  │  Strategy Templates (Jinja2)                         │    │
│  │  ├── STRATEGY.md.jinja  (策略哲学/方法论)             │    │
│  │  ├── GAMESTATE.md.jinja (游戏状态格式化)              │    │
│  │  ├── MEMORY.md.jinja    (历史动作记忆)                │    │
│  │  └── TOOLS.json         (可用函数定义)                │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS (OpenAI-compatible API)
                          │
┌─────────────────────────┼───────────────────────────────────┐
│              LLM API Provider                                │
│  ┌──────────────────────┴──────────────────────────────┐    │
│  │  OpenAI / Anthropic / Google / OpenRouter            │    │
│  │  或自定义 OpenAI 兼容代理                             │    │
│  │  (如 https://anz-luna.grolar-wage.ts.net/api)        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 组件详解

### 1. BalatroBot（游戏 Mod）

**GitHub**: https://github.com/coder/balatrobot
**文档**: https://coder.github.io/balatrobot/

#### 依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| **Balatro** | v1.0.1+ | 游戏本体（Steam 购买） |
| **Lovely Injector** | v0.8.0+ | Lua 代码注入器 |
| **Steamodded (smods)** | v1.0.0-beta-1221a+ | Balatro Mod 加载器 |
| **uv** | v0.9.21+ | Python 包管理器（CLI 工具） |

#### 安装结构

```
Mods/
├── smods/                # Mod 加载器
├── DebugPlus/            # 调试用（可选）
└── balatrobot/           # BalatroBot 目录
    ├── balatrobot.json   # 清单文件
    ├── balatrobot.lua    # 入口文件
    └── src/lua           # API 源码
```

#### Mods 目录位置

| 平台 | 路径 |
|------|------|
| Windows | `%AppData%/Balatro/Mods/balatrobot/` |
| macOS | `~/Library/Application Support/Balatro/Mods/balatrobot/` |
| Linux (Steam/Proton) | `~/.local/share/Steam/steamapps/compatdata/2379780/pfx/drive_c/users/steamuser/AppData/Roaming/Balatro/Mods/` |
| Linux (Native) | `~/.config/love/Mods/balatrobot/` |

> ⚠️ **注意**：Steam/Proton 启动器目前不支持，见 [issue #128](https://github.com/coder/balatrobot/issues/128)

#### API 端点列表

协议：JSON-RPC 2.0 over HTTP/1.1，默认端口 `12346`

| 方法 | 功能 | 所需游戏状态 |
|------|------|------------|
| `health` | 健康检查 | 任意 |
| `gamestate` | 获取完整游戏状态 | 任意 |
| `rpc.discover` | 获取 OpenRPC 规范 | 任意 |
| `start` | 开始新游戏 | MENU |
| `menu` | 返回主菜单 | 任意 |
| `save` | 保存进度 | 游戏中 |
| `load` | 读取存档 | 任意 |
| `select` | 选择当前 blind | BLIND_SELECT |
| `skip` | 跳过 blind（仅 Small/Big） | BLIND_SELECT |
| `buy` | 商店购买 | SHOP |
| `pack` | 选择/跳过补给包卡牌 | SMODS_BOOSTER_OPENED |
| `sell` | 卖出 joker/消耗品 | SHOP/SELECTING_HAND |
| `reroll` | 刷新商店 | SHOP |
| `cash_out` | 结算回合奖励 | ROUND_EVAL |
| `next_round` | 离开商店进入下一轮 | SHOP |
| `play` | 打出手牌 | SELECTING_HAND |
| `discard` | 弃牌 | SELECTING_HAND |
| `rearrange` | 重排手牌/joker/消耗品 | SELECTING_HAND/SHOP |
| `use` | 使用消耗品 | SELECTING_HAND |
| `add` | 添加卡牌（调试用） | 视类型而定 |
| `screenshot` | 截图 | 任意 |
| `set` | 设置游戏值（调试用） | 游戏中 |

#### 游戏状态暴露的数据

`gamestate` 返回完整的游戏状态 JSON，包括：

- **基本信息**: 状态 (state)、轮次 (round_num)、ante (ante_num)、金钱 (money)、牌组 (deck)、赌注 (stake)、种子 (seed)、是否胜利 (won)
- **手牌信息**: 每张牌的花色、点数、增强、印章、版本、是否 debuff
- **Joker 卡**: 完整 joker 列表及效果
- **消耗品**: 塔罗牌、星球牌、幽灵牌
- **Blind 信息**: 类型、状态、名称、效果、目标分数、标签
- **商店内容**: 可购买的卡牌、优惠券、补给包
- **牌型信息**: 所有牌型的等级、chips、mult
- **已使用优惠券**: used_vouchers
- **回合信息**: 剩余出牌次数、弃牌次数、已打分数

#### CLI 启动选项

```bash
# 启动 Balatro（带 Mod）
uvx balatrobot serve [OPTIONS]

# 调用 API
uvx balatrobot api METHOD [PARAMS]
```

关键选项：
| 选项 | 默认 | 说明 |
|------|------|------|
| `--fast` | 关 | 10 倍游戏速度 |
| `--headless` | 关 | 无头模式（最小渲染） |
| `--render-on-api` | 关 | 仅在 API 调用时渲染 |
| `--port` | 12346 | 服务端口 |
| `--no-shaders` | 关 | 禁用着色器（解决崩溃） |
| `--gamespeed` | 4 | 游戏速度倍率 |

---

### 2. BalatroLLM（LLM 驱动的 Bot）

**GitHub**: https://github.com/coder/balatrollm
**文档**: https://coder.github.io/balatrollm/

#### 支持的 LLM

**要求**：必须支持 **Tool Use / Function Calling**

已知兼容的模型（通过 OpenAI 兼容 API）：
- **OpenAI**: GPT-4o, GPT-4o-mini, GPT-5, gpt-oss-120b
- **Anthropic**: Claude 3.5 Sonnet, Claude Opus 系列
- **Google**: Gemini 系列
- **X-AI**: Grok 系列
- **DeepSeek**: DeepSeek 系列
- **Mistral AI**: Mistral 系列
- **Qwen**: Qwen 系列
- **MiniMax**, **Moonshot AI** 等

> 根据 BalatroBench 网站的颜色映射和 vendor 支持，以上厂商的模型都有被测试

#### 自定义 API Endpoint 配置

**方法 1：环境变量**

```bash
export BALATROLLM_BASE_URL="https://anz-luna.grolar-wage.ts.net/api"
export BALATROLLM_API_KEY="你的API密钥"
```

**方法 2：YAML 配置文件**

```yaml
# config/custom.yaml
model:
  - openai/gpt-4o  # 模型标识符，格式取决于你的代理配置

model_config:
  temperature: 0.2
  max_tokens: 2048
  extra_body:
    reasoning:
      effort: medium

# 可选覆盖
# base_url: https://anz-luna.grolar-wage.ts.net/api
# api_key: 你的密钥
```

**方法 3：CLI 参数**

```bash
balatrollm --model openai/gpt-4o \
  --base-url "https://anz-luna.grolar-wage.ts.net/api" \
  --api-key "你的密钥"
```

**优先级**：CLI 参数 > YAML 配置 > 环境变量

#### 决策逻辑

Bot 的核心循环 (`bot.py`)：

1. 调用 `gamestate` 获取当前游戏状态
2. 根据游戏状态，用 Jinja2 模板渲染三个 prompt 文件：
   - **STRATEGY.md** — 策略哲学（角色设定、决策优先级）
   - **GAMESTATE.md** — 当前游戏状态的结构化表示
   - **MEMORY.md** — 最近 10 次操作历史 + 错误信息
3. 加载 **TOOLS.json** — 当前游戏阶段可用的函数定义
4. 发送 Chat Completions 请求（带 tools）
5. 解析 LLM 返回的 tool call
6. 转为 JSON-RPC 调用 BalatroBot API
7. 处理特殊状态：
   - `BLIND_SELECT` → 自动 `select`（不跳过，因为 Tag 不支持）
   - `ROUND_EVAL` → 自动 `cash_out`
8. 循环直到 `GAME_OVER`

#### Prompt 策略

默认策略（`default`）是一种 **保守、注重经济** 的打法：

- **STRATEGY.md.jinja**：给 LLM 设定"专家 Balatro 玩家"的角色，定义决策优先级
- **GAMESTATE.md.jinja**：将游戏状态格式化为 LLM 易于理解的格式（金钱、手牌、joker、blind 目标等）
- **MEMORY.md.jinja**：展示最近 10 次操作（方法、参数、reasoning），以及错误信息
- **TOOLS.json**：按游戏阶段定义可用工具：
  - `SELECTING_HAND`: play, discard, rearrange, sell, use
  - `SHOP`: buy, reroll, next_round, sell, use, rearrange
  - `BLIND_SELECT`: select, skip（目前不使用 skip）
  - `SMODS_BOOSTER_OPENED`: pack

你可以创建自定义策略（在 `src/balatrollm/strategies/` 下新建目录），实现不同的打法风格。

#### 运行输出

每次运行会在 `./runs/` 目录生成详细的 artifacts：

```
runs/
  latest.json
  vX.Y.Z/<strategy>/<vendor>/<model>/<timestamp>_<deck>_<stake>_<seed>/
    task.json          # 任务配置
    strategy.json      # 策略清单
    run.log            # 运行日志
    requests.jsonl     # LLM 请求记录
    responses.jsonl    # LLM 响应记录
    gamestates.jsonl   # 游戏状态快照
    stats.json         # 汇总统计
    screenshots/       # 截图
```

#### 并行运行

```bash
# 3 个种子、2 个并行实例 = 3 个任务由 2 个 worker 处理
balatrollm --model openai/gpt-4o --parallel 2 --seed AAAAAAA BBBBBBB CCCCCCC
```

每个 worker 占用一个端口（12346, 12347, ...），自动启动/停止 Balatro 实例。

---

### 3. BalatroBench（排行榜）

**网站**: https://balatrobench.com
**GitHub**: https://github.com/coder/balatrobench
**数据集**: https://www.kaggle.com/datasets/s1m0n38/balatrobench

#### 测量指标

排行榜跟踪以下维度：

| 指标 | 说明 |
|------|------|
| **Round** | 平均最终轮次（±标准差） |
| **Valid Tool Calls** ✅ | 有效且可执行的 tool call 比例 |
| **Invalid State Calls** ⚠️ | 有效但当前状态不可执行的 tool call 比例 |
| **Failed Calls** ❌ | 无效 tool call 比例 |
| **Input Tokens (per call)** | 每次 tool call 的平均输入 token（±标准差） |
| **Output Tokens (per call)** | 每次 tool call 的平均输出 token（含推理 token，±标准差） |
| **Time (per call)** | 每次 tool call 的平均耗时（秒，±标准差） |
| **Cost (per call)** | 每次 tool call 的平均成本（毫美元，±标准差） |

#### 已测试的 Vendor

根据代码分析，BalatroBench 已测试来自以下厂商的模型：
- **OpenAI** (GPT 系列)
- **Google** (Gemini 系列)
- **Anthropic** (Claude 系列)
- **X-AI** (Grok 系列)
- **DeepSeek**
- **Mistral AI**
- **Qwen**
- **Z-AI**
- **MiniMax**
- **Moonshot AI**

#### 排行榜数据说明

> ⚠️ **无法直接获取实时排行榜数据**：BalatroBench 是一个 SPA（单页应用），数据从 BunnyCDN 动态加载。在没有浏览器自动化的环境下无法提取具体数值。建议直接访问 https://balatrobench.com 查看最新排名。

**已知信息**：
- 默认配置为 RED deck + WHITE stake（最简单的组合）
- 排行榜按平均到达的 **Round** 排序
- Balatro 有 8 个 ante，每个 ante 3 个 blind，理论上共 24 轮（打完即为胜利）
- 大多数 LLM 目前 **无法通关**，平均到达轮次在 3-12 轮之间（根据项目描述推测）
- Tool call 可靠性差异很大 — 这是区分模型好坏的关键指标

**已知趋势**（基于 vendor 列表和项目文档）：
- 前沿推理模型（GPT-4o 级别及以上）表现明显优于小型模型
- Claude 和 GPT 系列是主要竞争者
- Tool call 可靠性（成功率）和策略质量是决定胜负的两大因素

---

## 完整部署步骤

### 前提条件

- ✅ Steam 上已安装 Balatro (v1.0.1+)
- ✅ Windows / macOS / Linux 系统
- ✅ LLM API 密钥

### 步骤 1：安装 uv（Python 包管理器）

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 步骤 2：安装 Lovely Injector

1. 去 https://github.com/ethangreen-dev/lovely-injector 下载最新 release
2. 按平台放置文件：
   - **Windows**: 将 `version.dll` 放入 Balatro 游戏目录（如 `C:\Program Files (x86)\Steam\steamapps\common\Balatro\`）
   - **macOS**: 将 `liblovely.dylib` 放入 Balatro 游戏目录
   - **Linux Native**: 将 `liblovely.so` 放到 `/usr/local/lib/`

### 步骤 3：安装 Steamodded

1. 去 https://github.com/Steamodded/smods/wiki 按指南安装
2. 确保 `smods` 文件夹在 Mods 目录中

### 步骤 4：安装 BalatroBot Mod

```bash
# 下载最新 release
# 从 https://github.com/coder/balatrobot/releases 下载

# 将以下文件复制到 Mods 目录
# Mods/balatrobot/
#   ├── balatrobot.json
#   ├── balatrobot.lua
#   └── src/lua/
```

### 步骤 5：验证 BalatroBot

```bash
# 启动 Balatro（快速模式）
uvx balatrobot serve --fast

# 另一个终端验证
curl -X POST http://127.0.0.1:12346 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "health", "id": 1}'

# 预期响应
# {"jsonrpc":"2.0","result":{"status":"ok"},"id":1}
```

### 步骤 6：安装 BalatroLLM

```bash
# 克隆仓库
git clone --depth 1 https://github.com/coder/balatrollm.git
cd balatrollm

# 安装依赖
uv sync --no-dev

# 激活虚拟环境
source .venv/bin/activate

# 验证
balatrollm --help
```

### 步骤 7：配置并运行

```bash
# 设置环境变量
export BALATROLLM_BASE_URL="https://anz-luna.grolar-wage.ts.net/api"
export BALATROLLM_API_KEY="你的密钥"

# 运行！
balatrollm --model openai/gpt-4o --seed AAAAAAA

# 或使用配置文件
balatrollm config/example.yaml
```

---

## 接入自定义 API 代理

我们有自己的 OpenAI 兼容代理 `https://anz-luna.grolar-wage.ts.net/api`。

### 配置方式

**创建 `.envrc` 文件**：

```bash
# 在 balatrollm 目录中
export BALATROLLM_BASE_URL="https://anz-luna.grolar-wage.ts.net/api"
export BALATROLLM_API_KEY="你的API密钥"
export BALATROLLM_MODEL="openai/gpt-4o"  # 根据代理支持的模型修改
```

**或创建 YAML 配置文件**：

```yaml
# config/luna.yaml
parallel: 1

seed:
  - AAAAAAA

deck:
  - RED

stake:
  - WHITE

strategy:
  - default

model:
  - openai/gpt-4o  # 视代理路由规则调整

model_config:
  temperature: 0.2
  max_tokens: 2048
  extra_body:
    reasoning:
      effort: medium
```

### 注意事项

1. **模型标识符格式**：取决于你的代理如何路由。如果代理使用 OpenRouter 风格的 `vendor/model` 格式，保持不变；如果直接转发到 OpenAI，用 `gpt-4o` 即可
2. **Tool Use 支持**：确保代理透传 `tools` 和 `tool_choice` 参数
3. **Streaming**：BalatroLLM 可能使用非 streaming 模式，确保代理支持
4. **extra_body 透传**：如果代理不支持 `extra_body` 中的字段（如 `reasoning`），可能需要移除

---

## 各 LLM 效果对比

> ⚠️ 以下为基于项目文档、代码分析和社区信息的推测。具体数据请访问 https://balatrobench.com 查看实时排行榜。

### 预期表现等级

| 等级 | 模型 | 预计轮次 | 备注 |
|------|------|----------|------|
| 🥇 S 级 | GPT-5, Claude Opus 4.x | 8-12+ 轮 | 前沿推理模型，策略能力强 |
| 🥈 A 级 | GPT-4o, Claude 3.5 Sonnet | 6-10 轮 | 可靠的 tool call + 不错的策略 |
| 🥉 B 级 | Gemini 2.x Pro, Grok | 5-8 轮 | 有一定策略能力 |
| C 级 | GPT-4o-mini, 小型模型 | 3-5 轮 | tool call 可靠性差，策略简单 |
| D 级 | 不支持 tool use 的模型 | 不可用 | 无法运行 |

### 关键差异因素

1. **Tool Call 可靠性**：这是最重要的。失败的 tool call 会浪费回合和金钱
2. **策略理解深度**：理解 joker 协同效应、经济管理、牌型升级
3. **推理能力**：计算分数、评估风险
4. **上下文窗口**：游戏后期状态会变大

---

## Token 消耗估算

### 单次 Tool Call

基于架构分析：

| 组件 | 估算 Token 数 |
|------|-------------|
| STRATEGY.md（系统 prompt） | ~800-1500 tokens |
| GAMESTATE.md（游戏状态） | ~1000-3000 tokens（随游戏进展增长） |
| MEMORY.md（最近 10 步） | ~500-1500 tokens |
| TOOLS.json（函数定义） | ~300-800 tokens |
| **总输入** | **~2500-7000 tokens/call** |
| **输出**（含推理） | **~200-2000 tokens/call** |

### 一局完整游戏

Balatro 一局游戏的 tool call 次数取决于到达的轮次：

| 轮次 | 估算 Tool Calls | 估算总 Token |
|------|----------------|-------------|
| 3 轮（早期失败） | ~30-50 次 | ~150K-350K |
| 6 轮（中等表现） | ~80-120 次 | ~400K-840K |
| 10 轮（较好表现） | ~150-200 次 | ~750K-1.4M |
| 24 轮（通关） | ~350-500 次 | ~1.7M-3.5M |

### 估算成本（以 GPT-4o 定价为例）

| 场景 | 输入 Token | 输出 Token | 估算成本 |
|------|-----------|-----------|---------|
| 短局（~3 轮） | ~200K | ~30K | ~$0.50-1.00 |
| 中局（~6 轮） | ~500K | ~80K | ~$1.50-3.00 |
| 长局（~10 轮） | ~1M | ~150K | ~$3.00-6.00 |
| 通关（~24 轮） | ~2.5M | ~350K | ~$7.00-15.00 |

> 💡 通过我们的自定义代理可能可以降低成本，具体取决于代理的定价策略。
> 💡 BalatroBench 排行榜显示每次 tool call 的成本（毫美元），可以精确比较。

---

## 推荐配置

### 🏆 最佳性价比配置

```yaml
# config/recommended.yaml
parallel: 1
seed:
  - AAAAAAA
deck:
  - RED
stake:
  - WHITE
strategy:
  - default
model:
  - openai/gpt-4o  # 或等价模型
model_config:
  temperature: 0.2
  max_tokens: 2048
```

```bash
# 环境变量
export BALATROLLM_BASE_URL="https://anz-luna.grolar-wage.ts.net/api"
export BALATROLLM_API_KEY="你的密钥"

# BalatroBot 配置（提高效率）
export BALATROBOT_FAST=1
export BALATROBOT_HEADLESS=1  # 或用 BALATROBOT_RENDER_ON_API=1 看游戏画面
```

### 🎮 观赏体验配置（想看 AI 玩）

```bash
export BALATROBOT_FAST=1      # 加速但保留画面
export BALATROBOT_AUDIO=0     # 关闭声音
export BALATROBOT_HEADLESS=0  # 保留渲染

balatrollm --model openai/gpt-4o --views  # 启用 Web 视图
# 访问 http://localhost:12345/views/task.html 观看
```

### ⚡ 最快执行配置（批量跑分）

```yaml
parallel: 2  # 根据你的 LLM API 速率限制调整
seed:
  - AAAAAAA
  - BBBBBBB
  - CCCCCCC
deck:
  - RED
stake:
  - WHITE
model:
  - openai/gpt-4o
```

```bash
export BALATROBOT_HEADLESS=1
export BALATROBOT_FAST=1
export BALATROBOT_NO_SHADERS=1
```

---

## 已知限制和风险

### 功能限制

1. **不支持跳过 Blind**：当前 bot 总是选择打 blind（`select`），不会跳过。因为 Tag 系统在 BalatroBot 中尚未完全支持
2. **BLIND_SELECT 和 ROUND_EVAL 不由 LLM 决策**：这两个阶段是硬编码的（总是 select，总是 cash_out）
3. **Steam/Proton 不完全支持**：Linux 上 Steam/Proton 启动器有已知问题 ([#128](https://github.com/coder/balatrobot/issues/128))
4. **macOS Steam 启动问题**：macOS 不能通过 Steam 直接启动，CLI 会绕过直接执行 LOVE 运行时
5. **单一默认策略**：目前只有一个 `default` 策略。可以自定义，但需要 Jinja2 + Balatro 专业知识

### LLM 风险

1. **Token 消耗不可预测**：带推理的模型（如 o1、Opus 思考版）会产生大量输出 token
2. **Tool Call 失败**：LLM 可能生成无效的函数调用，导致浪费 token 和游戏回合
3. **API 速率限制**：并行运行时可能触发 API provider 的速率限制
4. **成本累积**：一局游戏可能消耗 $1-15+，批量跑分成本快速增长

### 技术风险

1. **游戏版本兼容性**：Balatro 更新可能破坏 Mod
2. **Lovely Injector 兼容性**：注入器更新可能与 Steamodded 不兼容
3. **端口冲突**：并行运行时需要多个端口
4. **游戏崩溃**：着色器问题可能导致崩溃（用 `--no-shaders` 缓解）

### 安全注意

1. **API 密钥暴露**：`.envrc` 文件包含敏感信息，已在 `.gitignore` 中，但注意不要泄露
2. **Tailscale 代理安全**：通过 Tailscale 代理时，确保只有授权节点可以访问

---

## 常见问题与排坑

### Q: 连接被拒绝 (Connection refused)

确保 Balatro 已启动且 Mod 加载成功。检查 `logs/{timestamp}/{port}.log`。

### Q: Mod 加载失败

1. 确认 Lovely Injector 版本 ≥ 0.8.0
2. 确认 Steamodded 版本 ≥ 1.0.0-beta-1221a
3. 确认文件结构正确

### Q: 端口占用

```bash
uvx balatrobot serve --port 8080  # 换个端口
```

### Q: 游戏崩溃

```bash
uvx balatrobot serve --no-shaders --headless --fast
```

### Q: LLM 不停返回无效 tool call

- 换用更强的模型（GPT-4o 级别及以上）
- 检查你的 API 代理是否正确透传 `tools` 参数
- 确认模型确实支持 function calling

### Q: 如何查看 AI 的思考过程？

- 运行日志在 `runs/` 目录的 `responses.jsonl` 中
- 启用 `--views` 可以在浏览器中实时查看
- BalatroBench.com 可以逐步回放每次 tool call

---

## 参考链接

- BalatroBot 文档: https://coder.github.io/balatrobot/
- BalatroLLM 文档: https://coder.github.io/balatrollm/
- BalatroBench 排行榜: https://balatrobench.com
- BalatroBench 数据集: https://www.kaggle.com/datasets/s1m0n38/balatrobench
- Discord 社区: https://discord.gg/TPn6FYgGPv
- Twitch 直播: https://www.twitch.tv/S1M0N38
