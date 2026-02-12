# 🌙 Luna 群标题自动更新功能

**功能**: 根据 Luna 的当前任务状态，自动更新群聊标题  
**启用时间**: 2026-02-12  
**状态**: ✅ 已上线

---

## 功能介绍

Luna 现在会自动根据当前执行的任务更新群聊标题，让你一眼就能看到：
- 当前正在执行什么任务
- 任务执行状态（进行中 / 已完成 / 失败等）
- 任务 ID（方便追踪）

## 标题格式

```
Luna [状态图标] [任务ID] [简短描述]
```

### 状态图标说明

| 图标 | 含义 | 示例 |
|------|------|------|
| 🔄 | 进行中 | Luna 🔄 tid-0212-30 编写文档 |
| ⏳ | 等待执行 | Luna ⏳ tid-0212-31 等待开始 |
| ✅ | 已完成 | Luna ✅ tid-0212-30 文档完成 |
| ❌ | 执行失败 | Luna ❌ tid-0212-30 更新失败 |
| 🚫 | 已取消 | Luna 🚫 tid-0212-30 任务取消 |
| 🌙 | 空闲中 | Luna 🌙 空闲中 |

---

## 配置说明

### 当前启用的群聊

| 群聊 | 状态 | 说明 |
|------|------|------|
| Carl 私聊 (Luna机器人主对话) | ✅ 启用 | 高优先级 |
| 📋 Luna任务板 | ✅ 启用 | 高优先级 |
| Luna 群聊 (多人) | ✅ 启用 | 中优先级 |

### 如何启用/禁用

编辑配置文件：`data/group-title-config.json`

```json
{
  "enabled": true,           // 全局开关
  "default_enabled": false,  // 新群聊默认是否启用
  "groups": {
    "oc_xxx": {
      "enabled": true,       // 该群聊是否启用
      "description": "群聊描述",
      "priority": "high"
    }
  }
}
```

---

## 工作原理

### 自动触发时机

群标题会在以下情况自动更新：

1. **任务创建** — 新任务加入队列
2. **任务开始** — 任务进入 running 状态
3. **任务完成** — 任务标记为 done
4. **任务失败** — 任务标记为 failed
5. **任务取消** — 任务被 cancel
6. **规划器步骤完成** — planner step-done
7. **规划器步骤失败** — planner step-fail
8. **规划器重新规划** — planner replan
9. **规划器取消** — planner cancel

### 智能任务选择

当多个任务同时存在时，标题显示优先级：

1. **当前群聊的 running 任务**（最高优先级）
2. **全局最新的 running 任务**
3. **当前群聊最近完成的任务**（30分钟内）
4. **全局最近完成的任务**（10分钟内）
5. **空闲状态**（无活跃任务）

### 后台任务过滤

以下任务不会显示在标题中：
- 定期检查任务（Periodic Check）
- 系统维护任务（[System]）

---

## 技术实现

### 核心脚本

| 脚本 | 功能 |
|------|------|
| `scripts/update-group-title.py` | 核心更新逻辑 |
| `data/group-title-config.json` | 群聊配置 |
| `data/group-title-state.json` | 上次更新状态（防重复） |

### 集成点

- **task-manager.py** — 任务状态变更后触发
- **planner.py** — 规划器步骤变更后触发
- **TaskEngine** — 提供任务查询接口

---

## 使用示例

### 查看当前任务分析

```bash
python3 scripts/update-group-title.py --chat-id oc_xxx --analyze
```

### 手动触发更新（测试用）

```bash
python3 scripts/update-group-title.py --chat-id oc_xxx --force
```

### 查看配置

```bash
cat data/group-title-config.json
```

---

## 故障排除

### 标题没有自动更新

1. 检查配置是否启用：`cat data/group-title-config.json`
2. 检查 Bot 是否有群管理权限
3. 手动测试：`python3 scripts/update-group-title.py --chat-id oc_xxx --force`

### 标题显示错误

1. 检查任务面板状态：`python3 scripts/task-manager.py list`
2. 检查是否有 running 任务被卡住

### 权限错误

如果看到 `403 Forbidden` 错误：
1. 在 Lark 后台给 Bot 添加 `im:chat` 权限
2. 确保 Bot 在群聊中有管理员权限

---

## 版本历史

| 版本 | 时间 | 变更 |
|------|------|------|
| v1.0 | 2026-02-12 | 初始版本上线 |

---

**文档维护**: Luna  
**最后更新**: 2026-02-12
