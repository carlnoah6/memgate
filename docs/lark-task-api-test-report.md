# Lark 任务卡片（待办）API 测试报告

**测试时间**: 2026-02-13  
**测试人**: Luna (tid-0213-2)  
**API 版本**: Lark Task API v2

---

## 1. 可用功能汇总

### ✅ 已验证可用功能

| 功能 | API 端点 | 状态 | 备注 |
|------|----------|------|------|
| 获取任务清单列表 | GET /task/v2/tasklists | ✅ | 可查看所有任务清单 |
| 列出任务 | GET /task/v2/tasks | ✅ | 支持分页 |
| 创建任务 | POST /task/v2/tasks | ✅ | 支持摘要、描述、截止日期等 |
| 获取任务详情 | GET /task/v2/tasks/{guid} | ✅ | 返回完整任务信息 |
| 更新任务 | PATCH /task/v2/tasks/{guid} | ✅ | 需指定 update_fields |
| 完成任务 | PATCH /task/v2/tasks/{guid} | ✅ | 设置 completed_at 时间戳 |
| 取消完成 | PATCH /task/v2/tasks/{guid} | ✅ | 设置 completed_at 为 "0" |
| 删除任务 | DELETE /task/v2/tasks/{guid} | ✅ | 永久删除 |

### ❌ 测试失败/不可用功能

| 功能 | 状态 | 原因 |
|------|------|------|
| 添加评论 | ❌ | 404，API 路径可能不同 |
| 分配任务 | ❌ | update_fields 不支持 assignee |
| 设置 followers | ❌ | 创建时不支持 |

---

## 2. API 格式规范

### 2.1 创建任务

```http
POST /task/v2/tasks
Content-Type: application/json

{
  "summary": "任务标题",
  "description": "任务描述",
  "due": {
    "timestamp": "1771546794000"  // 毫秒时间戳字符串
  },
  "start": {
    "timestamp": "1770942009000"
  },
  "is_all_day": false
}
```

**注意**: 
- `due` 和 `start` 必须是对象格式，包含 `timestamp` 字段
- 时间戳是**字符串类型**的毫秒时间戳
- `is_all_day` 是布尔值

### 2.2 更新任务

```http
PATCH /task/v2/tasks/{guid}
Content-Type: application/json

{
  "task": {
    "summary": "新标题",
    "description": "新描述",
    "completed_at": "1770942025000",
    "due": {"timestamp": "1771546794000"}
  },
  "update_fields": ["summary", "description", "completed_at", "due"]
}
```

**关键要求**: 
- 必须使用 `update_fields` 数组显式指定要更新的字段
- 支持的字段: `summary`, `description`, `completed_at`, `due`, `start`, `is_all_day`, `repeat_rule`, `mode`, `is_milestone`, `custom_complete`, `custom_fields`, `extra`
- **不支持**: `assignee`, `followers`

### 2.3 完成任务

```http
PATCH /task/v2/tasks/{guid}
Content-Type: application/json

{
  "task": {
    "completed_at": "1770942025000"  // 当前时间的毫秒时间戳
  },
  "update_fields": ["completed_at"]
}
```

取消完成:
```json
{
  "task": {"completed_at": "0"},
  "update_fields": ["completed_at"]
}
```

### 2.4 删除任务

```http
DELETE /task/v2/tasks/{guid}
```

---

## 3. 任务数据结构

```json
{
  "guid": "a0c7d7a5-2f5b-48d6-a303-458de48fe7bb",
  "task_id": "t102603",
  "summary": "任务标题",
  "description": "任务描述",
  "status": "todo",  // 或 "done"
  "completed_at": "0",  // 毫秒时间戳字符串，未完成时为 "0"
  "created_at": "1770942009886",
  "updated_at": "1770942016585",
  "due": {
    "is_all_day": false,
    "timestamp": "1771546794000"
  },
  "creator": {
    "id": "ou_35f664e694dd100adf97b867e68e1d3a",
    "type": "user"
  },
  "url": "https://applink.larksuite.com/client/todo/detail?guid=...",
  "origin": {
    "href": {"title": "Luna", "url": ""},
    "platform_i18n_name": {...}
  },
  "source": 7,  // 任务来源
  "mode": 2,
  "is_milestone": false,
  "subtask_count": 0,
  "parent_task_guid": "",
  "tasklists": [],  // 所属任务清单
  "dependencies": []
}
```

---

## 4. 与 OpenClaw 的集成方案

### 4.1 使用场景

