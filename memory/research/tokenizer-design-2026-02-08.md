# Tokenizer 设计：BPE vs SentencePiece vs Unigram，中英文混合方案

> 研究日期：2026-02-08
> 任务来源：LLM 从零训练系列 #3

---

## 一、核心概念：为什么 Tokenizer 如此重要？

Tokenizer 是 LLM 训练的**第一步也是最关键的一步**——它决定了模型"看到"的文本单位，直接影响：

1. **训练效率**：token 数量 = 训练的计算量。更高效的 tokenizer 意味着同样的文本需要更少的 token
2. **推理速度**：每个 token 需要一次 forward pass，更少的 token = 更快的生成
3. **上下文窗口利用率**：相同 context length 下，高效 tokenizer 能塞进更多信息
4. **多语言公平性**：差的 tokenizer 可能让中文用 3x token 编码同样信息，导致成本和效果都打折
5. **语义理解**：token 边界影响模型对语义的理解（如中文分词错误会改变语义）

## 二、三大 Tokenizer 算法详解

### 2.1 Byte-Pair Encoding (BPE)

**原理**：自底向上的贪心合并算法
1. 从基础词表（字符或字节）开始
2. 统计所有相邻 token 对的频率
3. 合并最高频的 token 对为新 token
4. 重复直到达到目标词表大小

**变体**：
- **字符级 BPE**：基础词表 = 所有 Unicode 字符。缺点：基础词表可能很大
- **字节级 BPE (BBPE)**：基础词表 = 256 个字节值。优点：固定大小，可表示任何 Unicode 字符，无 UNK token

**特点**：
| 维度 | 表现 |
|------|------|
| 方向 | 自底向上（从小到大合并） |
| 确定性 | ✅ 完全确定性，同一文本总是产生相同分词 |
| 训练速度 | 快，O(n) 每步 |
| OOV 处理 | BBPE 无 OOV；字符级可能有 |
| 使用者 | GPT-2/3/4, LLaMA 系列, Mistral, DeepSeek |

**代码示例**（概念）：
```python
# BPE 核心循环
vocab = set(all_bytes)  # 256 bytes
merges = []
for i in range(num_merges):
    pair = most_frequent_pair(corpus)
    merges.append(pair)
    vocab.add(merge(pair))
    corpus = apply_merge(corpus, pair)
```

### 2.2 Unigram Language Model

**原理**：自顶向下的概率剪枝算法
1. 从一个**大词表**开始（包含所有常见子串）
2. 用 Unigram 语言模型为每个 token 分配概率
3. 计算移除每个 token 后整体 loss 的增加量
4. 移除 loss 增加最小的 10-20% token
5. 重复直到达到目标词表大小

**特点**：
| 维度 | 表现 |
|------|------|
| 方向 | 自顶向下（从大到小剪枝） |
| 确定性 | ❌ 可以产生多种分词（可采样），支持 subword regularization |
| 语义质量 | 通常更好，因为基于概率优化 |
| 训练速度 | 较慢，需要 EM 算法 |
| OOV 处理 | 需要 byte fallback 或 UNK |
| 使用者 | T5, mT5, ALBERT, XLNet（通过 SentencePiece） |

**关键优势**：Unigram 的**subword regularization** 能力——对同一文本采样不同分词，相当于数据增强，可以提高模型鲁棒性。

### 2.3 WordPiece

**原理**：类似 BPE，但合并标准不同
- BPE：合并频率最高的 pair
- WordPiece：合并使训练数据**似然最大化**的 pair（互信息最大）

**特点**：
- 用 `##` 标记非词首子词（如 "playing" → ["play", "##ing"]）
- 主要被 BERT 系列使用
- 实际上 Google 没有开源训练算法，只有推理代码

**现代 LLM 中已较少使用**，主流选择是 BPE（特别是 BBPE）。

### 2.4 三者对比总结

