# Research Task: Data Loader Implementation (t090)

## 目标
基于 "从零训练模型" 路线图 Phase 2，实现高效的流式数据加载器。

## 任务清单
1. **实现数据加载器 (`data/dataloader.py`)**:
   - 流式读取预处理后的 tokenized 数据（`.bin` / `.npy` / memory-mapped files）
   - 支持 sequence packing（将多条短文本拼接到 max_seq_len，用 attention mask 分隔）
   - 支持分布式采样（每个 rank 读不同的 data shard）
   - Prefetch / 多 worker 并行加载
   - 动态 batch 构建（padding-free when possible）

2. **实现数据预处理脚本 (`data/prepare_data.py`)**:
   - 读取原始文本 → tokenize → 写入二进制格式
   - 支持 sharding（将大数据集分成多个 shard）
   - 记录 metadata（总 token 数、shard 信息）

3. **与 Trainer 集成**:
   - 修改 `training/trainer.py` 使其接受新的 DataLoader
   - 确保 checkpoint 包含 data position（恢复训练时不重复数据）

4. **编写测试 (`tests/test_dataloader.py`)**:
   - 用小数据集验证 tokenization → binary → dataloader 全链路
   - 验证 sequence packing 正确性
   - 验证分布式采样不重叠

5. **同步到 Wiki**:
   - **Space ID**: `7604150806383693538`
   - **Parent Node Token**: `OZmqwn4yviwsY2k1JBblkgTYg5c`
   - **Title**: "Data Loader Implementation"

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json`
- **消息发送**: `bash scripts/lark-send-message.sh ...`
- **已有代码**: `model/`, `training/trainer.py`, `data/pipeline.py`, `data/tokenizer.model`

## 任务管理
- 任务 ID: t090
- 完成后运行: `python3 scripts/task-manager.py complete t090 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t090 "错误原因"`
