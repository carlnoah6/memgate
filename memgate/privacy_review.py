#!/usr/bin/env python3
"""
Privacy Guard — 输出审查器

发送前检测消息是否包含隐私泄露。
支持开关控制（config.review.enabled）。
"""

import json
import re
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from .knowledge_store import KnowledgeStore, ALWAYS_PRIVATE_CATEGORIES

# Lazy import to avoid hard dependency on numpy when semantic is disabled
_SemanticDetector = None


def _get_semantic_detector():
    global _SemanticDetector
    if _SemanticDetector is None:
        try:
            from .semantic_detector import SemanticDetector

            _SemanticDetector = SemanticDetector
        except ImportError:
            _SemanticDetector = False  # mark as unavailable
    return _SemanticDetector if _SemanticDetector is not False else None


# Data directory configuration
DEFAULT_PRIVACY_DIR = Path.home() / ".openclaw" / "workspace" / "privacy"
PRIVACY_DIR = Path(os.getenv("MEMGATE_DATA_DIR", DEFAULT_PRIVACY_DIR))
CONFIG_PATH = PRIVACY_DIR / "config.json"
PATTERNS_DIR = PRIVACY_DIR / "patterns"


@dataclass
class Violation:
    """一个违规项"""

    category: str  # e.g. "calendar", "family"
    matched: str  # matched text
    description: str  # human-readable description


@dataclass
class ReviewResult:
    """审查结果"""

    passed: bool
    message: Optional[str] = None
    violations: list = field(default_factory=list)
    suggestion: Optional[str] = None


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {"review": {"enabled": True}}


def load_patterns() -> dict:
    """加载隐私检测模式"""
    default_patterns = {
        "calendar": {
            "description": "日程/日历信息",
            "patterns": [
                r"明天.*[去见约]",
                r"今天.*[去见约]",
                r"昨天.*[去见约]",
                r"\d{1,2}[:.]\d{2}.*[去见约到]",
                r"(上午|下午|晚上|早上)\d{1,2}[点时]",
                r"日程|行程|安排|预约|航班",
                r"schedule|appointment|meeting.*at|tomorrow.*at",
            ],
        },
        "family": {
            "description": "家庭成员信息",
            "patterns": [
                # These will be populated from user's knowledge store
            ],
        },
        "finance": {
            "description": "财务信息",
            "patterns": [
                r"工资|薪水|月薪|年薪|收入",
                r"投资.*\d|账户.*余额|信用卡.*\d",
                r"(my|your|his|her|the)\s+salary|salary\s+(is|of|was)",
                r"(my|your|his|her|the)\s+income|income\s+(is|of|was)",
                r"balance\s+(is|of)|investment.*\$",
            ],
        },
        "contact_private": {
            "description": "私人联系方式",
            "patterns": [
                r"\d{8,11}",  # phone numbers
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # email
                r"住在|地址[是为]|家在",
                r"address\s+(is|at)|live\s+at|located\s+at",
            ],
        },
    }

    # Load custom patterns if exist
    custom_path = PATTERNS_DIR / "default.json"
    if custom_path.exists():
        try:
            with open(custom_path) as f:
                custom = json.load(f)
                for cat, data in custom.items():
                    if cat in default_patterns:
                        default_patterns[cat]["patterns"].extend(
                            data.get("patterns", [])
                        )
                    else:
                        default_patterns[cat] = data
        except (json.JSONDecodeError, KeyError):
            pass

    return default_patterns


