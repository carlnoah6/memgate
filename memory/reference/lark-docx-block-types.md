# Lark Docx Block Type 参考

> 来源: https://github.com/chyroc/lark/blob/master/type_docx.go
> 验证日期: 2026-02-09

## Block Type 映射表

| block_type | 名称 | JSON key | 说明 |
|-----------|------|----------|------|
| 1 | Page | `page` | 文档根节点 |
| 2 | Text | `text` | 普通文本段落 |
| 3 | Heading1 | `heading1` | 一级标题 |
| 4 | Heading2 | `heading2` | 二级标题 |
| 5 | Heading3 | `heading3` | 三级标题 |
| 6 | Heading4 | `heading4` | 四级标题 |
| 7 | Heading5 | `heading5` | 五级标题 |
| 8 | Heading6 | `heading6` | 六级标题 |
| 9 | Heading7 | `heading7` | 七级标题 |
| 10 | Heading8 | `heading8` | 八级标题 |
| 11 | Heading9 | `heading9` | 九级标题 |
| **12** | **Bullet** | **`bullet`** | **无序列表** |
| **13** | **Ordered** | **`ordered`** | **有序列表** |
| 14 | Code | `code` | 代码块 |
| 15 | Quote | `quote` | 引用 |
| 16 | Equation | `equation` | 公式（可能已下线）|
| 17 | Todo | `todo` | 任务/待办 |
| 18 | Bitable | `bitable` | 多维表格 |
| 19 | Callout | `callout` | 高亮块 |
| 20 | ChatCard | `chat_card` | 群聊卡片 |
| 21 | Diagram | `diagram` | 流程图/UML |
| **22** | **Divider** | **`divider`** | **分割线** |
| 23 | File | `file` | 文件 |
| 24 | Grid | `grid` | 分栏 |
| 25 | GridColumn | `grid_column` | 分栏列 |
| 26 | Iframe | `iframe` | 内嵌 |
| 27 | Image | `image` | 图片 |
| 31 | Table | `table` | 表格 |
| 32 | TableCell | `table_cell` | 单元格 |
| 34 | QuoteContainer | `quote_container` | 引用容器 |

## 创建 block 的 JSON 结构

### 文本段落 (type=2)
```json
{"block_type": 2, "text": {"elements": [{"text_run": {"content": "文字"}}]}}
```

### 标题 (type=3~11)
```json
{"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "二级标题"}}]}}
```
注意：heading 的 JSON key 不是 `heading`，而是 `heading1`/`heading2`/... 对应 type 3/4/5/...

### 无序列表 (type=12)
```json
{"block_type": 12, "bullet": {"elements": [{"text_run": {"content": "列表项"}}]}}
```

### 有序列表 (type=13)
```json
{"block_type": 13, "ordered": {"elements": [{"text_run": {"content": "列表项"}}]}}
```

### 分割线 (type=22)
```json
{"block_type": 22, "divider": {}}
```

### 加粗文字
```json
{"text_run": {"content": "加粗", "text_element_style": {"bold": true}}}
```

## API 端点

- 创建 children: `POST /docx/v1/documents/{doc_id}/blocks/{doc_id}/children`
- 删除 children: `DELETE /docx/v1/documents/{doc_id}/blocks/{doc_id}/children/batch_delete`
- 获取 children: `GET /docx/v1/documents/{doc_id}/blocks/{doc_id}/children`
- 必须用 **user_access_token**
