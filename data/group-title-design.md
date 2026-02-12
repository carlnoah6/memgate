# 群标题自动生成设计文档

**任务**: tid-0212-24 — 群标题自动更新功能 Step 2  
**时间**: 2026-02-12  
**更新**: 2026-02-12 23:35（根据 MEMORY.md 确认的 v4 混合模式更新）
**状态**: ✅ 设计已确认，实现见 `scripts/update-group-title.py`

---

## ⚠️ 重要说明

本设计文档已根据 Carl 的反馈更新。**最终设计采用 v4 混合模式**，核心原则是：

> **话题 > 任务** — 用户关心"在聊什么"，不是"系统在执行什么任务"。

详细设计文档见：`docs/group-title-design.md`

---

## v4 混合模式设计（已确认）

### 核心原则

| 版本 | 逻辑 | 问题 | 结果 |
|------|------|------|------|
| v1 | 显示 running 任务名 | 子任务跳动、所有群一样、无任务时"空闲" | ❌ 废弃 |
| v2 | 显示具体步骤 | 标题太长、看不懂 | ❌ 废弃 |
| v3 | 话题跟踪（3小时窗口） | 和规划器冲突 | ⚠️ 部分解决 |
| **v4** | **混合模式** | 完美符合需求 | ✅ **采用** |

### 三层优先级逻辑

```
1. 有活跃规划器 → "🔄 <规划器名字>"（如"群标题自动更新"）
2. 无规划器但有对话 → "💬 聊<话题>"（如"聊飞书"）  
3. 都无为 → "🌙 空闲"
```

### 关键决策

| 决策 | 说明 |
|------|------|
| ✅ 规划器名字（goal） | 而非具体任务/步骤 |
| ✅ 3小时时间窗口 | 允许中断休息 |
| ✅ 15字符限制 | 手机端完整显示 |
| ❌ 不显示 task_id | 避免技术细节 |
| ❌ 不显示 Step X | 过于具体 |
| ❌ 不显示完整描述 | 太长看不懂 |

### 话题检测规则

1. **活跃窗口**: 3小时内（最近一条消息在3小时内）
2. **冷却时间**: 6小时无消息 = 话题结束
3. **关键词匹配**: 从最近消息提取关键词，匹配预设话题

### 关键词配置

```json
// data/group-title-config.json
{
  "topic_keywords": {
    "openclaw": ["openclaw", "gateway", "重启", "升级"],
    "lark": ["lark", "飞书", "群标题", "表格"],
    "planning": ["规划器", "planner", "编排"],
    "proxy": ["api-proxy", "zoro", "代理"],
    "training": ["训练", "model", "llm"]
  },
  "topic_display_names": {
    "openclaw": "OpenClaw",
    "lark": "飞书",
    "planning": "规划器",
    "proxy": "API代理",
    "training": "模型训练"
  }
}
```

---

## 数据结构

### 规划器数据

```json
// data/planner/<chat_id后8位>.json
{
  "goal": "群标题自动更新",
  "chat_id": "oc_7f3ebd31a5cf2fec9170952b29eb2700",
  "steps": [
    {"id": 1, "status": "done", "title": "调研 Lark API"},
    {"id": 2, "status": "running", "title": "设计状态检测逻辑"},
    {"id": 3, "status": "pending", "title": "实现核心脚本"}
  ],
  "created_at": "2026-02-12T22:00:00+08:00",
  "updated_at": "2026-02-12T22:25:00+08:00"
}
```

### 状态缓存

```json
// data/group-title-state.json
{
  "last_titles": {
    "oc_7f3ebd31a5cf2fec9170952b29eb2700": {
      "title": "🔄 群标题自动更新",
      "type": "planner",
      "updated_at": "2026-02-12T22:25:00+08:00"
    }
  },
  "version": 1
}
```

---

## 实现函数设计

### 主入口

```python
def update_group_title(chat_id: str, dry_run: bool = False) -> dict:
    """
    更新指定群聊的标题
    
    返回: {
        "updated": bool,      # 是否实际更新
        "old_title": str,     # 原标题
        "new_title": str,     # 新标题
        "reason": str         # 更新原因
    }
    """
```

### 三层检测

```python
def detect_title_context(chat_id: str) -> dict:
    """
    检测当前群聊的标题上下文
    
    返回优先级最高的上下文：
    - type: "planner" | "topic" | "idle"
    - title: 格式化后的标题
    - source: 数据来源说明
    """
    # 1. 检查活跃规划器
    planner = get_active_planner(chat_id)
    if planner and has_running_or_pending_steps(planner):
        return {
            "type": "planner",
            "title": format_planner_title(planner["goal"]),
            "source": f"planner:{planner.get('task_id', 'unknown')}"
        }
    
    # 2. 检查活跃对话话题
    topic = analyze_conversation_topic(chat_id)
    if topic:
        return {
            "type": "topic",
            "title": format_topic_title(topic),
            "source": f"topic:{topic['key']}"
        }
    
    # 3. 空闲状态
    return {
        "type": "idle",
        "title": "🌙 空闲",
        "source": "idle"
    }
```

### 格式化函数

