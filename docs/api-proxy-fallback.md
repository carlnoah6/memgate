# API 代理层 Fallback — 到限额自动切换

> 状态：✅ 已完成并上线（2026-02-10）
> 项目：🔧 OpenClaw 优化

## 问题

OpenClaw 内置 fallback 机制有严重问题：
- **切换慢**：额度用完后反复聊天仍用旧模型
- **状态不稳定**：成功切到备用模型后又会自动切回去

## 架构

```
OpenClaw → api-proxy (8180) → Antigravity (8080) → Claude/Gemini API
```

- Antigravity 是 Google Cloud Code 代理，用 OAuth 登录 Google 账户
- Carl 订阅了 Google Ultra，额度每 5 小时刷新一次
- Claude 和 Gemini 是**独立额度池**（可互为 fallback）
- Antigravity `/health` 接口暴露每个模型的实时剩余额度（`remainingFraction`）和刷新时间

## 方案：主动感知额度 + 自动切换

### 核心逻辑

```python
# 1. 后台每 30s 轮询 /health，缓存各模型额度
health_cache = poll_health()  # {model: {remaining: 0.8, resetTime: ...}}

# 2. 请求进来时，主动选择有额度的模型
def pick_model(requested_model):
    chain = FALLBACK_CHAINS.get(requested_model, [requested_model])
    for model in chain:
        if health_cache[model]["remaining"] > 0.05:  # >5% 额度
            return model
    return chain[-1]  # 都没额度就用最后一个赌一把

# 3. 替换 model 字段，透明转发
```

### Fallback 链配置

```json
{
  "fallback_chains": {
    "claude-opus-4-6-thinking": [
      "claude-opus-4-6-thinking",
      "gemini-3-pro-high",
      "claude-sonnet-4-5-thinking"
    ],
    "gemini-3-pro-high": [
      "gemini-3-pro-high",
      "claude-opus-4-6-thinking",
      "gemini-3-pro-low"
    ]
  },
  "health_poll_interval_seconds": 30,
  "min_remaining_fraction": 0.05
}
```

### 关键优势
- **零失败请求**：主动感知额度，不等 429
- **对 OpenClaw 透明**：proxy 层处理，OpenClaw 无需改动
- **跨模型 fallback**：Claude 到限额自动切 Gemini，反之亦然
- **额度独立**：Claude 和 Gemini 分别刷新，天然互补

### 代码位置
- `/home/ubuntu/api-proxy/server.py`（现有 409 行，需增加约 80 行）

## 实现计划
- [x] 添加 `/health` 轮询 + 额度缓存 ✅
- [x] 实现 fallback chain 查询逻辑 ✅
- [x] 请求拦截：替换 model 字段 ✅
- [x] Anthropic ↔ OpenAI 格式转换（Kimi 支持）✅
- [x] 日志：记录每次 fallback 切换 ✅
- [x] 测试：格式转换 + 端到端 + 模拟额度耗尽 ✅
- [x] 上线 ✅ 2026-02-10
- [x] Token 用量按模型统计 ✅（日报 + Lark 表格）
