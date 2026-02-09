# HEARTBEAT.md

心跳已启用（every: 5m），**用于驱动所有定时任务**。

## ⚠️ 为什么用心跳而不是 OpenClaw cron？
OpenClaw cron 有 bug（`every` 类型 job 永远不执行），在修复前不可用。
所以所有需要 LLM 的定时任务统一由心跳 + `sessions_spawn` 驱动。
**这是唯一方案，不要发明别的方式。**

## 每次心跳执行流程

0. **重启检测**（最高优先级）：运行 `bash scripts/check-restart.sh`
   - 如果输出包含 `just_restarted` → **立刻主动汇报**，不要回 HEARTBEAT_OK！
   - 汇报内容：「✅ 重启完成（pid XXX）。[说明重启原因]。[检查有无未完成任务并恢复]」
   - 检查方式：读取今天的 `memory/YYYY-MM-DD.md` 最后几行，看有没有未完成的任务
   - 汇报后继续执行下面的正常流程
   - 如果输出 `running_normally` → 跳过此步，继续正常流程
   - **重要**：每次重启前必须执行完整的重启流程（见下方「重启操作流程」）

## ⚠️ 重启操作流程（必须严格遵守）

### 重启前检查（必做）

执行重启脚本**之前**，必须先检查是否有其他 session 在工作：

```
sessions_list(activeMinutes=2, messageLimit=0)
```

- 如果只有当前 session → 可以直接重启
- 如果有**子任务 (subagent)** 正在运行 → **等待完成或通知 Carl 确认**后再重启
- 如果有**其他群聊 session** 活跃 → 可以重启（群聊消息会自动重新排队）
- **config.patch（SIGUSR1 热重载）不影响其他 session**，优先使用。仅改 node_modules 时才需要全进程重启

### 执行重启

**重启前必须先完成回复！** 不要在回复还在流式输出时就执行重启。正确流程：
1. 先告诉 Carl 「我要重启了，原因是 XXX，重启后会自动汇报」
2. 等当前回复完全输出（流式卡片关闭）
3. 然后执行重启脚本

```bash
bash scripts/restart-gateway.sh "重启原因"
```

脚本自动完成：
1. 写重启标记（`mark-restart.sh`）
2. 通过 `openclaw cron add --wake now` 创建 wake job（重启后 15 秒触发心跳）
3. 等待 5 秒（让流式卡片关闭）
4. 执行 `openclaw gateway restart`

**绝不要手动分步执行这些操作！** 用脚本才能保证 wakeMode 等参数正确。

**背景说明**：
- `openclaw gateway restart` 是全进程重启，不会自动发 GatewayRestart 消息
- `config.patch` 是 SIGUSR1 热重载，会自动发 GatewayRestart（但不能加载 node_modules 改动）
- cron job 持久化在磁盘，重启后自动加载 → `--wake now` 立即触发心跳 → check-restart.sh → 汇报
- **不能用 curl 调 wake API**（gateway 用 WebSocket JSON-RPC，不是 REST）

## ⚠️ OpenClaw 更新后必须检查 Patch

每次 OpenClaw 更新（`update.run` 或手动 `npm update`）后，**必须检查并重新应用所有 patch**：

```bash
# Feishu 流式卡片 patch
python3 patches/apply-feishu-streaming-fix.py

# Feishu 群聊 session key patch（From 用 chatId 而非 senderId）
python3 patches/fix-feishu-group-session-key.py

# 禁用误导性的队列通知（thinking model 下 3 秒超时太短导致误报）
python3 patches/disable-queue-notification.py

# 修复流式卡片泄露 NO_REPLY/HEARTBEAT_OK 文字
python3 patches/fix-streaming-silent-reply.py

# 修复流式卡片串台（onAgentEvent 全局广播 → 加 sessionKey 过滤）
python3 patches/fix-streaming-cross-session.py

# 全局 lane 并发从 1 改为 4（解决群聊等私聊排队问题）
python3 patches/fix-lane-concurrency.py

# 输出 "✅ Patch already applied." → 无需操作
# 输出 "🔧 Patch needed/applied" → 需要重启
```

如果 patch 应用后需要重启，用统一脚本：`bash scripts/restart-gateway.sh "重新应用 Feishu patch"`

1. 运行调度脚本：`python3 scripts/heartbeat-scheduler.py`
2. 脚本输出 JSON，`due` 数组列出到期任务名
3. 如果 `due` 为空 → 回复 HEARTBEAT_OK
4. 如果 `due` 不为空 → 按任务名 spawn 对应子任务（脚本已自动更新时间戳）
5. **不要自己判断是否到期！脚本说到期就到期，无条件 spawn。**

到期任务的 spawn 方式：
- `periodic` → 读取 `data/periodic-check-prompt.md` 完整内容作为 task，runTimeoutSeconds=240
- `research` → 从 `data/backlog.md` 取下一个未完成任务，runTimeoutSeconds=1800
- `dailyReport` → 读取 `data/daily-report-prompt.md` 完整内容作为 task，runTimeoutSeconds=300
- `morningGreeting` → 今日日程提醒（runTimeoutSeconds=120）
- `weeklyReview` → 读取 `data/weekly-review-prompt.md` 完整内容作为 task，runTimeoutSeconds=300

