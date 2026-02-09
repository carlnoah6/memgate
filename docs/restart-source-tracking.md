# 重启来源追踪 & 回复路由

> 状态：待实现
> 项目：🔧 OpenClaw 优化
> 记录日期：2026-02-09

## 问题

重启可能从任何 session 触发（主 session、群聊 session 等），但重启后的汇报只回到主 session，触发重启的 session 不知道结果。

## 方案

### 1. 记录触发来源
`mark-restart.sh` 增加参数：
```bash
mark-restart.sh "重启原因" --source-session "session_key" --source-chat "chat_id"
```

标记文件增加字段：
```json
{
  "reason": "重启原因",
  "timestamp": "2026-02-10T08:00:00+08:00",
  "source_session": "agent:main:feishu:dm:xxx",
  "source_chat": "oc_453c88ec..."
}
```

### 2. 重启后路由
`check-restart.sh` 读取标记文件，返回来源信息：
- 如果来源是当前 session → 在当前 session 汇报
- 如果来源是其他 session → 通过 `lark-send-message.sh` 发到对应 chat_id

### 3. 统一流程
所有 session 都走统一的重启脚本，不只是主 session。

## 当前状态
- [ ] 设计方案
- [ ] 修改 mark-restart.sh
- [ ] 修改 check-restart.sh
- [ ] 测试多 session 场景
