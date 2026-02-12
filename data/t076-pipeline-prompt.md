# Research Task: Data Processing Pipeline (t076)

## 目标
实现数据清洗流水线的最小可行原型 (MVP)。

## 任务清单
1. **设计流水线 (`data/pipeline.py`)**:
   - 包含以下步骤的框架：
     1. **Language Identification** (如 `fasttext` 或简单启发式)
     2. **Quality Filtering** (长度、困惑度/perplexity、特殊字符比例)
     3. **Deduplication** (MinHash LSH 或简单的精确去重)
     4. **PII Scrubbing** (正则替换 Email/Phone/IP)
   - 代码应为 Python 脚本，可独立运行。
   - 使用 mock 数据或小样本展示流程跑通。

2. **依赖管理**:
   - 更新 `requirements.txt` 添加所需库 (如 `datatrove`, `fasttext`, `nltk`, `presidio-analyzer` 等，视具体选型而定)。

3. **同步到 Wiki**:
   - 将设计思路和代码片段写入 Wiki。
   - **Space ID**: `7604150806383693538`
   - **Parent Node Token**: `OZmqwn4yviwsY2k1JBblkgTYg5c`
   - **Title**: "Data Processing Pipeline MVP"

4. **更新 Backlog**:
   - 修改 `data/backlog.md`: 将 "数据清洗流水线原型 (Processing Pipeline)" 标记为完成。

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json` (user_access_token)
- **Wiki API**:
  - 创建节点: `POST /open-apis/wiki/v2/spaces/{space_id}/nodes`
  - 写入内容: `POST /open-apis/docx/v1/documents/{token}/blocks/{token}/children`
- **消息发送**:
  - 脚本: `bash /home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "oc_a2a70c6b4a29c2f2eb6c2500ea42a500" "✅ t076 完成: ..."`
  - **禁止使用 `message` 工具**

## 任务管理
- 任务 ID: t076
- 完成后运行: `python3 scripts/task-manager.py complete t076 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t076 "错误原因"`
