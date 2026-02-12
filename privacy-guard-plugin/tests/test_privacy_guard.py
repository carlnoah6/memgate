"""
Tests for Privacy Guard Plugin
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from privacy_guard import (
    PrivacyGuardPlugin,
    KnowledgeStore,
    PrivacyContext,
    PrivacyReviewer,
    ChannelInfo,
    KnowledgeItem,
)


@pytest.fixture
def temp_knowledge_dir():
    """Create temporary directory for knowledge storage"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_config(temp_knowledge_dir):
    """Sample plugin configuration"""
    return {
        "enabled": True,
        "review": {
            "enabled": True,
            "llm_self_review": False,
            "block_on_violation": True,
        },
        "knowledge_base": {
            "path": temp_knowledge_dir,
            "auto_tag": True,
        },
        "defaults": {
            "visibility": "private",
            "always_private_categories": [
                "calendar",
                "family",
                "finance",
                "health",
                "auth",
                "contact_private",
                "dm_content",
            ],
        },
    }


@pytest.fixture
def sample_knowledge_items():
    """Sample knowledge items for testing"""
    return [
        KnowledgeItem(
            id="k_001",
            user="carl",
            content="会 Python 编程",
            visibility="public",
            category="skill",
            source="test",
            created="2026-02-10T07:00:00+08:00",
        ),
        KnowledgeItem(
            id="k_002",
            user="carl",
            content="明天 14:00 要见马原",
            visibility="private",
            category="calendar",
            source="test",
            created="2026-02-10T07:00:00+08:00",
        ),
        KnowledgeItem(
            id="k_003",
            user="alex",
            content="喜欢喝咖啡",
            visibility="public",
            category="preference",
            source="test",
            created="2026-02-10T07:00:00+08:00",
        ),
        KnowledgeItem(
            id="k_004",
            user="alex",
            content="月薪 5000 元",
            visibility="private",
            category="finance",
            source="test",
            created="2026-02-10T07:00:00+08:00",
        ),
    ]


@pytest.fixture
def knowledge_store(temp_knowledge_dir, sample_knowledge_items):
    """Knowledge store with sample data"""
    store = KnowledgeStore(temp_knowledge_dir)
    for item in sample_knowledge_items:
        store.add(item)
    return store


class TestKnowledgeStore:
    """Test knowledge storage functionality"""

    def test_add_and_get_knowledge(self, knowledge_store):
        """Test adding and retrieving knowledge items"""
        items = knowledge_store.get_by_user("carl")
        assert len(items) == 2
        assert items[0].user == "carl"
        assert items[0].content == "会 Python 编程"

    def test_get_public_knowledge(self, knowledge_store):
        """Test retrieving only public knowledge"""
        public_items = knowledge_store.get_public_by_user("carl")
        assert len(public_items) == 1
        assert public_items[0].visibility == "public"
        assert public_items[0].content == "会 Python 编程"

    def test_list_users(self, knowledge_store):
        """Test listing users with knowledge"""
        users = knowledge_store.list_users()
        assert set(users) == {"carl", "alex"}

    def test_save_and_load(self, temp_knowledge_dir, sample_knowledge_items):
        """Test saving to and loading from filesystem"""
        # Create store and add items
        store1 = KnowledgeStore(temp_knowledge_dir)
        for item in sample_knowledge_items:
            store1.add(item)

        # Create new store and load from filesystem
        store2 = KnowledgeStore(temp_knowledge_dir)
        store2.load()

        # Verify data was saved and loaded correctly
        assert len(store2.get_by_user("carl")) == 2
        assert len(store2.get_by_user("alex")) == 2