Lark 任务卡片可以在以下场景与 OpenClaw 集成：

1. **任务提醒**: 心跳检测时发现即将到期的事项 → 创建 Lark 任务
2. **规划器任务同步**: 规划器中的步骤完成 → 同步更新 Lark 任务状态
3. **用户指令**: "把这个加入待办" → 创建 Lark 任务
4. **定期任务**: 每日/每周自动生成重复性任务

### 4.2 技术实现

**Token 要求**: 需要 `user_access_token`（tenant_token 权限不足）

**权限范围**:
```
task:task:write     - 创建/更新/删除任务
task:tasklist:read  - 读取任务清单
```

**Python 调用示例**:

```python
from datetime import datetime, timedelta, timezone
from scripts.lark_common import lark_api, get_user_token

def create_lark_task(summary: str, description: str = "", due_days: int = None):
    token = get_user_token()
    
    body = {"summary": summary}
    if description:
        body["description"] = description
    if due_days:
        due_ts = int((datetime.now(timezone.utc) + timedelta(days=due_days)).timestamp() * 1000)
        body["due"] = {"timestamp": str(due_ts)}
    
    result = lark_api(
        "POST", "/task/v2/tasks",
        body=body,
        token=token,
        token_type="user"
    )
    return result.get("task", {})

def complete_lark_task(task_guid: str):
    token = get_user_token()
    completed_ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    
    result = lark_api(
        "PATCH",
        f"/task/v2/tasks/{task_guid}",
        body={
            "task": {"completed_at": completed_ts},
            "update_fields": ["completed_at"]
        },
        token=token,
        token_type="user"
    )
    return result.get("task", {})
```

### 4.3 与规划器的集成

可以在规划器步骤完成后自动同步到 Lark 任务：

```python
# 规划器 step-done 回调中
def on_step_complete(plan_chat_id, step_id, result):
    # 如果该步骤关联了 Lark 任务，则更新状态
    task_guid = get_linked_lark_task(plan_chat_id, step_id)
    if task_guid:
        complete_lark_task(task_guid)
```

### 4.4 与心跳的集成

在定期检查中自动创建提醒任务：

```python
# heartbeat-scheduler.py 中的定期检查
def check_upcoming_events():
    events = get_calendar_events(days=1)
    for event in events:
        if event.get('reminder') and not has_lark_task(event['id']):
            create_lark_task(
                summary=f"提醒: {event['summary']}",
                description=event.get('description', ''),
                due_days=1
            )
```

---

## 5. 限制与注意事项

### 5.1 已知限制

| 限制 | 说明 |
|------|------|
| 不支持评论 | 评论 API 路径未找到或需要其他权限 |
| 不支持分配 | 无法通过 API 设置 assignee |
| 不支持 followers | 无法通过 API 设置任务关注者 |
| 需 user_token | tenant_token 权限不足以操作任务 |

### 5.2 注意事项

1. **时间戳格式**: 所有时间戳必须是**字符串类型**的毫秒时间戳
2. **update_fields**: 更新时必须显式指定要修改的字段
3. **权限检查**: 确保应用的 OAuth 范围包含 `task:task:write`
4. **任务归属**: 通过 API 创建的任务归属给 token 对应的用户
5. **链接格式**: 任务 URL 格式为 `https://applink.larksuite.com/client/todo/detail?guid={guid}&suite_entity_num={task_id}`

---

## 6. 测试脚本

测试脚本位置: `scripts/test-lark-task-api.py`

运行方式:
```bash
cd /home/ubuntu/.openclaw/workspace
python3 scripts/test-lark-task-api.py
```

测试覆盖:
- ✅ 创建简单任务
- ✅ 创建带截止日期的任务
- ✅ 获取任务详情
- ✅ 更新任务
- ✅ 完成任务
- ✅ 取消完成
- ✅ 删除任务
- ✅ 列出任务清单

---

## 7. 结论

Lark Task API v2 提供了基本的任务管理功能，可以满足与 OpenClaw 的基本集成需求：

**推荐集成**:
- 从 OpenClaw 创建 Lark 任务作为提醒
- 同步 OpenClaw 规划器状态到 Lark 任务
- 心跳检测时自动创建待办事项

**暂不建议**:
- 复杂的任务分配场景（不支持 assignee）
- 评论同步（API 不可用）

**下一步建议**:
1. 创建 `lark_task.py` 模块封装常用操作
2. 在规划器中添加 Lark 任务同步选项
3. 在心跳流程中添加自动任务创建逻辑
