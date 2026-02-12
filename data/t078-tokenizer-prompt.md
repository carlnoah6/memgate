# Research Task: Tokenizer Training MVP (t078)

## 目标
训练一个基于 SentencePiece 的 BPE Tokenizer (Vocab Size: 100k) 原型。

## 任务清单
1. **准备训练数据**:
   - 使用 `data/download/download_fineweb_edu.py` 下载少量样本（例如 100MB-500MB），或者使用 HuggingFace `wikitext` 数据集作为替代，用于快速验证训练流程。
   - 保存为 `data/corpus_sample.txt`。

2. **编写训练脚本 (`scripts/train_tokenizer.py`)**:
   - 使用 `sentencepiece` 库。
   - 参数参考：
     - `vocab_size=100000` (Roadmap 目标)
     - `model_type="bpe"`
     - `character_coverage=0.9995`
   - 输出：`tokenizer.model` 和 `tokenizer.vocab`。

3. **测试 Tokenizer**:
   - 编写简单的加载测试，打印示例文本的 Token ID 和还原文本。

4. **同步到 Wiki**:
   - 将训练代码、参数配置和简单的测试结果写入 Wiki。
   - **Space ID**: `7604150806383693538`
   - **Parent Node Token**: `OZmqwn4yviwsY2k1JBblkgTYg5c`
   - **Title**: "Tokenizer Training MVP"

5. **更新 Backlog**:
   - 修改 `data/backlog.md`: 将 "Tokenizer 训练与评估 (Tokenizer Training)" 标记为完成。

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json` (user_access_token)
- **Wiki API**:
  - 创建节点: `POST /open-apis/wiki/v2/spaces/{space_id}/nodes`
  - 写入内容: `POST /open-apis/docx/v1/documents/{token}/blocks/{token}/children`
- **消息发送**:
  - 脚本: `bash /home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "oc_a2a70c6b4a29c2f2eb6c2500ea42a500" "✅ t078 完成: ..."`

## 任务管理
- 任务 ID: t078
- 完成后运行: `python3 scripts/task-manager.py complete t078 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t078 "错误原因"`
