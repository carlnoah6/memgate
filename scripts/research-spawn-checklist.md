# 研究任务 Spawn 前必检清单

## ⚠️ 每次 spawn 研究子任务前，必须逐项检查。缺一不可。

### 1. Wiki 父节点存在性检查
- [ ] 在 `data/backlog.md` 的「Wiki 目标映射」表中查找该项目
- [ ] 如果不存在 → **先创建 Wiki 父节点，再填入映射表**
- [ ] 确认有具体的 `parent_node_token`（不能只有 space_id）

### 2. Spawn Prompt 必须包含以下字段
- [ ] **user_access_token 路径**: `data/lark-user-token.json`
- [ ] **Wiki Space ID**: 从映射表获取
- [ ] **Wiki 父节点 node_token**: 从映射表获取
- [ ] **Wiki 创建方法**: 包含完整的 curl 命令模板
- [ ] **消息发送脚本**: `scripts/lark-send-message.sh "<chat_id>" "<内容>"`
- [ ] **目标 chat_id**: 从映射表获取
- [ ] **明确说明不要用 `message` 工具**

### 3. API 参数验证
- [ ] **所有 block_type 数字**必须从 `memory/reference/lark-docx-block-types.md` 查取
- [ ] **不能凭记忆编写**任何枚举值、type 编号、字段名
- [ ] 常用 block_type: Text=2, Heading2=4, Heading3=5, Bullet=12, Ordered=13, Code=14, Divider=22
- [ ] ⚠️ 教训(2/9): 15/16 不是列表，是 Quote/Equation！子任务多花了 30 分钟调试

### 4. Prompt 模板（复制使用）

```
## Wiki 同步（必须完成）
1. 获取 user_access_token:
   TOKEN=$(python3 -c "import json; print(json.load(open('/home/ubuntu/.openclaw/workspace/data/lark-user-token.json'))['access_token'])")

2. 在 Wiki 创建文档节点:
   curl -s -X POST "https://open.larksuite.com/open-apis/wiki/v2/spaces/{SPACE_ID}/nodes" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"obj_type":"docx","node_type":"origin","parent_node_token":"{PARENT_NODE_TOKEN}","title":"文档标题"}'

3. 将研究内容写入文档（分段写入，每段 <4500 字符）:
   curl -s -X POST "https://open.larksuite.com/open-apis/docx/v1/documents/{obj_token}/blocks/{obj_token}/children" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"children":[{"block_type":14,"code":{"style":{"language":1},"elements":[{"text_run":{"content":"内容"}}]}}],"index":0}'

## 消息发送
- **不要用 `message` 工具**（子任务没有 Feishu 配置）
- 用脚本: /home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "{CHAT_ID}" "消息内容"
```