| 特性 | BPE | Unigram | WordPiece |
|------|-----|---------|-----------|
| **构建方向** | 自底向上合并 | 自顶向下剪枝 | 自底向上合并 |
| **合并标准** | 频率最高 | 概率优化 | 互信息最大 |
| **分词确定性** | 确定 | 概率性（可采样） | 确定 |
| **处理未知文本** | 好（BBPE 无 OOV） | 需 fallback | 一般 |
| **训练速度** | 快 | 慢 | 中 |
| **当前主流度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |

## 三、SentencePiece：不是算法，是框架

**重要区分**：SentencePiece 不是一种分词算法，而是 Google 开发的**分词框架/库**，支持：
- BPE 算法
- Unigram 算法

### 3.1 SentencePiece 的核心优势

1. **语言无关**：直接在原始文本上训练，不需要预分词（pre-tokenization）
   - 传统 BPE 需要先用空格/规则分词，再在词内做子词分割
   - SentencePiece 把空格当作普通字符（用 `▁` 表示），从原始字节流学习
   - **这对中文至关重要**——中文没有空格分隔词

2. **可逆性**：保留空格信息，可以完美还原原文

3. **Byte fallback**：对未见字符用 UTF-8 字节表示，保证无 OOV

4. **高效**：C++ 实现，训练和推理都很快

### 3.2 SentencePiece vs HuggingFace Tokenizers

| 特性 | SentencePiece | HuggingFace Tokenizers |
|------|--------------|----------------------|
| 预分词 | 不需要 | 需要（regex/空格） |
| 空格处理 | `▁` 作为词表一部分 | 依赖 pre-tokenizer |
| 中文支持 | 原生好 | 需要配置 |
| BPE 性能 | 通常更好（研究表明） | 标准 |
| 训练接口 | 命令行 / Python | Python |
| 使用者 | LLaMA 1/2, T5, mT5 | BERT, GPT-2, RoBERTa |

**研究发现**：2024 年的对比研究（24 个 2.6B 模型）表明，**SentencePiece 的 BPE 实现在单语和多语设置中通常优于 HuggingFace 的 BPE 实现**。

### 3.3 Tiktoken（OpenAI）

LLaMA 3 和 GPT-4 转向使用 **tiktoken**——OpenAI 的 BPE 实现：
- 纯 BBPE，用 regex 做 pre-tokenization（拆分数字、空格等）
- Rust 实现，推理极快
- LLaMA 3 从 SentencePiece 切换到 tiktoken

## 四、主流模型 Tokenizer 参数对比

| 模型 | 算法 | 库 | 词表大小 | 中文 tokens | 中文效率(char/token) |
|------|------|-----|---------|------------|---------------------|
| **GPT-4** | BBPE | tiktoken | 100,277 | ~10k | ~1.0-1.5 |
| **GPT-4o** | BBPE | tiktoken | 200,019 | ~20k+ | ~1.5-2.0 |
| **LLaMA 2** | BPE | SentencePiece | 32,000 | 极少 | ~0.3-0.5（很差） |
| **LLaMA 3** | BBPE | tiktoken | 128,256 | 大量增加 | ~1.5 |
| **Qwen** | BBPE | tiktoken | 151,643 | ~25k | ~1.5-1.8 |
| **DeepSeek-V2** | BBPE | 自研 | 100,000 | 中文>英文 | ~1.5 |
| **DeepSeek-V3** | BBPE | 自研 | 128,000 | 丰富 | ~1.5-2.0 |
| **ChatGLM3** | BPE | SentencePiece | 64,789 | ~31k | ~1.5 |
| **Baichuan2** | BPE | SentencePiece | 125,696 | ~70k | ~2.0 |
| **Yi-34B** | BPE | SentencePiece | 64,000 | ~21k | ~1.5 |
| **Mistral** | BBPE | SentencePiece | 32,000 | 极少 | ~0.3-0.5（很差） |

### 关键发现

