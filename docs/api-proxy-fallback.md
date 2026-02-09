# API 代理层 Fallback — 到限额自动切换

> 状态：待实现
> 项目：🔧 OpenClaw 优化
> 记录日期：2026-02-09

## 问题

OpenClaw 内置 fallback 机制有严重问题：
- **切换慢**：额度用完后反复聊天仍用旧模型
- **状态不稳定**：成功切到备用模型后又会自动切回去

## 方案

在 api-proxy 层实现 fallback，对 OpenClaw 完全透明：

```
用户请求 → api-proxy → 主 endpoint
                ↓ (429/额度用尽)
           备用 endpoint → 重试
```

### 实现要点
1. 代理收到 429/额度用尽错误 → 自动切备用 key/endpoint → 重试
2. 维护一个 endpoint 优先级列表，按健康状态动态排序
3. 对 OpenClaw 完全透明，无需感知切换
4. 记录切换日志，供监控使用

### 代码位置
- `/home/ubuntu/api-proxy/server.py`

## 当前状态
- [ ] 设计方案
- [ ] 实现代码
- [ ] 测试
- [ ] 上线
