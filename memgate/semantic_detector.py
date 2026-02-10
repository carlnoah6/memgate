#!/usr/bin/env python3
"""
Privacy Guard — 语义级隐私检测器 (Embedding-based)

通过将隐私知识条目编码为向量，对输出文本做语义相似度匹配，
弥补关键词/正则匹配被改述绕过的短板。

支持多种 embedding provider:
  - "openai"  : OpenAI text-embedding-3-small (需 OPENAI_API_KEY)
  - "local"   : sentence-transformers 本地模型 (需 pip install sentence-transformers)
  - "ngram"   : 内置字符 n-gram + 词袋 混合相似度 (零依赖, 用于测试/fallback)

典型用法:
    detector = SemanticDetector(provider="ngram")
    detector.build_index(private_items)
    hits = detector.detect("He goes hiking with Ma Yuan every two weeks")
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .knowledge_store import KnowledgeItem, KnowledgeStore, ALWAYS_PRIVATE_CATEGORIES

# ─── 常量 ──────────────────────────────────────────────────────

DEFAULT_SIMILARITY_THRESHOLD = 0.55  # cosine similarity 阈值
DEFAULT_TOP_K = 5  # 每次检索 top-k 最近邻
CACHE_DIR = Path(__file__).parent / ".embedding_cache"


# ═══════════════════════════════════════════════════════════════
#  数据类
# ═══════════════════════════════════════════════════════════════


@dataclass
class SemanticHit:
    """一条语义匹配结果"""

    item_id: str
    category: str
    similarity: float
    matched_content: str  # 被命中的知识条目原文
    query_text: str  # 触发命中的查询片段


@dataclass
class SemanticResult:
    """语义检测汇总"""

    flagged: bool
    hits: list[SemanticHit] = field(default_factory=list)
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD


# ═══════════════════════════════════════════════════════════════
#  Embedding Provider 抽象层
# ═══════════════════════════════════════════════════════════════


class EmbeddingProvider(ABC):
    """嵌入向量提供器基类"""

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """
        将一组文本编码为向量矩阵。

        Args:
            texts: 文本列表
        Returns:
            shape (len(texts), dim) 的 float32 ndarray
        """
        ...

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度"""
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding-3-small / text-embedding-ada-002"""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        batch_size: int = 64,
    ):
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ImportError("pip install openai  (需要 openai SDK)")

        self.model = model
        self.batch_size = batch_size
        self._client = openai.OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url,
        )
        self._dim: Optional[int] = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            r = self._client.embeddings.create(input=["probe"], model=self.model)
            self._dim = len(r.data[0].embedding)
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        all_vecs: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            resp = self._client.embeddings.create(input=batch, model=self.model)
            sorted_data = sorted(resp.data, key=lambda d: d.index)
            all_vecs.extend([d.embedding for d in sorted_data])
        arr = np.array(all_vecs, dtype=np.float32)
        if self._dim is None:
            self._dim = arr.shape[1]
        return arr


class LocalEmbeddingProvider(EmbeddingProvider):
    """sentence-transformers 本地模型"""

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "pip install sentence-transformers  (需要 sentence-transformers)"
            )
        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_sentence_embedding_dimension()

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, convert_to_numpy=True).astype(np.float32)


# ─── 内置轻量级 N-gram Provider (零依赖 fallback) ─────────────


def _tokenize(text: str) -> list[str]:
    """
    中英文混合分词:
      - 英文按空格/标点切词并小写化
      - 中文逐字拆分（CJK 字符）
    """
    tokens: list[str] = []
    buf: list[str] = []
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            if buf:
                word = "".join(buf).strip().lower()
                if word:
                    tokens.append(word)
                buf = []
            tokens.append(ch)
        elif ch.isalnum() or ch == "'":
            buf.append(ch)
        else:
            if buf:
                word = "".join(buf).strip().lower()
                if word:
                    tokens.append(word)
                buf = []
    if buf:
        word = "".join(buf).strip().lower()
        if word:
            tokens.append(word)
    return tokens


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    """提取字符级 n-gram"""
    text = re.sub(r"\s+", " ", text.lower().strip())
    return [text[i : i + n] for i in range(len(text) - n + 1)]


class NgramEmbeddingProvider(EmbeddingProvider):
    """
    基于字符 n-gram + 词袋 的混合嵌入。

    无外部依赖。将文本映射到固定维度的稀疏向量（通过 hash 投影），
    然后 L2 归一化后做 cosine 相似度。
    """

    def __init__(self, dim: int = 4096, char_n: int = 3, word_weight: float = 2.0):
        self._dim = dim
        self.char_n = char_n
        self.word_weight = word_weight

    @property
    def dim(self) -> int:
        return self._dim

    def _text_to_features(self, text: str) -> Counter:
        features: Counter = Counter()
        for ng in _char_ngrams(text, self.char_n):
            features[ng] += 1
        for tok in _tokenize(text):
            features[f"W:{tok}"] += self.word_weight
        toks = _tokenize(text)
        for i in range(len(toks) - 1):
            features[f"B:{toks[i]}_{toks[i+1]}"] += self.word_weight * 0.5
        return features

    def _hash_feature(self, feature: str) -> int:
        h = int(hashlib.md5(feature.encode()).hexdigest(), 16)
        return h % self._dim

    def _feature_sign(self, feature: str) -> float:
        h = int(hashlib.sha1(feature.encode()).hexdigest(), 16)
        return 1.0 if h % 2 == 0 else -1.0

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, text in enumerate(texts):
            features = self._text_to_features(text)
            for feat, weight in features.items():
                idx = self._hash_feature(feat)
                sign = self._feature_sign(feat)
                vecs[i, idx] += weight * sign
            norm = np.linalg.norm(vecs[i])
            if norm > 0:
                vecs[i] /= norm
        return vecs


# ═══════════════════════════════════════════════════════════════
#  Privacy Vector Index
# ═══════════════════════════════════════════════════════════════


class PrivacyVectorIndex:
    """
    隐私知识向量索引。
    使用 numpy 实现 cosine 相似度搜索，无需 faiss 依赖。
    """

    def __init__(self, provider: EmbeddingProvider):
        self.provider = provider
        self._vectors: Optional[np.ndarray] = None
        self._items: list[KnowledgeItem] = []
        self._item_texts: list[str] = []

    @property
    def size(self) -> int:
        return len(self._items)

    def _item_to_text(self, item: KnowledgeItem) -> str:
        parts = [item.content]
        if item.tags:
            parts.append(" ".join(item.tags))
        return " ".join(parts)

    def build(self, items: list[KnowledgeItem]) -> None:
        if not items:
            self._vectors = np.zeros((0, self.provider.dim), dtype=np.float32)
            self._items = []
            self._item_texts = []
            return
        self._items = list(items)
        self._item_texts = [self._item_to_text(it) for it in self._items]
        self._vectors = self.provider.embed(self._item_texts)

    def search(
        self, query_vec: np.ndarray, top_k: int = DEFAULT_TOP_K
    ) -> list[tuple[int, float]]:
        if self._vectors is None or self._vectors.shape[0] == 0:
            return []
        qn = np.linalg.norm(query_vec)
        if qn == 0:
            return []
        q = query_vec / qn
        norms = np.linalg.norm(self._vectors, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)
        normed = self._vectors / norms
        sims = normed @ q
        top_k = min(top_k, len(sims))
        top_indices = np.argpartition(sims, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]
        return [(int(idx), float(sims[idx])) for idx in top_indices]

    def get_item(self, index: int) -> KnowledgeItem:
        return self._items[index]


# ═══════════════════════════════════════════════════════════════
#  Semantic Detector
# ═══════════════════════════════════════════════════════════════


def _split_into_segments(text: str, max_len: int = 120) -> list[str]:
    """将长文本按句子切分为多个片段。"""
    if len(text) <= max_len:
        return [text]
    parts = re.split(r"[。\n；;.!！?？]+", text)
    segments: list[str] = []
    buf = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(buf) + len(p) > max_len and buf:
            segments.append(buf.strip())
            buf = p
        else:
            buf = f"{buf} {p}" if buf else p
    if buf.strip():
        segments.append(buf.strip())
    return segments if segments else [text]


class SemanticDetector:
    """
    语义级隐私检测器。

    使用 embedding 向量索引检测输出文本是否在语义上匹配私有知识。
    作为关键词/正则匹配的补充层。

    Usage:
        detector = SemanticDetector(provider="ngram")
        detector.build_index(store.get_private("alice"))
        result = detector.detect("Alice goes hiking with her investor biweekly")
        if result.flagged:
            for hit in result.hits:
                print(f"  Warning: {hit.category} (sim={hit.similarity:.3f})")
    """

    def __init__(
        self,
        provider: str | EmbeddingProvider = "ngram",
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        top_k: int = DEFAULT_TOP_K,
        **provider_kwargs,
    ):
        if isinstance(provider, str):
            self._provider = _create_provider(provider, **provider_kwargs)
        else:
            self._provider = provider
        self.threshold = threshold
        self.top_k = top_k
        self._index: Optional[PrivacyVectorIndex] = None

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    @property
    def index(self) -> Optional[PrivacyVectorIndex]:
        return self._index

    def build_index(self, private_items: list[KnowledgeItem]) -> int:
        """为私有知识条目构建向量索引（只索引 always-private 类别）。"""
        items = [it for it in private_items if it.category in ALWAYS_PRIVATE_CATEGORIES]
        self._index = PrivacyVectorIndex(self._provider)
        self._index.build(items)
        return self._index.size

    def build_index_from_store(
        self, store: KnowledgeStore, users: Optional[list[str]] = None
    ) -> int:
        """从 KnowledgeStore 构建索引。"""
        if users is None:
            users = store.list_users()
        all_private: list[KnowledgeItem] = []
        for user in users:
            all_private.extend(store.get_private(user))
        return self.build_index(all_private)

    def detect(self, text: str) -> SemanticResult:
        """检测文本是否语义上匹配私有知识。"""
        if self._index is None or self._index.size == 0:
            return SemanticResult(flagged=False, threshold=self.threshold)
        segments = _split_into_segments(text)
        if not segments:
            return SemanticResult(flagged=False, threshold=self.threshold)
        seg_vecs = self._provider.embed(segments)
        hits: list[SemanticHit] = []
        seen_item_ids: set[str] = set()
        for seg_idx, segment in enumerate(segments):
            results = self._index.search(seg_vecs[seg_idx], top_k=self.top_k)
            for item_idx, sim in results:
                if sim < self.threshold:
                    continue
                item = self._index.get_item(item_idx)
                if item.id in seen_item_ids:
                    continue
                seen_item_ids.add(item.id)
                hits.append(
                    SemanticHit(
                        item_id=item.id,
                        category=item.category,
                        similarity=sim,
                        matched_content=item.content,
                        query_text=segment,
                    )
                )
        hits.sort(key=lambda h: h.similarity, reverse=True)
        return SemanticResult(
            flagged=len(hits) > 0, hits=hits, threshold=self.threshold
        )


# ═══════════════════════════════════════════════════════════════
#  Provider 工厂
# ═══════════════════════════════════════════════════════════════


def _create_provider(name: str, **kwargs) -> EmbeddingProvider:
    name = name.lower().strip()
    if name == "openai":
        return OpenAIEmbeddingProvider(**kwargs)
    elif name == "local":
        return LocalEmbeddingProvider(**kwargs)
    elif name == "ngram":
        return NgramEmbeddingProvider(**kwargs)
    else:
        raise ValueError(
            f"Unknown embedding provider: {name!r}. " f"Supported: openai, local, ngram"
        )


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Semantic privacy detection CLI")
    parser.add_argument("--provider", default="ngram", help="embedding provider")
    parser.add_argument("--threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD)
    parser.add_argument("--user", default=None, help="index specific user only")
    parser.add_argument("message", help="message to check")
    args = parser.parse_args()

    store = KnowledgeStore()
    detector = SemanticDetector(provider=args.provider, threshold=args.threshold)
    users = [args.user] if args.user else None
    n = detector.build_index_from_store(store, users=users)
    print(f"Index size: {n}")

    result = detector.detect(args.message)
    print(
        json.dumps(
            {
                "flagged": result.flagged,
                "threshold": result.threshold,
                "hits": [
                    {
                        "item_id": h.item_id,
                        "category": h.category,
                        "similarity": round(h.similarity, 4),
                        "matched_content": h.matched_content,
                        "query_text": h.query_text,
                    }
                    for h in result.hits
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