1. **中文效率差距巨大**：LLaMA 2 的 32K 词表编码中文极其低效（一个汉字可能要 2-3 个 token），而 Qwen 的 151K 词表中文效率达 1.5-1.8 字符/token
2. **趋势**：词表从 32K → 128K+ 是明确趋势，主要为了多语言效率
3. **Qwen 的策略最激进**：151K 词表，是目前对中英文平衡最好的

## 五、中英文混合 Tokenizer 设计方案

### 5.1 核心挑战

1. **无空格分词**：中文没有天然的词边界
2. **字符密度差异**：一个中文字符含义密度远高于一个英文字母
3. **UTF-8 编码不对等**：中文字符 3 字节，英文 1 字节。BBPE 中如果不做优化，中文天然需要 3x token
4. **跨语言合并问题**：BPE 可能产生语义错误的跨字合并（如 "学" + "科" 应在某些上下文不合并）
5. **词表分配**：中英文占词表比例直接影响各自效率

### 5.2 推荐方案：Byte-level BPE + 大词表

**最佳实践路线**（综合 Qwen、DeepSeek、LLaMA 3 的经验）：

#### 步骤 1：准备训练语料
```
中文：40-50%（包括简繁体、各领域文本）
英文：30-40%
代码：10-15%
其他语言：5-10%
```

**关键原则**：tokenizer 训练数据的语言比例决定了各语言的编码效率。想要中文高效，必须给足中文数据。

#### 步骤 2：选择算法和库

**推荐组合**：

| 场景 | 推荐 | 理由 |
|------|------|------|
| 研究/小团队 | SentencePiece BPE | 成熟、文档好、训练方便 |
| 追求极致性能 | tiktoken-style BBPE | LLaMA 3 / Qwen 验证过 |
| 需要概率分词 | SentencePiece Unigram | subword regularization |

#### 步骤 3：词表大小选择

| 模型规模 | 推荐词表大小 | 理由 |
|---------|------------|------|
| < 1B | 32K - 64K | 词表占参数比例太大，需控制 |
| 1B - 7B | 64K - 128K | 平衡效率和参数量 |
| 7B - 70B | 100K - 152K | 词表开销占比小，可以大 |
| > 70B | 128K - 200K | 参考 GPT-4o 的 200K |

**词表大小的参数开销计算**：
```
embedding 参数 = vocab_size × hidden_dim
例：128K × 4096 = 524M 参数
对于 7B 模型，这是 7.5% 的开销
对于 70B 模型，只是 0.75%
```

#### 步骤 4：Pre-tokenization 正则表达式

这是容易被忽略但极其重要的步骤。参考 GPT-4 / LLaMA 3 的 regex：

```python
# LLaMA 3 / GPT-4 style regex
pat = r"""'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}{1,3}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"""
```

**关键设计决策**：
- **数字拆分**：将数字拆成每 1-3 位一组（提高数学能力）
- **中文处理**：`\p{L}` 匹配所有 Unicode 字母/汉字，中文字符被单独匹配
- **空格保留**：空格信息不丢失
- **换行保留**：对代码很重要

#### 步骤 5：特殊 Token 设计

```python
special_tokens = {
    "<|begin_of_text|>": 128000,  # BOS
    "<|end_of_text|>": 128001,    # EOS
    "<|start_header_id|>": 128002,
    "<|end_header_id|>": 128003,
    "<|eot_id|>": 128004,         # end of turn
    "<|im_start|>": 128005,       # chat format
    "<|im_end|>": 128006,
    # 预留空间给未来扩展
    "<|reserved_0|>": 128007,
    # ... 更多预留
}
```

**建议**：预留 200-500 个 special token 位，方便后续扩展（如工具调用、多模态标记等）。

### 5.3 SentencePiece 训练实战配置

