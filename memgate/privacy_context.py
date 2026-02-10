#!/usr/bin/env python3
"""
Privacy Guard — Context Isolation Engine

Determines which knowledge the current session can access.
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .knowledge_store import KnowledgeStore, KnowledgeItem


PRIVACY_DIR = Path(__file__).parent.parent / "privacy"
CONFIG_PATH = PRIVACY_DIR / "config.json"


@dataclass
class ChannelInfo:
    """Channel information."""

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
    Privacy context: determines which knowledge the current session can access.

    Core rules:
    1. DM (1 person) -> All of the user's knowledge (public + private)
    2. Group chat (multiple people) -> All participants' public knowledge only
    3. Same user, different channels -> Knowledge is shared (as long as participant sets match)
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
        """Return knowledge entries accessible to the current session."""
        if not self.config.get("enabled", True):
            # Privacy disabled: return everything
            result = []
            for user in self.store.list_users():
                result.extend(self.store.get_all(user))
            return result

        if self.is_private:
            # DM: all knowledge for this user
            user = list(self.participants)[0]
            return self.store.get_all(user)
        else:
            # Group chat: public knowledge from all participants
            result = []
            for user in self.participants:
                result.extend(self.store.get_public(user))
            return result

    def can_access_item(self, item: KnowledgeItem) -> bool:
        """Check whether the current context can access a given knowledge item."""
        if not self.config.get("enabled", True):
            return True

        if self.is_private:
            user = list(self.participants)[0]
            return item.user == user
        else:
            # Group chat: can only access participants' public knowledge
            if item.user not in self.participants:
                return False
            return item.visibility == "public"

    def get_accessible_paths(self) -> set[str]:
        """Return the set of accessible file paths (for filtering memory_search results)."""
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
        Filter memory_search results.

        results: list of {path: str, content: str, ...}
        """
        if not self.config.get("enabled", True):
            return results

        accessible = self.get_accessible_paths()
        return [r for r in results if r.get("path", "") in accessible]

    def get_context_summary(self) -> str:
        """Generate a context summary (for injection into the session prompt)."""
        if self.is_private:
            user = list(self.participants)[0]
            return f"[Privacy] DM mode (user: {user}) — can access all of this user's knowledge"
        else:
            users = ", ".join(sorted(self.participants))
            return (
                f"[Privacy] Group chat mode (participants: {users}) — "
                f"can only use participants' public knowledge; must not leak anyone's private information"
            )