class PrivacyReviewer:
    """
    发送前审查消息，检测隐私泄露

    三层检测：
    1. 规则匹配（快速、确定性）— 检查已知的私有信息模式
    2. 用户实体匹配 — 检查是否提及了其他用户的私有实体（名字、地点等）
    3. 语义匹配（embedding）— 检测改述/间接描述的隐私泄露

    可通过 config.review.enabled 开关控制。
    语义检测通过 config.review.semantic.enabled 独立控制。
    """

    def __init__(
        self,
        config: Optional[dict] = None,
        store: Optional[KnowledgeStore] = None,
        semantic_detector=None,
    ):
        self.config = config or load_config()
        self.store = store or KnowledgeStore()
        self.patterns = load_patterns()

        review_config = self.config.get("review", {})
        self.enabled = review_config.get("enabled", True)
        self.block_on_violation = review_config.get("block_on_violation", True)

        # ── 语义检测层 ──
        semantic_config = review_config.get("semantic", {})
        self.semantic_enabled = semantic_config.get("enabled", True)

        if semantic_detector is not None:
            # Injected (e.g. for testing)
            self._semantic = semantic_detector
        elif self.semantic_enabled:
            SemanticDetectorCls = _get_semantic_detector()
            if SemanticDetectorCls is not None:
                provider = semantic_config.get("provider", "ngram")
                threshold = semantic_config.get("threshold", 0.55)
                self._semantic = SemanticDetectorCls(
                    provider=provider, threshold=threshold
                )
            else:
                self._semantic = None
                self.semantic_enabled = False
        else:
            self._semantic = None

        self._semantic_index_built = False

    def _check_patterns(self, message: str) -> list[Violation]:
        """规则匹配检查"""
        violations = []
        for category, data in self.patterns.items():
            if category not in ALWAYS_PRIVATE_CATEGORIES:
                continue  # Only check always-private categories
            for pattern in data.get("patterns", []):
                try:
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match:
                        violations.append(
                            Violation(
                                category=category,
                                matched=match.group(),
                                description=f"检测到{data.get('description', category)}信息",
                            )
                        )
                        break  # One violation per category is enough
                except re.error:
                    continue
        return violations

    # Common words / stopwords to ignore in entity matching
    _STOPWORDS = {
        "的",
        "是",
        "在",
        "了",
        "和",
        "有",
        "不",
        "人",
        "都",
        "一",
        "到",
        "会",
        "上",
        "这",
        "个",
        "他",
        "她",
        "我",
        "你",
        "他们",
        "我们",
        "与",
        "也",
        "就",
        "但",
        "对",
        "把",
        "去",
        "来",
        "很",
        "要",
        "能",
        "可以",
        "没有",
        "所以",
        "因为",
        "如果",
        "from",
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "not",
        "are",
        "was",
        "has",
        "have",
        "been",
        "will",
    }

    def _check_private_entities(
        self, message: str, sender: str, participants: set
    ) -> list[Violation]:
        """检查是否提及了私有实体（从知识库加载）"""
        violations = []
        seen_categories = set()

        # For each participant, check if their private knowledge entities appear
        for user in participants:
            private_items = self.store.get_private(user)
            for item in private_items:
                if item.category in seen_categories:
                    continue  # One violation per category is enough
                content_snippets = []
                for s in item.content.split():
                    s = s.strip("，。、：；！？()（）\"'")
                    if not s or s.lower() in self._STOPWORDS:
                        continue
                    is_cjk = any("\u4e00" <= c <= "\u9fff" for c in s)
                    min_len = 4 if is_cjk else 6
                    if len(s) >= min_len:
                        content_snippets.append(s)
                for snippet in content_snippets:
                    if snippet in message:
                        violations.append(
                            Violation(
                                category=item.category,
                                matched=snippet,
                                description=f"提及了 {user} 的私有{item.category}信息",
                            )
                        )
                        seen_categories.add(item.category)
                        break

        return violations

    def _ensure_semantic_index(self, participants: set) -> None:
        """确保语义检测索引已构建（惰性构建）"""
        if not self.semantic_enabled or self._semantic is None:
            return
        if self._semantic_index_built:
            return
        all_private = []
        for user in participants:
            all_private.extend(self.store.get_private(user))
        if all_private:
            self._semantic.build_index(all_private)
        self._semantic_index_built = True

    def _check_semantic(self, message: str, participants: set) -> list[Violation]:
        """语义相似度检测 (Layer 3)"""
        if not self.semantic_enabled or self._semantic is None:
            return []

        self._ensure_semantic_index(participants)

        result = self._semantic.detect(message)
        if not result.flagged:
            return []

        violations = []
        seen_categories = set()
        for hit in result.hits:
            if hit.category in seen_categories:
                continue
            violations.append(
                Violation(
                    category=hit.category,
                    matched=f"[语义匹配 sim={hit.similarity:.2f}] {hit.matched_content[:60]}",
                    description=f"语义检测到与私有{hit.category}信息高度相似的内容",
                )
            )
            seen_categories.add(hit.category)

        return violations

    def review(
        self, message: str, channel_id: str, participants: set, sender: str = ""
    ) -> ReviewResult:
        """
        审查消息

        Args:
            message: 待发送的消息
            channel_id: 目标频道
            participants: 频道参与者集合
            sender: 消息发送者（通常是 assistant）

        Returns:
            ReviewResult: 审查结果
        """
        # Disabled → always pass
        if not self.enabled:
            return ReviewResult(passed=True, message=message)

        # Private channel (1 person) → no review needed
        if len(participants) <= 1:
            return ReviewResult(passed=True, message=message)

        # ── Layer 1: Pattern matching ──
        violations = self._check_patterns(message)

        # ── Layer 2: Private entity matching ──
        entity_violations = self._check_private_entities(message, sender, participants)
        violations.extend(entity_violations)

        # ── Layer 3: Semantic similarity detection ──
        # Only run if Layer 1+2 didn't already flag the message
        if not violations:
            semantic_violations = self._check_semantic(message, participants)
            violations.extend(semantic_violations)

        if violations:
            return ReviewResult(
                passed=False,
                violations=violations,
                suggestion="消息包含私有信息，应移除后重新生成",
            )

        return ReviewResult(passed=True, message=message)

    def get_status(self) -> dict:
        """返回审查器状态"""
        return {
            "enabled": self.enabled,
            "block_on_violation": self.block_on_violation,
            "pattern_categories": list(self.patterns.keys()),
            "users_with_knowledge": self.store.list_users(),
            "semantic": {
                "enabled": self.semantic_enabled,
                "provider": (
                    type(self._semantic.provider).__name__ if self._semantic else None
                ),
                "index_built": self._semantic_index_built,
                "index_size": (
                    self._semantic.index.size
                    if (self._semantic and self._semantic.index)
                    else 0
                ),
            },
        }