```python
def format_planner_title(goal: str, max_length: int = 15) -> str:
    """格式化规划器标题"""
    # 移除常见前缀
    prefixes = ["[Plan]", "[Research]", "群标题"]
    for prefix in prefixes:
        goal = goal.replace(prefix, "").strip()
    
    # 截断
    if len(goal) > max_length - 2:  # 留2字符给图标和空格
        goal = goal[:max_length-3] + "…"
    
    return f"🔄 {goal}"


def format_topic_title(topic: dict, max_length: int = 15) -> str:
    """格式化话题标题"""
    name = topic.get("display_name", topic["key"])
    if len(name) > max_length - 3:  # 留3字符给"💬 聊"
        name = name[:max_length-4] + "…"
    return f"💬 聊{name}"
```

---

## 边界情况处理

| 场景 | 处理方式 | 标题示例 |
|------|----------|----------|
| 规划器完成 | 显示话题或空闲 | 💬 聊飞书 / 🌙 空闲 |
| 规划器取消 | 同完成 | 🌙 空闲 |
| 多规划器冲突 | 取最新的规划器 | 🔄 最新规划器名 |
| 话题检测失败 | 默认显示"聊天中" | 💬 聊天中 |
| API调用失败 | 保持原标题，记录日志 | (不更新) |
| 标题无变化 | 跳过API调用 | (不更新) |

---

## 触发时机

| 触发源 | 触发条件 | 处理 |
|--------|----------|------|
| 心跳 | 每 30 分钟检查一次 | 批量检查所有活跃群聊 |
| 规划器变更 | step-done / step-fail / replan | 立即触发对应群 |
| 任务完成 | task complete / fail | 检查是否影响群标题 |
| 新消息 | 3小时窗口检测 | 被动检测，不主动触发 |

---

## 配置项

```python
# scripts/update-group-title.py 顶部配置

TITLE_CONFIG = {
    # 长度限制
    "max_length": 15,
    
    # 活跃窗口（小时）
    "active_window_hours": 3,
    
    # 冷却时间（小时）
    "cooldown_hours": 6,
    
    # 图标映射
    "icons": {
        "planner": "🔄",
        "topic": "💬",
        "idle": "🌙",
    },
    
    # 描述前缀移除规则
    "prefixes_to_remove": [
        r"\[Plan\]",
        r"\[Research\]",
        r"群标题",
    ]
}
```

---

## 与现有系统集成

### 与 planner 集成

```python
# planner.py step-done/step-fail/replan 后调用:
subprocess.run([
    "python3", "scripts/update-group-title.py",
    "--chat-id", chat_id,
    "--reason", f"planner_{action}"
], capture_output=True)
```

### 与 task-manager 集成

```python
# task-manager.py complete/fail 后（如果影响群聊）:
if task.get("source_chat"):
    update_group_title(task["source_chat"], reason=f"task_{status}")
```

### 与心跳集成

```python
# heartbeat-scheduler.py 中添加:
def check_group_titles():
    """检查所有需要更新的群标题"""
    active_chats = get_active_chat_ids()  # 有消息或任务的群
    for chat_id in active_chats:
        update_group_title(chat_id, reason="heartbeat")
```

---

## 测试用例

| 用例 | 输入 | 预期输出 |
|------|------|----------|
| 活跃规划器 | planner running | 🔄 群标题自动更新 |
| 规划器完成 | planner done | 💬 聊飞书 / 🌙 空闲 |
| 话题匹配 | 消息含"飞书" | 💬 聊飞书 |
| 话题不匹配 | 闲聊消息 | 💬 聊天中 |
| 空闲 | 6小时无消息 | 🌙 空闲 |
| 长规划器名 | goal 超过15字符 | 🔄 群标题自动更… |
| 无变化 | 标题相同 | 跳过更新 |

---

## 实现状态

- [x] 设计文档（本文档）
- [x] 详细设计文档（`docs/group-title-design.md`）
- [x] 核心脚本（`scripts/update-group-title.py`）
- [ ] 配置文件（`data/group-title-config.json`）
- [ ] 心跳集成
- [ ] planner 集成
- [ ] task-manager 集成

---

## 经验教训

### ✅ 做得好的
1. **快速迭代**: 从任务跟踪→话题跟踪→混合模式，3轮内找到正确方向
2. **用户驱动**: 根据 Carl 反馈实时调整，不固守最初设计
3. **配置化**: 关键词映射外置到 JSON，便于调整

### ⚠️ 踩过的坑
1. **过度工程**: 最初想显示完整任务描述 → 太长看不懂
2. **技术视角**: 关注 task_id、步骤编号 → 用户不关心
3. **路径混乱**: chat_id 格式不一致（oc_xxx vs 后8位）

### 📝 核心洞察
- **用户视角**: Carl 要的是"一眼知道在聊啥"，不是"精确追踪每个子任务"
- **时间 > 状态**: 对话的自然节奏比系统状态更能反映"当前在做什么"
- **简洁至上**: 15字符内表达完整意图，宁可模糊也不要冗长

---

**设计完成时间**: 2026-02-12 22:30 (SGT)  
**更新时间**: 2026-02-12 23:35 (SGT) — 根据 v4 混合模式更新  
**状态**: 设计已确认，实现参考 `scripts/update-group-title.py`
