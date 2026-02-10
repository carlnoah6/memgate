#!/usr/bin/env python3
"""
Tests for Provider layer — LarkProvider with mocked Lark API responses.

Covers:
- Normal private chat (admin + bot only)
- Group chat with multiple humans
- Paranoid Check: hidden members (expected > actual)
- Paranoid Check: member_count=0 edge case
- External user invisible to bot (the original bug)
- is_safe() correctly combines privacy + integrity checks
"""

import unittest
from unittest.mock import patch

from memgate.providers.base import BaseProvider, ProviderContext
from memgate.providers.lark import LarkProvider


def _make_provider(**kwargs):
    """Create a LarkProvider with fake credentials (API calls will be mocked)."""
    defaults = {
        "app_id": "fake_app_id",
        "app_secret": "fake_app_secret",
        "admin_open_id": "ou_admin_alice",
    }
    defaults.update(kwargs)
    return LarkProvider(**defaults)


def _mock_chat_info(member_count: int):
    """Mock response for GET /im/v1/chats/{chat_id}."""
    return {"member_count": str(member_count)}


def _mock_members(*members):
    """
    Mock response for GET /im/v1/chats/{chat_id}/members.
    Each member is a tuple: (member_id, name, member_type?)
    member_type defaults to None (user).
    """
    items = []
    for m in members:
        item = {"member_id": m[0], "name": m[1]}
        if len(m) > 2 and m[2]:
            item["member_type"] = m[2]
        items.append(item)
    return items


class TestProviderContext(unittest.TestCase):
    """Test ProviderContext data class."""

    def test_context_creation(self):
        ctx = ProviderContext(
            chat_id="test",
            is_private=True,
            participants={"user_a"},
            channel_type="dm",
            reason="test",
        )
        self.assertTrue(ctx.is_private)
        self.assertIsNone(ctx.unsafe_reason)

    def test_context_with_unsafe_reason(self):
        ctx = ProviderContext(
            chat_id="test",
            is_private=True,
            participants={"user_a"},
            channel_type="dm",
            reason="test",
            unsafe_reason="Hidden users detected",
        )
        self.assertIsNotNone(ctx.unsafe_reason)


class TestLarkProviderConfig(unittest.TestCase):
    """Test LarkProvider configuration loading."""

    def test_explicit_credentials(self):
        provider = _make_provider()
        self.assertEqual(provider.config["app_id"], "fake_app_id")
        self.assertEqual(provider.config["app_secret"], "fake_app_secret")

    def test_missing_credentials_raises(self):
        with self.assertRaises(ValueError):
            LarkProvider(app_id=None, app_secret=None)