### 普通任务（runTimeoutSeconds=240）

| 任务 | key | 间隔 | 说明 |
|------|-----|------|------|
| 定期检查 | periodic | 5 分钟 | 邮件 + 日历 + TODO + 邮件→日历自动同步 + 文档评论检查 |

**定期检查的 spawn prompt**：读取 `data/periodic-check-prompt.md` 的完整内容作为 task。不要自己编 prompt。

### 研究任务（runTimeoutSeconds=1800）

| 任务 | key | 间隔 | 说明 |
|------|-----|------|------|
| 后台研究 | research | 5 分钟 | 从 backlog.md 取下一个未完成任务做研究 |

### 每日任务（按当前 SGT 时间判断，每天只跑一次）
| 任务 | key | 时间 | 说明 |
|------|-----|------|------|
| 每日日报 | dailyReport | 04:00 | 生成昨天日报 |
| 早安提醒 | morningGreeting | 07:00 | 今日日程提醒 |

### 每周任务（按当前 SGT 时间 + 星期判断，每周只跑一次）
| 任务 | key | 时间 | 说明 |
|------|-----|------|------|
| 周日计划 Review | weeklyReview | 周日 10:00 | 下周日程 review + 约人确认 |

### 深夜规则（23:00-07:00 SGT）
- 跳过定期检查和评论检查
- 后台研究继续跑

## ⚠️ 文档评论处理规则（必须遵守）

评论是用户的反馈或指令，**每一条都必须处理，不存在"不紧急就跳过"的选项**。

处理流程：
1. 运行 `python3 scripts/sync-tracked-docs.py` 同步文档列表
2. 用 tenant_access_token 获取所有 tracked docs 的评论（`file_type` 必须放在 URL query param，不是 body）
3. 与 `data/comment-state.json` 对比，找出新评论
4. **对每一条新评论**：
   a. 理解评论意图（如"完成"=声称完成任务，问题=需要回答，修改建议=需要修改文档）
   b. **如果是"完成"类评论，必须先验证**：调 API / 检查文件 / 检查配置，确认任务真的完成了
   c. 验证通过：执行对应操作（更新文档状态），回复评论（说明已验证并更新）
   d. 验证失败：回复评论说明未通过验证，**不标记为已解决**
   e. 标记评论为已解决（PATCH `is_solved: true`）——仅验证通过后
   f. 更新 `comment-state.json`
5. API 格式：
   - 读评论：`GET /drive/v1/files/{token}/comments?file_type=docx`
   - 回复：`POST /drive/v1/files/{token}/comments/{id}/replies?file_type=docx`
   - 解决：`PATCH /drive/v1/files/{token}/comments/{id}?file_type=docx` body `{"is_solved":true}`

## ⚠️ 子任务 prompt 必须包含的信息

每个 spawn 的子任务 prompt 必须明确写入：

1. **Token 类型**：Wiki 用 user_access_token（从 `data/lark-user-token.json` 读取），消息用 tenant_access_token
2. **消息发送方式**：子任务**不能用 `message` 工具**（缺少 Feishu 配置）！必须用脚本：
   ```bash
   /home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "<chat_id>" "<消息内容>"
   ```
3. **Wiki 写入位置**：从 `data/backlog.md` 底部的「Wiki 目标映射」表中查询具体的 space_id + parent_node_token
4. **消息发送目标**：从 `data/backlog.md` 底部的「消息目标映射」表中查询 chat_id。当前对话来自哪里就发回哪里

### 研究任务 spawn prompt 模板
spawn 后台研究时，**必须先读取 `scripts/research-spawn-checklist.md`**，逐项检查后再 spawn。

必须在 prompt 中明确告诉子任务：
- 该任务属于哪个项目（如"从零训练模型"/"AI 玩小丑牌"/"内部参考"）
- Wiki Space ID 和父节点 node_token（从 backlog 映射表获取）
- **Wiki 创建的完整 curl 命令**（不能只说"同步到 Wiki"，子任务不知道怎么操作）
- **user_access_token 路径**: `data/lark-user-token.json`
- 完成后消息应该发到哪个 chat_id
- 不需要上 Wiki 的任务明确说"不需要创建 Wiki 节点"

**⚠️ 映射表缺失时的处理**：如果 backlog 映射表里没有该项目的 parent_node_token，必须**先创建 Wiki 父节点、更新映射表，再 spawn 子任务**。绝不能跳过。

### 常用目标
- Carl 私聊: `oc_453c88ec52dd029845c46249837e3ba0`
- Luna 群聊: `oc_a2a70c6b4a29c2f2eb6c2500ea42a500`
- Carl 私人知识库: space `7604150806383693538`
- Luna 协同知识库: space `7604126789916479197`

## ⚠️ 防串台
- 子任务用 `scripts/lark-send-message.sh` 直接发消息到目标 chat_id
- **不要用 `message` 工具**（子任务环境没有 Feishu channel 配置，会报错）
- **不要依赖 sessions_spawn 的 announce 回传**（会走 main session 的 deliveryContext，可能串台）
- 主 session 收到子任务回传后回复 NO_REPLY
