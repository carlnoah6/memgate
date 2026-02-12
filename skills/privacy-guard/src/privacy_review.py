#!/usr/bin/env python3
"""
Privacy Guard — 输出审查器

发送前检测消息是否包含隐私泄露。
支持开关控制（config.review.enabled）。
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from knowledge_store import KnowledgeStore, ALWAYS_PRIVATE_CATEGORIES


PRIVACY_DIR = Path(__file__).parent
CONFIG_PATH = PRIVACY_DIR / "config.json"
PATTERNS_DIR = PRIVACY_DIR / "patterns"


@dataclass
class Violation:
    """一个违规项"""
    category: str       # e.g. "calendar", "family"
    matched: str        # matched text
    description: str    # human-readable description


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
                r"明天.*[去见约]", r"今天.*[去见约]", r"昨天.*[去见约]",
                r"\d{1,2}[:.]\d{2}.*[去见约到]",
                r"(上午|下午|晚上|早上)\d{1,2}[点时]",
                r"日程|行程|安排|预约|航班",
                r"schedule|appointment|meeting at",
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
                r"salary|income|balance|investment.*\$",
            ],
        },
        "contact_private": {
            "description": "私人联系方式",
            "patterns": [
                r"\d{8,11}",  # phone numbers
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # email
                r"住在|地址[是为]|家在",
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
                        default_patterns[cat]["patterns"].extend(data.get("patterns", []))
                    else:
                        default_patterns[cat] = data
        except (json.JSONDecodeError, KeyError):
            pass

    return default_patterns


class PrivacyReviewer:
    """
    发送前审查消息，检测隐私泄露
    
    两层检测：
    1. 规则匹配（快速、确定性）— 检查已知的私有信息模式
    2. 用户实体匹配 — 检查是否提及了其他用户的私有实体（名字、地点等）
    
    可通过 config.review.enabled 开关控制。
    """

    def __init__(self, config: Optional[dict] = None,
                 store: Optional[KnowledgeStore] = None):
        self.config = config or load_config()
        self.store = store or KnowledgeStore()
        self.patterns = load_patterns()

        review_config = self.config.get("review", {})
        self.enabled = review_config.get("enabled", True)
        self.block_on_violation = review_config.get("block_on_violation", True)

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
                        violations.append(Violation(
                            category=category,
                            matched=match.group(),
                            description=f"检测到{data.get('description', category)}信息"
                        ))
                        break  # One violation per category is enough
                except re.error:
                    continue
        return violations

    def _check_private_entities(self, message: str,
                                 sender: str,
                                 participants: set) -> list[Violation]:
        """检查是否提及了私有实体（从知识库加载）"""
        violations = []

        # For each participant, check if their private knowledge entities appear
        for user in participants:
            private_items = self.store.get_private(user)
            for item in private_items:
                # Check if private knowledge content appears in message
                # Only check substantive content (>3 chars to avoid false positives)
                content_snippets = [
                    s.strip() for s in item.content.split()
                    if len(s.strip()) > 3
                ]
                for snippet in content_snippets:
                    if snippet in message:
                        violations.append(Violation(
                            category=item.category,
                            matched=snippet,
                            description=f"提及了 {user} 的私有{item.category}信息"
                        ))
                        break

        return violations

    def review(self, message: str, channel_id: str,
               participants: set, sender: str = "") -> ReviewResult:
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
        entity_violations = self._check_private_entities(
            message, sender, participants)
        violations.extend(entity_violations)

        if violations:
            return ReviewResult(
                passed=False,
                violations=violations,
                suggestion="消息包含私有信息，应移除后重新生成"
            )

        return ReviewResult(passed=True, message=message)

    def get_status(self) -> dict:
        """返回审查器状态"""
        return {
            "enabled": self.enabled,
            "block_on_violation": self.block_on_violation,
            "pattern_categories": list(self.patterns.keys()),
            "users_with_knowledge": self.store.list_users(),
        }
