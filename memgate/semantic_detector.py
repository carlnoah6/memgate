#!/usr/bin/env python3
"""
Privacy Guard — Semantic-level Privacy Detector (Embedding-based)

Encodes private knowledge entries as vectors and performs semantic similarity
matching on output text, compensating for the shortcomings of keyword/regex
matching when paraphrasing is used to evade detection.

Supports multiple embedding providers:
  - "openai"  : OpenAI text-embedding-3-small (requires OPENAI_API_KEY)
  - "local"   : sentence-transformers local model (requires pip install sentence-transformers)
  - "ngram"   : Built-in character n-gram + bag-of-words hybrid similarity (zero dependencies, for testing/fallback)

Typical usage:
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

# --- Constants ---

DEFAULT_SIMILARITY_THRESHOLD = 0.55  # Cosine similarity threshold
DEFAULT_TOP_K = 5  # Retrieve top-k nearest neighbors per query
CACHE_DIR = Path(__file__).parent / ".embedding_cache"


# ===================================================================
#  Data Classes
# ===================================================================


@dataclass
class SemanticHit:
    """A single semantic match between a query segment and a private knowledge entry.

    Attributes:
        item_id: Unique identifier of the matched ``KnowledgeItem``.
        category: Privacy category of the matched item (e.g. ``"health"``).
        similarity: Cosine similarity score between the query segment and the
            matched knowledge entry (range 0..1).
        matched_content: Original textual content of the matched knowledge entry.
        query_text: The query fragment (segment) that triggered this match.
    """

    item_id: str
    category: str
    similarity: float
    matched_content: str
    query_text: str


@dataclass
class SemanticResult:
    """Aggregated result of a semantic privacy detection scan.

    Attributes:
        flagged: ``True`` if at least one knowledge entry exceeded the
            similarity threshold; ``False`` otherwise.
        hits: List of :class:`SemanticHit` instances sorted by descending
            similarity.  Empty when ``flagged`` is ``False``.
        threshold: The cosine similarity threshold that was used for this
            detection run.
    """

    flagged: bool
    hits: list[SemanticHit] = field(default_factory=list)
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD


# ===================================================================
#  Embedding Provider Abstraction Layer
# ===================================================================


class EmbeddingProvider(ABC):
    """Abstract base class for embedding vector providers.

    Subclasses must implement :meth:`embed` to convert text into dense
    vectors and expose the vector dimensionality via the :attr:`dim`
    property.
    """

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Encode a batch of text strings into embedding vectors.

        Args:
            texts: List of text strings to embed.

        Returns:
            A ``float32`` numpy array of shape ``(len(texts), dim)`` where
            each row is the embedding vector for the corresponding input text.
        """
        ...

    @property
    @abstractmethod
    def dim(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by the OpenAI Embeddings API.

    Uses models such as ``text-embedding-3-small`` or
    ``text-embedding-ada-002``.  Requires the ``openai`` Python package
    and a valid ``OPENAI_API_KEY`` environment variable (or an explicit
    *api_key* argument).
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        batch_size: int = 64,
    ):
        """Initialise the OpenAI embedding provider.

        Args:
            model: Name of the OpenAI embedding model to use.
            api_key: OpenAI API key.  Falls back to the ``OPENAI_API_KEY``
                environment variable when not provided.
            base_url: Optional custom base URL for the OpenAI-compatible API.
            batch_size: Maximum number of texts to embed in a single API call.

        Raises:
            ImportError: If the ``openai`` package is not installed.
        """
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ImportError("pip install openai  (requires openai SDK)")

        self.model = model
        self.batch_size = batch_size
        self._client = openai.OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url,
        )
        self._dim: Optional[int] = None

    @property
    def dim(self) -> int:
        """Return the embedding dimensionality, probing the API if unknown."""
        if self._dim is None:
            r = self._client.embeddings.create(input=["probe"], model=self.model)
            self._dim = len(r.data[0].embedding)
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        """Encode texts via the OpenAI Embeddings API.

        Texts are processed in batches of :attr:`batch_size`.

        Args:
            texts: List of text strings to embed.

        Returns:
            A ``float32`` numpy array of shape ``(len(texts), dim)``.
        """
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
    """Embedding provider using a local ``sentence-transformers`` model.

    Runs entirely on the local machine without external API calls.
    Requires the ``sentence-transformers`` Python package.
    """

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        """Initialise the local sentence-transformers provider.

        Args:
            model_name: Hugging Face model identifier for the
                ``SentenceTransformer`` to load.

        Raises:
            ImportError: If ``sentence-transformers`` is not installed.
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "pip install sentence-transformers  (requires sentence-transformers)"
            )
        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_sentence_embedding_dimension()

    @property
    def dim(self) -> int:
        """Return the embedding dimensionality of the loaded model."""
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        """Encode texts using the local sentence-transformers model.

        Args:
            texts: List of text strings to embed.

        Returns:
            A ``float32`` numpy array of shape ``(len(texts), dim)``.
        """
        return self._model.encode(texts, convert_to_numpy=True).astype(np.float32)


# --- Built-in lightweight N-gram Provider (zero-dependency fallback) ---


def _tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese/English text into a flat token list.

    English words are split on whitespace and punctuation boundaries and
    lowercased.  Chinese (CJK Unified Ideographs) characters are emitted as
    individual single-character tokens.

    Args:
        text: The input text to tokenize.

    Returns:
        A list of token strings.
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
    """Extract overlapping character-level n-grams from *text*.

    Whitespace is collapsed to single spaces and the text is lowercased
    before n-gram extraction.

    Args:
        text: The input text.
        n: Length of each n-gram.

    Returns:
        A list of character n-gram strings.
    """
    text = re.sub(r"\s+", " ", text.lower().strip())
    return [text[i : i + n] for i in range(len(text) - n + 1)]


class NgramEmbeddingProvider(EmbeddingProvider):
    """Hybrid embedding provider based on character n-grams and bag-of-words.

    Requires no external dependencies.  Text features (character n-grams,
    unigram words, and bigram word pairs) are hashed into a fixed-dimension
    sparse vector using the *hashing trick*, then L2-normalised so that dot
    products correspond to cosine similarity.
    """

    def __init__(self, dim: int = 4096, char_n: int = 3, word_weight: float = 2.0):
        """Initialise the n-gram embedding provider.

        Args:
            dim: Dimensionality of the output embedding vectors.
            char_n: Length of character n-grams to extract.
            word_weight: Multiplicative weight applied to word-level features
                relative to character n-gram features.
        """
        self._dim = dim
        self.char_n = char_n
        self.word_weight = word_weight

    @property
    def dim(self) -> int:
        """Return the fixed output vector dimensionality."""
        return self._dim

    def _text_to_features(self, text: str) -> Counter:
        """Convert text into a weighted feature bag.

        Extracts character n-grams, word unigrams, and word bigrams, each
        with their respective weights.

        Args:
            text: The input text.

        Returns:
            A :class:`~collections.Counter` mapping feature strings to their
            accumulated weights.
        """
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
        """Map a feature string to a vector index via MD5 hashing.

        Args:
            feature: The feature string to hash.

        Returns:
            An integer index in the range ``[0, dim)``.
        """
        h = int(hashlib.md5(feature.encode()).hexdigest(), 16)
        return h % self._dim

    def _feature_sign(self, feature: str) -> float:
        """Determine the sign (+1 or -1) for a feature via SHA-1 hashing.

        Using a random sign reduces hash-collision bias in the projected
        vector (the *signed hashing trick*).

        Args:
            feature: The feature string to hash.

        Returns:
            ``1.0`` or ``-1.0``.
        """
        h = int(hashlib.sha1(feature.encode()).hexdigest(), 16)
        return 1.0 if h % 2 == 0 else -1.0

    def embed(self, texts: list[str]) -> np.ndarray:
        """Encode texts into L2-normalised hash-projected vectors.

        Args:
            texts: List of text strings to embed.

        Returns:
            A ``float32`` numpy array of shape ``(len(texts), dim)``.
        """
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


# ===================================================================
#  Privacy Vector Index
# ===================================================================


class PrivacyVectorIndex:
    """In-memory vector index for private knowledge items.

    Stores embedding vectors computed by an :class:`EmbeddingProvider` and
    supports brute-force cosine similarity search using NumPy (no FAISS
    dependency required).
    """

    def __init__(self, provider: EmbeddingProvider):
        """Initialise the vector index.

        Args:
            provider: The embedding provider used to compute vectors.
        """
        self.provider = provider
        self._vectors: Optional[np.ndarray] = None
        self._items: list[KnowledgeItem] = []
        self._item_texts: list[str] = []

    @property
    def size(self) -> int:
        """Return the number of items stored in the index."""
        return len(self._items)

    def _item_to_text(self, item: KnowledgeItem) -> str:
        """Convert a knowledge item to a single text string for embedding.

        The item's content and tags (if any) are concatenated.

        Args:
            item: The knowledge item to convert.

        Returns:
            A space-joined text representation.
        """
        parts = [item.content]
        if item.tags:
            parts.append(" ".join(item.tags))
        return " ".join(parts)

    def build(self, items: list[KnowledgeItem]) -> None:
        """Build the vector index from a list of knowledge items.

        Computes embedding vectors for all items and stores them for
        subsequent similarity searches.

        Args:
            items: Knowledge items to index.  An empty list results in an
                empty (but valid) index.
        """
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
        """Find the top-k most similar items to a query vector.

        Args:
            query_vec: A 1-D embedding vector for the query.
            top_k: Maximum number of results to return.

        Returns:
            A list of ``(item_index, cosine_similarity)`` tuples sorted in
            descending order of similarity.  May contain fewer than *top_k*
            entries if the index is smaller.
        """
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
        """Retrieve a knowledge item by its positional index.

        Args:
            index: Zero-based index into the stored items list.

        Returns:
            The :class:`KnowledgeItem` at the given position.

        Raises:
            IndexError: If *index* is out of range.
        """
        return self._items[index]


# ===================================================================
#  Semantic Detector
# ===================================================================


def _split_into_segments(text: str, max_len: int = 120) -> list[str]:
    """Split long text into sentence-level segments for granular matching.

    If *text* is shorter than *max_len* it is returned as a single-element
    list.  Otherwise the text is split on common sentence-ending punctuation
    (periods, exclamation marks, question marks, semicolons, and CJK
    equivalents) and consecutive short fragments are merged until each
    segment approaches *max_len*.

    Args:
        text: The input text to segment.
        max_len: Soft maximum character length for each segment.

    Returns:
        A non-empty list of text segments.
    """
    if len(text) <= max_len:
        return [text]
    # Split by common sentence delimiters (English and Chinese)
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
    Semantic-level privacy detector.

    Uses an embedding vector index to detect whether output text semantically
    matches private knowledge. Serves as a supplementary layer to keyword/regex
    matching.

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
        """Initialise the semantic detector.

        Args:
            provider: Either a provider name string (``"openai"``,
                ``"local"``, or ``"ngram"``) or a pre-instantiated
                :class:`EmbeddingProvider` instance.
            threshold: Cosine similarity threshold above which a match is
                considered a privacy hit.
            top_k: Number of nearest neighbours to retrieve per query
                segment.
            **provider_kwargs: Extra keyword arguments forwarded to the
                provider constructor when *provider* is a string.
        """
        if isinstance(provider, str):
            self._provider = _create_provider(provider, **provider_kwargs)
        else:
            self._provider = provider
        self.threshold = threshold
        self.top_k = top_k
        self._index: Optional[PrivacyVectorIndex] = None

    @property
    def provider(self) -> EmbeddingProvider:
        """Return the embedding provider used by this detector."""
        return self._provider

    @property
    def index(self) -> Optional[PrivacyVectorIndex]:
        """Return the current vector index, or ``None`` if not yet built."""
        return self._index

    def build_index(self, private_items: list[KnowledgeItem]) -> int:
        """Build a vector index from private knowledge items.

        Only items whose category is in
        :data:`~memgate.knowledge_store.ALWAYS_PRIVATE_CATEGORIES` are
        indexed.

        Args:
            private_items: List of :class:`KnowledgeItem` instances to
                consider for indexing.

        Returns:
            The number of items actually indexed.
        """
        items = [it for it in private_items if it.category in ALWAYS_PRIVATE_CATEGORIES]
        self._index = PrivacyVectorIndex(self._provider)
        self._index.build(items)
        return self._index.size

    def build_index_from_store(
        self, store: KnowledgeStore, users: Optional[list[str]] = None
    ) -> int:
        """Build the vector index from a :class:`KnowledgeStore`.

        Collects all private items for the specified users (or all users
        if *users* is ``None``) and delegates to :meth:`build_index`.

        Args:
            store: The knowledge store to read items from.
            users: Optional list of user identifiers to include.  When
                ``None``, all users in the store are included.

        Returns:
            The number of items indexed.
        """
        if users is None:
            users = store.list_users()
        all_private: list[KnowledgeItem] = []
        for user in users:
            all_private.extend(store.get_private(user))
        return self.build_index(all_private)

    def detect(self, text: str) -> SemanticResult:
        """Detect whether *text* semantically matches any private knowledge.

        The text is split into segments, each segment is embedded and
        compared against the vector index.  Matches exceeding the
        similarity threshold are collected and returned.

        Args:
            text: The output text to scan for privacy leaks.

        Returns:
            A :class:`SemanticResult` indicating whether any private
            knowledge was matched, along with detailed hit information.
        """
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


# ===================================================================
#  Provider Factory
# ===================================================================


def _create_provider(name: str, **kwargs) -> EmbeddingProvider:
    """Instantiate an embedding provider by name.

    Args:
        name: Provider identifier — one of ``"openai"``, ``"local"``, or
            ``"ngram"`` (case-insensitive).
        **kwargs: Additional keyword arguments forwarded to the provider
            constructor.

    Returns:
        An :class:`EmbeddingProvider` instance.

    Raises:
        ValueError: If *name* does not match any known provider.
    """
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


# ===================================================================
#  CLI
# ===================================================================

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