class TestPrivacyContext:
    """Test context-based access control"""

    def test_private_chat_access(self, sample_config, knowledge_store):
        """Test private chat can access all knowledge"""
        channel = ChannelInfo(
            channel_id="dm_carl",
            participants={"carl"},
            channel_type="dm",
        )
        context = PrivacyContext(channel, sample_config, knowledge_store)

        assert context.is_private
        accessible = context.get_accessible_knowledge()
        assert len(accessible) == 2  # Both public and private
        assert all(item.user == "carl" for item in accessible)

    def test_group_chat_access(self, sample_config, knowledge_store):
        """Test group chat can only access public knowledge"""
        channel = ChannelInfo(
            channel_id="group_abc",
            participants={"carl", "alex"},
            channel_type="group",
        )
        context = PrivacyContext(channel, sample_config, knowledge_store)

        assert not context.is_private
        accessible = context.get_accessible_knowledge()
        assert len(accessible) == 2  # Only public items
        assert all(item.visibility == "public" for item in accessible)
        assert {item.user for item in accessible} == {"carl", "alex"}

    def test_can_access_item(self, sample_config, knowledge_store):
        """Test item access permission checking"""
        channel = ChannelInfo(
            channel_id="group_abc",
            participants={"carl", "alex"},
            channel_type="group",
        )
        context = PrivacyContext(channel, sample_config, knowledge_store)

        # Get sample items
        items = knowledge_store.get_all()
        public_item = next(i for i in items if i.visibility == "public")
        private_item = next(i for i in items if i.visibility == "private")

        # Public item should be accessible
        assert context.can_access_item(public_item)

        # Private item should not be accessible in group chat
        assert not context.can_access_item(private_item)

    def test_filter_memory_results(self, sample_config, knowledge_store):
        """Test filtering memory search results"""
        channel = ChannelInfo(
            channel_id="group_abc",
            participants={"carl", "alex"},
            channel_type="group",
        )
        context = PrivacyContext(channel, sample_config, knowledge_store)

        # Simulate memory search results
        results = [
            {"path": "carl/public.jsonl", "content": "会 Python 编程"},
            {"path": "carl/private.jsonl", "content": "明天 14:00 要见马原"},
            {"path": "alex/public.jsonl", "content": "喜欢喝咖啡"},
            {"path": "alex/private.jsonl", "content": "月薪 5000 元"},
            {"path": "other/public.jsonl", "content": "Other content"},
        ]

        filtered = context.filter_memory_results(results)
        assert len(filtered) == 2  # Only carl/public and alex/public
        assert filtered[0]["path"] == "carl/public.jsonl"
        assert filtered[1]["path"] == "alex/public.jsonl"

    def test_context_summary(self, sample_config, knowledge_store):
        """Test context summary generation"""
        # Private chat
        private_channel = ChannelInfo(
            channel_id="dm_carl",
            participants={"carl"},
            channel_type="dm",
        )
        private_context = PrivacyContext(private_channel, sample_config, knowledge_store)
        private_summary = private_context.get_context_summary()
        assert "Private chat" in private_summary
        assert "carl" in private_summary

        # Group chat
        group_channel = ChannelInfo(
            channel_id="group_abc",
            participants={"carl", "alex"},
            channel_type="group",
        )
        group_context = PrivacyContext(group_channel, sample_config, knowledge_store)
        group_summary = group_context.get_context_summary()
        assert "Group chat" in group_summary
        assert "carl, alex" in group_summary or "alex, carl" in group_summary


class TestPrivacyReviewer:
    """Test output review functionality"""

    def test_review_private_chat(self, sample_config, knowledge_store):
        """Test review allows all messages in private chat"""
        reviewer = PrivacyReviewer(sample_config, knowledge_store)
        result = reviewer.review(
            "明天 14:00 要见马原",
            "dm",
            {"carl"},
        )
        assert result.passed
        assert len(result.violations) == 0

    def test_review_group_chat_safe(self, sample_config, knowledge_store):
        """Test review allows safe messages in group chat"""
        reviewer = PrivacyReviewer(sample_config, knowledge_store)
        result = reviewer.review(
            "Carl 会 Python 编程",
            "group",
            {"carl", "alex"},
        )
        assert result.passed
        assert len(result.violations) == 0

    def test_review_group_chat_violation(self, sample_config, knowledge_store):
        """Test review detects privacy violations in group chat"""
        reviewer = PrivacyReviewer(sample_config, knowledge_store)
        result = reviewer.review(
            "Carl 明天 14:00 要见马原",
            "group",
            {"carl", "alex"},
        )
        assert not result.passed
        assert len(result.violations) > 0
        assert result.violations[0].category == "calendar"

    def test_review_disabled(self, sample_config, knowledge_store):
        """Test review when disabled"""
        config = sample_config.copy()
        config["review"]["enabled"] = False
        reviewer = PrivacyReviewer(config, knowledge_store)
        result = reviewer.review(
            "Carl 明天 14:00 要见马原",
            "group",
            {"carl", "alex"},
        )
        assert result.passed


