#!/usr/bin/env python3
"""
Privacy Guard — Knowledge Storage and Tagging Module

Each knowledge entry is stored in JSONL format with public/private visibility tags.
"""

import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

# Data directory configuration
# Priority: Env Var > Default Workspace Path
DEFAULT_PRIVACY_DIR = Path.home() / ".openclaw" / "workspace" / "privacy"
PRIVACY_DIR = Path(os.getenv("MEMGATE_DATA_DIR", DEFAULT_PRIVACY_DIR))
KNOWLEDGE_DIR = PRIVACY_DIR / "knowledge"

SGT = timezone(timedelta(hours=8))


@dataclass
class KnowledgeItem:
    """A single knowledge item."""

    id: str
    user: str
    content: str
    visibility: str  # "public" | "private"
    category: str  # "skill", "preference", "calendar", "family", "finance", etc.
    source: str  # "user_declared", "calendar_sync", "group_chat:channel_id", "dm", etc.
    created: str  # ISO 8601
    tags: list = field(default_factory=list)
    channel_scope: Optional[str] = (
        None  # if from group chat, only visible in that group
    )

    def to_dict(self):
        d = asdict(self)
        # Remove None values
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeItem":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            user=d["user"],
            content=d["content"],
            visibility=d.get("visibility", "private"),
            category=d.get("category", "general"),
            source=d.get("source", "unknown"),
            created=d.get("created", datetime.now(SGT).isoformat()),
            tags=d.get("tags", []),
            channel_scope=d.get("channel_scope"),
        )


# Categories that are ALWAYS private, regardless of user tagging
ALWAYS_PRIVATE_CATEGORIES = {
    "calendar",
    "family",
    "finance",
    "health",
    "auth",
    "contact_private",
    "dm_content",
}


class KnowledgeTagger:
    """Classifies knowledge entries as public/private."""

    # Category detection patterns
    # KEEP Chinese characters inside these patterns as they are functional regex/keywords
    CATEGORY_PATTERNS = {
        "calendar": [
            "日程",
            "日历",
            "约了",
            "见了",
            "去了",
            "行程",
            "预约",
            "航班",
            "会议",
            "开会",
            "下周",
            "上周",
            "明天",
            "后天",
            "schedule",
            "calendar",
            "meeting",
            "appointment",
        ],
        "family": [
            "孩子",
            "儿子",
            "女儿",
            "老婆",
            "太太",
            "妻子",
            "爸",
            "妈",
            "child",
            "son",
            "daughter",
            "wife",
            "husband",
            "family",
        ],
        "finance": [
            "工资",
            "薪水",
            "投资",
            "账户",
            "余额",
            "贷款",
            "信用卡",
            "salary",
            "investment",
            "account",
            "balance",
            "loan",
        ],
        "health": [
            "看医生",
            "体检",
            "生病",
            "药",
            "手术",
            "诊所",
            "doctor",
            "hospital",
            "medicine",
            "health",
        ],
        "auth": ["密码", "password", "api_key", "token", "secret", "credential"],
        "contact_private": [
            "电话",
            "手机号",
            "地址",
            "住在",
            "身份证",
            "phone",
            "address",
            "ID number",
        ],
        "skill": [
            "会",
            "擅长",
            "精通",
            "学过",
            "技能",
            "know",
            "skilled",
            "proficient",
            "experience with",
        ],
        "preference": [
            "喜欢",
            "偏好",
            "习惯",
            "爱好",
            "like",
            "prefer",
            "hobby",
            "favorite",
        ],
    }

    def detect_category(self, content: str) -> str:
        """Detect the category of the content."""
        content_lower = content.lower()
        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern in content_lower:
                    return category
        return "general"

    def classify(
        self, content: str, source: str = "unknown", user_override: Optional[str] = None
    ) -> str:
        """
        Returns 'public' or 'private'.

        user_override: User's explicit visibility override.
        """
        # User explicit override (but cannot override always-private)
        category = self.detect_category(content)

        # Always private categories cannot be made public
        if category in ALWAYS_PRIVATE_CATEGORIES:
            return "private"

        # User explicit override
        if user_override == "public":
            return "public"
        if user_override == "private":
            return "private"

        # Check for #public tag in content
        if "#public" in content:
            return "public"

        # Content shared in group chat = public within that group
        if source.startswith("group:"):
            return "public"

        # Default: private
        return "private"


class KnowledgeStore:
    """Knowledge store (JSONL files)."""

    def __init__(self, base_dir: Path = KNOWLEDGE_DIR):
        self.base_dir = base_dir

    def _user_dir(self, user: str) -> Path:
        d = self.base_dir / user
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_file(self, path: Path) -> list[KnowledgeItem]:
        items = []
        if not path.exists():
            return items
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(KnowledgeItem.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
        return items

    def _append_item(self, path: Path, item: KnowledgeItem):
        with open(path, "a") as f:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

    def add(self, item: KnowledgeItem) -> KnowledgeItem:
        """Add a knowledge item."""
        if not item.id:
            item.id = f"k_{uuid.uuid4().hex[:8]}"

        # Force always-private categories
        if item.category in ALWAYS_PRIVATE_CATEGORIES:
            item.visibility = "private"

        filename = f"{item.visibility}.jsonl"
        path = self._user_dir(item.user) / filename
        self._append_item(path, item)
        return item

    def get_public(self, user: str) -> list[KnowledgeItem]:
        """Get a user's public knowledge."""
        return self._load_file(self._user_dir(user) / "public.jsonl")

    def get_private(self, user: str) -> list[KnowledgeItem]:
        """Get a user's private knowledge."""
        return self._load_file(self._user_dir(user) / "private.jsonl")

    def get_all(self, user: str) -> list[KnowledgeItem]:
        """Get all knowledge for a user."""
        return self.get_public(user) + self.get_private(user)

    def list_users(self) -> list[str]:
        """List all users."""
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]
