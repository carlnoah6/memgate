# Lark 事件订阅指南

## 常用事件订阅

### 1. 消息事件（必需）
| 事件 | 说明 | 是否必需 |
|------|------|----------|
| `im.message.receive_v1` | 接收单聊/群聊消息 | ✅ 必需 |
| `im.message.reaction.created_v1` | 消息被添加表情回应 | 可选 |
| `im.message.reaction.deleted_v1` | 消息表情回应被删除 | 可选 |

### 2. 机器人事件
| 事件 | 说明 |
|------|------|
| `application.bot.menu_v6` | 用户点击机器人菜单 |
| `p2p_chat_create` | 用户首次与机器人单聊 |

### 3. 群组事件
| 事件 | 说明 |
|------|------|
| `im.chat.disbanded_v1` | 群聊被解散 |
| `im.chat.updated_v1` | 群聊信息更新 |

---

## 推荐配置

**最简配置（只收消息）：**
```
✅ im.message.receive_v1
```

**完整配置（推荐）：**
```
✅ im.message.receive_v1（接收消息）
✅ p2p_chat_create（用户首次聊天）
✅ im.message.reaction.created_v1（表情回应）
```

---

## 在 Lark 后台配置

1. 访问 https://open.larksuite.com
2. 你的应用 → **Events** → **Event Subscription**
3. 在 **Subscribe to events** 中添加事件