class TestPrivacyGuardPlugin:
    """Test main plugin functionality"""

    @pytest.fixture
    def plugin(self, sample_config):
        """Create plugin instance"""
        plugin = PrivacyGuardPlugin()
        plugin.setup(sample_config)
        return plugin

    def test_plugin_setup(self, plugin):
        """Test plugin setup"""
        assert plugin.id == "privacy-guard"
        assert plugin.name == "Privacy Guard"
        assert plugin.config["enabled"] is True
        assert plugin.store is not None
        assert plugin.reviewer is not None

    def test_on_session_init_private(self, plugin):
        """Test session initialization for private chat"""
        session = {
            "channel_id": "dm_carl",
            "participants": ["carl"],
            "prompt": "Original prompt",
        }
        updated = plugin.on_session_init(session)
        assert "privacy_context" in updated
        assert "Private chat" in updated["privacy_context"]
        assert plugin.contexts["dm_carl"] is not None

    def test_on_session_init_group(self, plugin):
        """Test session initialization for group chat"""
        session = {
            "channel_id": "group_abc",
            "participants": ["carl", "alex"],
            "prompt": "Original prompt",
        }
        updated = plugin.on_session_init(session)
        assert "privacy_context" in updated
        assert "Group chat" in updated["privacy_context"]
        assert plugin.contexts["group_abc"] is not None

    def test_on_before_send_message_private(self, plugin):
        """Test message review for private chat (should pass)"""
        session = {
            "channel_id": "dm_carl",
            "participants": ["carl"],
        }
        plugin.on_session_init(session)
        message = "明天 14:00 要见马原"
        result = plugin.on_before_send_message(message, session)
        assert result == message

    def test_on_before_send_message_group_safe(self, plugin):
        """Test message review for group chat with safe message"""
        session = {
            "channel_id": "group_abc",
            "participants": ["carl", "alex"],
        }
        plugin.on_session_init(session)
        message = "Carl 会 Python 编程"
        result = plugin.on_before_send_message(message, session)
        assert result == message

    def test_on_before_send_message_group_violation(self, plugin):
        """Test message review for group chat with violation"""
        session = {
            "channel_id": "group_abc",
            "participants": ["carl", "alex"],
        }
        plugin.on_session_init(session)
        message = "Carl 明天 14:00 要见马原"
        
        # Should raise error when block_on_violation is True
        with pytest.raises(ValueError):
            plugin.on_before_send_message(message, session)

    def test_on_memory_search(self, plugin):
        """Test memory search filtering"""
        session = {
            "channel_id": "group_abc",
            "participants": ["carl", "alex"],
        }
        plugin.on_session_init(session)
        
        results = [
            {"path": "carl/public.jsonl", "content": "会 Python 编程"},
            {"path": "carl/private.jsonl", "content": "明天 14:00 要见马原"},
            {"path": "alex/public.jsonl", "content": "喜欢喝咖啡"},
        ]
        
        filtered = plugin.on_memory_search(results, session)
        assert len(filtered) == 2  # Only public items
        assert all("public.jsonl" in r["path"] for r in filtered)

    def test_on_file_read_allowed(self, plugin):
        """Test file read permission for allowed file"""
        session = {
            "channel_id": "dm_carl",
            "participants": ["carl"],
        }
        plugin.on_session_init(session)
        
        # Public file for participant should be allowed
        result = plugin.on_file_read("carl/public.jsonl", session)
        assert result["allow"] is True

    def test_on_file_read_denied(self, plugin):
        """Test file read permission for denied file"""
        session = {
            "channel_id": "group_abc",
            "participants": ["carl", "alex"],
        }
        plugin.on_session_init(session)
        
        # Private file in group chat should be denied
        result = plugin.on_file_read("carl/private.jsonl", session)
        assert result["allow"] is False
        assert "Private knowledge" in result["reason"]

    def test_get_privacy_context(self, plugin):
        """Test getting privacy context"""
        session = {
            "channel_id": "group_abc",
            "participants": ["carl", "alex"],
        }
        plugin.on_session_init(session)
        
        context = plugin.get_privacy_context(session)
        assert context["is_private"] is False
        assert set(context["participants"]) == {"carl", "alex"}
        assert "Group chat" in context["summary"]

    def test_review_message(self, plugin):
        """Test message review via tool"""
        result = plugin.review_message(
            "Carl 明天 14:00 要见马原",
            "group",
            ["carl", "alex"],
        )
        assert result["passed"] is False
        assert len(result["violations"]) > 0
        assert result["violations"][0]["category"] == "calendar"

    def test_add_knowledge(self, plugin):
        """Test adding knowledge via tool"""
        result = plugin.add_knowledge(
            user="test_user",
            content="Test content",
            category="test",
            visibility="public",
            source="test",
        )
        assert result["success"] is True
        assert result["item"]["user"] == "test_user"
        assert result["item"]["content"] == "Test content"
        assert result["item"]["visibility"] == "public"


def test_integration_scenarios():
    """Test integration scenarios"""
    # This would test the full plugin integration
    # For now, we'll create a simple integration test
    plugin = PrivacyGuardPlugin()
    config = {
        "enabled": True,
        "review": {"enabled": True, "block_on_violation": True},
        "knowledge_base": {"path": "./test_knowledge"},
        "defaults": {"visibility": "private"},
    }
    plugin.setup(config)
    
    # Test that plugin is properly initialized
    assert plugin.store is not None
    assert plugin.reviewer is not None
    assert plugin.config["enabled"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])