```python
import sentencepiece as spm

spm.SentencePieceTrainer.train(
    sentence_iterator=data_iterator,
    model_prefix="my_tokenizer",
    vocab_size=100000,              # 词表大小
    model_type="bpe",               # 算法：bpe 或 unigram
    character_coverage=1.0,          # 字符覆盖率，1.0 保证无 UNK
    byte_fallback=True,              # 字节回退，处理未见字符
    split_digits=True,               # 拆分数字
    allow_whitespace_only_pieces=True,
    num_threads=24,
    max_sentence_length=300000,
    train_extremely_large_corpus=True,
    
    # 特殊 token
    unk_piece='<unk>',
    bos_piece='<s>',
    eos_piece='</s>',
    pad_piece='<pad>',
    unk_id=0, bos_id=1, eos_id=2, pad_id=3,
    
    # 用户自定义 token
    user_defined_symbols=[
        "<|im_start|>", "<|im_end|>",
        "<|system|>", "<|user|>", "<|assistant|>"
    ],
)
```

### 5.4 使用 HuggingFace Tokenizers 训练

```python
from tokenizers import Tokenizer, models, trainers, pre_tokenizers, processors

# 初始化
tokenizer = Tokenizer(models.BPE())

# Pre-tokenizer（关键！）
tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)

# 训练器
trainer = trainers.BpeTrainer(
    vocab_size=100000,
    special_tokens=["<pad>", "<s>", "</s>", "<unk>"],
    min_frequency=2,
    show_progress=True,
)

# 训练
tokenizer.train_from_iterator(data_iterator, trainer=trainer)

# 后处理
tokenizer.post_processor = processors.ByteLevel(trim_offsets=True)
```

## 六、中文 Tokenizer 的特殊问题与解决方案

### 6.1 合并错误问题

BPE 在中文上的典型问题（Digital Orientalist, 2025 研究）：
- "他是学**科技**的" 可能被错误分为 "学科" + "技"（因为"学科"在语料中更高频）
- "他**不**相信" 可能被合并为 "他不" 作为一个 token
- "的**事物**" 可能被错误分为 "的事" + "物"

**这些错误的根源**：BPE 的贪心合并策略 + 中文缺乏空格分隔

### 6.2 解决方案

1. **增大词表**：更多 token 意味着更多正确的多字词被覆盖。Qwen 的 151K 和 Baichuan 的 125K 都是这个思路

2. **控制 pre-tokenization**：
   - 可以先用 jieba/THULAC 等中文分词工具预处理
   - 或者在 regex 中添加中文感知规则
   - 但这会引入分词工具自身的偏差

3. **使用 Unigram 替代 BPE**：Unigram 的概率优化可能产生更合理的中文分词

4. **字符级 + 常见词混合**：
   - 保证所有常用汉字（~6000 个）作为独立 token
   - 高频双字词（~20000 个）作为合并 token
   - 其余走正常 BPE 合并

### 6.3 推荐的中文优化策略

```python
# 方法 1：确保常用汉字在词表中
# 在 SentencePiece 中，character_coverage=1.0 + 足够的中文语料 
# 通常能自动覆盖

# 方法 2：手动添加高频中文词
user_defined_symbols = [
    # 常见双字词
    "我们", "他们", "什么", "可以", "这个", "那个",
    "因为", "所以", "但是", "如果", "虽然", "而且",
    # ... 更多高频词
]

# 方法 3：数据配比优化
# 中文语料占比至少 40%
# 确保语料覆盖多个领域：新闻、百科、小说、论坛、学术
```

## 七、选型建议决策树

```
你在训练什么模型？
├── 纯英文模型
│   └── 推荐：BBPE + tiktoken/HF Tokenizers
│       词表：32K-50K
│
├── 中英双语模型 ← 大多数情况
│   ├── 模型 ≤ 3B
│   │   └── SentencePiece BPE, 词表 64K
│   ├── 模型 3B-13B
│   │   └── SentencePiece BPE 或 tiktoken, 词表 100K-128K
│   └── 模型 > 13B
│       └── tiktoken BBPE, 词表 128K-152K
│
├── 多语言模型（>5 种语言）
│   └── SentencePiece BPE, 词表 128K-200K
│
└── 领域专用（代码/医学等）
    └── 在通用 tokenizer 基础上扩展
        或训练领域 tokenizer, 词表 50K-100K
```

