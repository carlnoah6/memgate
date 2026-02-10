#!/usr/bin/env python3
"""
Privacy Guard — 上下文隔离引擎

决定当前 session 可以访问哪些知识。
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))
from knowledge_store import KnowledgeStore, KnowledgeItem, KNOWLEDGE_DIR


PRIVACY_DIR = Path(__file__).parent.parent / "privacy"
CONFIG_PATH = PRIVACY_DIR / "config.json"


@dataclass
class ChannelInfo:
    """频道信息"""
    channel_id: str
    participants: set  # set of user IDs
    channel_type: str  # "dm" or "group"

    @property
    def is_private(self) -> bool:
        return len(self.participants) <= 1


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {"enabled": True, "defaults": {"visibility": "private"}}


class PrivacyContext:
    """
    隐私上下文：决定当前 session 可以访问哪些知识
    
    核心规则：
    1. 私聊（1人）→ 该用户的所有知识（public + private）
    2. 群聊（多人）→ 所有参与者的 public 知识
    3. 同用户不同频道 → 信息互通（只要参与者集合相同）
    """

    def __init__(self, channel: ChannelInfo, store: Optional[KnowledgeStore] = None):
        self.channel = channel
        self.store = store or KnowledgeStore()
        self.config = load_config()

    @property
    def is_private(self) -> bool:
        return self.channel.is_private

    @property
    def participants(self) -> set:
        return self.channel.participants

    def get_accessible_knowledge(self) -> list[KnowledgeItem]:
        """返回当前 session 可访问的知识条目"""
        if not self.config.get("enabled", True):
            # Privacy disabled: return everything
            result = []
            for user in self.store.list_users():
                result.extend(self.store.get_all(user))
            return result

        if self.is_private:
            # 私聊：该用户的所有知识
            user = list(self.participants)[0]
            return self.store.get_all(user)
        else:
            # 群聊：所有参与者的 public 知识
            result = []
            for user in self.participants:
                result.extend(self.store.get_public(user))
            return result

    def can_access_item(self, item: KnowledgeItem) -> bool:
        """检查当前上下文是否可以访问某条知识"""
        if not self.config.get("enabled", True):
            return True

        if self.is_private:
            user = list(self.participants)[0]
            return item.user == user
        else:
            # 群聊：只能访问参与者的 public 知识
            if item.user not in self.participants:
                return False
            return item.visibility == "public"

    def get_accessible_paths(self) -> set[str]:
        """返回可访问的文件路径集合（用于过滤 memory_search 结果）"""
        paths = set()

        if self.is_private:
            user = list(self.participants)[0]
            user_dir = self.store.base_dir / user
            paths.add(str(user_dir / "public.jsonl"))
            paths.add(str(user_dir / "private.jsonl"))
        else:
            for user in self.participants:
                user_dir = self.store.base_dir / user
                paths.add(str(user_dir / "public.jsonl"))
                # NOT private.jsonl in group context

        return paths

    def filter_memory_results(self, results: list[dict]) -> list[dict]:
        """
        过滤 memory_search 结果
        
        results: list of {path: str, content: str, ...}
        """
        if not self.config.get("enabled", True):
            return results

        accessible = self.get_accessible_paths()
        return [r for r in results if r.get("path", "") in accessible]

    def get_context_summary(self) -> str:
        """生成上下文摘要（注入到 session prompt 中）"""
        if self.is_private:
            user = list(self.participants)[0]
            return f"[Privacy] 私聊模式 (用户: {user}) — 可访问该用户的所有知识"
        else:
            users = ", ".join(sorted(self.participants))
            return (
                f"[Privacy] 群聊模式 (参与者: {users}) — "
                f"只能使用参与者的公共知识，不能泄露任何人的私有信息"
            )