class TestLarkProviderPrivacyDetection(unittest.TestCase):
    """Test fetch_context + is_safe with mocked API responses."""

    def _run_fetch(self, provider, chat_id, chat_info, members, bot_id="ou_bot_luna"):
        """Run fetch_context with mocked API calls."""
        with patch.object(
            provider, "_get_tenant_token", return_value="fake_token"
        ), patch.object(
            provider, "_get_bot_open_id", return_value=bot_id
        ), patch.object(
            provider, "_get_chat_info", return_value=chat_info
        ), patch.object(provider, "_get_group_members", return_value=members):
            return provider.fetch_context(chat_id)

    def test_private_chat_admin_and_bot(self):
        """Only admin + bot → private and safe."""
        provider = _make_provider()
        ctx = self._run_fetch(
            provider,
            "oc_private",
            _mock_chat_info(2),
            _mock_members(
                ("ou_admin_alice", "Alice"),
                ("ou_bot_luna", "Luna", "bot"),
            ),
        )
        self.assertTrue(ctx.is_private)
        self.assertEqual(ctx.channel_type, "dm")
        self.assertIsNone(ctx.unsafe_reason)
        self.assertTrue(provider.is_safe(ctx))

    def test_group_chat_multiple_humans(self):
        """Admin + other humans → group, not safe for private data."""
        provider = _make_provider()
        ctx = self._run_fetch(
            provider,
            "oc_group",
            _mock_chat_info(3),
            _mock_members(
                ("ou_admin_alice", "Alice"),
                ("ou_other_user", "Alice"),
                ("ou_bot_luna", "Luna", "bot"),
            ),
        )
        self.assertFalse(ctx.is_private)
        self.assertEqual(ctx.channel_type, "group")
        self.assertIsNone(ctx.unsafe_reason)
        # is_safe should be False because it's not private
        self.assertFalse(provider.is_safe(ctx))

    def test_paranoid_check_hidden_members(self):
        """
        Chat claims 3 members but API only returns 2.
        This is the ORIGINAL BUG: external user invisible to bot.
        Must be marked UNSAFE.
        """
        provider = _make_provider()
        ctx = self._run_fetch(
            provider,
            "oc_hidden_user",
            _mock_chat_info(3),  # Chat says 3 members
            _mock_members(  # But API only shows 2
                ("ou_admin_alice", "Alice"),
                ("ou_bot_luna", "Luna", "bot"),
            ),
        )
        # Even though visible members suggest private, paranoid check catches it
        self.assertIsNotNone(ctx.unsafe_reason)
        self.assertIn("Inconsistency", ctx.unsafe_reason)
        self.assertFalse(provider.is_safe(ctx))

    def test_paranoid_check_member_count_zero(self):
        """
        API returns member_count=0 but we can see members.
        This is unreliable data — must be marked UNSAFE.
        """
        provider = _make_provider()
        ctx = self._run_fetch(
            provider,
            "oc_zero_count",
            _mock_chat_info(0),  # Unreliable: claims 0
            _mock_members(
                ("ou_admin_alice", "Alice"),
                ("ou_bot_luna", "Luna", "bot"),
            ),
        )
        self.assertIsNotNone(ctx.unsafe_reason)
        self.assertIn("Unreliable", ctx.unsafe_reason)
        self.assertFalse(provider.is_safe(ctx))

    def test_same_name_different_user_bug(self):
        """
        REGRESSION TEST for the 2026-02-11 bug:
        Group has admin "Alice", user "Luna" (human), and bot "Luna" (bot).
        The bot and the user share the same name.
        Must correctly identify the human Luna as a non-bot participant.
        """
        provider = _make_provider()
        ctx = self._run_fetch(
            provider,
            "oc_same_name",
            _mock_chat_info(3),
            _mock_members(
                ("ou_admin_alice", "Alice"),
                ("ou_human_luna", "Luna"),  # Human user named Luna
                ("ou_bot_luna", "Luna", "bot"),  # Bot also named Luna
            ),
        )
        # Should detect that there's a non-admin human
        self.assertFalse(ctx.is_private)
        self.assertEqual(ctx.channel_type, "group")
        # ou_human_luna should be in participants
        self.assertIn("ou_human_luna", ctx.participants)
        # Bot should NOT be in participants
        self.assertNotIn("ou_bot_luna", ctx.participants)
        # Not safe for private data
        self.assertFalse(provider.is_safe(ctx))

    def test_same_name_hidden_user_bug(self):
        """
        REGRESSION TEST for the EXACT scenario that triggered the bug:
        Chat has 3 entities (Alice, human Luna, bot Luna).
        But API only returns Alice (human Luna is external/invisible).
        member_count=3 but we only see Alice + bot = 2 items, or
        API might not even return the bot.

        The paranoid check must catch this.
        """
        provider = _make_provider()
        # Scenario: API returns only Alice (1 item), chat claims 3
        ctx = self._run_fetch(
            provider,
            "oc_exact_bug",
            _mock_chat_info(3),  # Chat says 3
            _mock_members(  # API only returns 1
                ("ou_admin_alice", "Alice"),
            ),
        )
        self.assertIsNotNone(ctx.unsafe_reason)
        self.assertFalse(provider.is_safe(ctx))

    def test_bot_only_chat(self):
        """Edge case: only the bot in the chat (empty human list)."""
        provider = _make_provider()
        ctx = self._run_fetch(
            provider,
            "oc_bot_only",
            _mock_chat_info(1),
            _mock_members(
                ("ou_bot_luna", "Luna", "bot"),
            ),
        )
        # 0 humans → private
        self.assertTrue(ctx.is_private)
        self.assertTrue(provider.is_safe(ctx))

    def test_consistent_member_count(self):
        """When expected == actual, no paranoid check failure."""
        provider = _make_provider()
        ctx = self._run_fetch(
            provider,
            "oc_consistent",
            _mock_chat_info(2),
            _mock_members(
                ("ou_admin_alice", "Alice"),
                ("ou_bot_luna", "Luna", "bot"),
            ),
        )
        self.assertIsNone(ctx.unsafe_reason)


class TestBaseProviderInterface(unittest.TestCase):
    """Verify BaseProvider can't be instantiated directly."""

    def test_abstract_methods(self):
        with self.assertRaises(TypeError):
            BaseProvider()


if __name__ == "__main__":
    unittest.main()