## 八、实用工具和资源

### 训练工具
1. **SentencePiece** - https://github.com/google/sentencepiece
2. **HuggingFace Tokenizers** - https://github.com/huggingface/tokenizers
3. **tiktoken** - https://github.com/openai/tiktoken（仅推理，不含训练）

### 评估工具
1. **Fertility**（生育率）：平均每个词需要多少 token。越低越好
2. **Parity**（平等性）：不同语言编码效率的一致性
3. **Compression ratio**：原始字节数 / token 数

### 评估脚本示例
```python
def evaluate_tokenizer(tokenizer, texts_zh, texts_en):
    """评估 tokenizer 的中英文效率"""
    # 中文 fertility
    zh_chars = sum(len(t) for t in texts_zh)
    zh_tokens = sum(len(tokenizer.encode(t)) for t in texts_zh)
    zh_fertility = zh_tokens / zh_chars
    
    # 英文 fertility（按词算）
    en_words = sum(len(t.split()) for t in texts_en)
    en_tokens = sum(len(tokenizer.encode(t)) for t in texts_en)
    en_fertility = en_tokens / en_words
    
    print(f"中文: {zh_fertility:.2f} tokens/char (越低越好，理想 0.5-0.7)")
    print(f"英文: {en_fertility:.2f} tokens/word (越低越好，理想 1.2-1.5)")
    
    # Parity
    parity = zh_fertility / en_fertility
    print(f"中英平等性: {parity:.2f} (越接近 1 越好)")
```

## 九、总结与建议

### 对于从零训练中英双语 LLM：

1. **算法选择**：**Byte-level BPE**（主流、验证充分、确定性好）
2. **训练框架**：SentencePiece（如果追求易用）或 自研 tiktoken-style（如果追求极致控制）
3. **词表大小**：
   - 7B 以下：**64K-100K**
   - 7B 以上：**100K-152K**
4. **数据配比**：中文 45%、英文 35%、代码 15%、其他 5%
5. **必须确保**：
   - `byte_fallback=True`（无 OOV）
   - `split_digits=True`（数学能力）
   - 数字拆分为 1-3 位一组
   - 预留 200+ special token 位
6. **验证指标**：
   - 中文 fertility < 0.7 tokens/char
   - 英文 fertility < 1.5 tokens/word
   - 中英 parity 比值在 0.8-1.2 之间

### ⚠️ 常见陷阱

1. **不要用纯英文 tokenizer 处理中文**（LLaMA 2 的教训：32K 词表，中文极差）
2. **不要过度合并中文字符**（可能产生语义错误的 token）
3. **训练语料要有代表性**（GPT-4o 词表被发现含大量赌博/色情相关中文 token）
4. **词表大小不是越大越好**（增大嵌入层开销，小模型尤其要注意）
5. **Tokenizer 训练后不能轻易更换**（需要重新训练整个模型）

---

## 参考来源

1. HuggingFace Tokenizer Summary - https://huggingface.co/docs/transformers/en/tokenizer_summary
2. "To Merge or Not to Merge: Chinese Tokenization in LLMs" - Digital Orientalist, 2025
3. "Tokenizer Choice For LLM Training: Negligible or Crucial?" - Continuum Labs, 2024
4. Meta LLaMA 3 Blog - https://ai.meta.com/blog/meta-llama-3/
5. Qwen Tokenization Note - https://github.com/QwenLM/Qwen/blob/main/tokenization_note.md
6. DeepSeek-V2 Technical Report - https://arxiv.org/html/2405.04434v2
7. "Tokenization Matters!" - arXiv 2405.17067
