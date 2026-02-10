import pytest
import tempfile
import shutil
from pathlib import Path

from memgate.knowledge_store import KnowledgeStore, KnowledgeItem, KnowledgeTagger
from memgate.privacy_context import PrivacyContext, ChannelInfo
from memgate.privacy_review import PrivacyReviewer


@pytest.fixture
def privacy_env():
    """Setup a temporary privacy environment with populated data"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="privacy_test_"))
    knowledge_dir = tmp_dir / "knowledge"
    knowledge_dir.mkdir()
    store = KnowledgeStore(knowledge_dir)

    config = {
        "enabled": True,
        "review": {"enabled": True, "block_on_violation": True},
        "defaults": {"visibility": "private"},
    }

    # --- Setup Data ---
    # Alice's public knowledge
    store.add(
        KnowledgeItem(
            id="k_alice_001",
            user="alice",
            content="Proficient in Python and JavaScript programming",
            visibility="public",
            category="skill",
            source="user_declared",
            created="2026-02-10T08:00:00+08:00",
        )
    )
    # Alice's private knowledge
    store.add(
        KnowledgeItem(
            id="k_alice_003",
            user="alice",
            content="Hiking with Charlie at Central Park tomorrow at 14:00",
            visibility="private",
            category="calendar",
            source="calendar_sync",
            created="2026-02-10T08:00:00+08:00",
        )
    )
    store.add(
        KnowledgeItem(
            id="k_alice_005",
            user="alice",
            content="Monthly salary 50000",
            visibility="private",
            category="finance",
            source="user_declared",
            created="2026-02-10T08:00:00+08:00",
        )
    )

    # Alex's public knowledge
    store.add(
        KnowledgeItem(
            id="k_bob_001",
            user="bob",
            content="Expert in data analysis and R language",
            visibility="public",
            category="skill",
            source="user_declared",
            created="2026-02-10T08:00:00+08:00",
        )
    )

    yield {"store": store, "config": config, "tmp_dir": tmp_dir}

    # Cleanup
    shutil.rmtree(tmp_dir)


# -- Normal Usage --


def test_dm_access_private_knowledge(privacy_env):
    """T1: Private knowledge should be accessible in DMs."""
    ch = ChannelInfo("dm_alice", {"alice"}, "dm")
    ctx = PrivacyContext(ch, privacy_env["store"])
    knowledge = ctx.get_accessible_knowledge()
    categories = {k.category for k in knowledge}

    assert "calendar" in categories
    assert "finance" in categories
    assert "skill" in categories


def test_group_access_public_knowledge(privacy_env):
    """T4: Public knowledge should be accessible in group chats."""
    ch = ChannelInfo("group_abc", {"alice", "bob"}, "group")
    ctx = PrivacyContext(ch, privacy_env["store"])
    knowledge = ctx.get_accessible_knowledge()

    public_items = [k for k in knowledge if k.visibility == "public"]
    assert len(public_items) > 0

    users = {k.user for k in public_items}
    assert "alice" in users
    assert "bob" in users


def test_dm_can_reference_group_context(privacy_env):
    """T5: DMs can reference group chat context (basic context check)."""
    ch = ChannelInfo("dm_alice", {"alice"}, "dm")
    ctx = PrivacyContext(ch, privacy_env["store"])
    assert ctx.is_private
    assert len(ctx.get_accessible_knowledge()) > 0


# -- Isolation Verification --


def test_group_blocks_private_knowledge(privacy_env):
    """T2: Private knowledge should not be visible in group chats."""
    ch = ChannelInfo("group_abc", {"alice", "bob"}, "group")
    ctx = PrivacyContext(ch, privacy_env["store"])
    knowledge = ctx.get_accessible_knowledge()

    private_items = [k for k in knowledge if k.visibility == "private"]
    assert len(private_items) == 0


def test_group_blocks_own_private_knowledge(privacy_env):
    """T3: Even the owner's private knowledge should not be exposed in group chats."""
    ch = ChannelInfo("group_abc", {"alice", "bob"}, "group")
    ctx = PrivacyContext(ch, privacy_env["store"])
    knowledge = ctx.get_accessible_knowledge()

    alice_private = [
        k for k in knowledge if k.user == "alice" and k.visibility == "private"
    ]
    assert len(alice_private) == 0


def test_cross_reference_attack_blocked(privacy_env):
    """T9: Cross-reference attack — reviewer blocks it."""
    reviewer = PrivacyReviewer(config=privacy_env["config"], store=privacy_env["store"])
    # "Alice is hiking with Charlie at Central Park tomorrow at 14:00"
    result = reviewer.review(
        "Alice is hiking with Charlie at Central Park tomorrow at 14:00",
        "group_abc",
        {"alice", "bob"},
    )
    assert not result.passed


def test_untagged_knowledge_is_private():
    """T11: Untagged knowledge defaults to private."""
    tagger = KnowledgeTagger()
    vis = tagger.classify("Alice is reading a book recently", source="dm")
    assert vis == "private"


# -- Classifier Tests --


def test_classifier_patterns():
    tagger = KnowledgeTagger()
    assert tagger.classify("Dinner with friends tomorrow") == "private"  # calendar
    assert tagger.classify("Salary 50000") == "private"  # finance

    # Skills can be public
    assert tagger.classify("Knows Python #public") == "public"

    # Always private overrides
    assert tagger.classify("Wage 50000", user_override="public") == "private"


# -- Reviewer Tests --


def test_reviewer_group_blocks_calendar(privacy_env):
    reviewer = PrivacyReviewer(config=privacy_env["config"], store=privacy_env["store"])
    result = reviewer.review(
        "Alice has a meeting with a friend tomorrow at 3pm",
        "group_abc",
        {"alice", "bob"},
    )
    assert not result.passed


def test_reviewer_group_allows_public(privacy_env):
    reviewer = PrivacyReviewer(config=privacy_env["config"], store=privacy_env["store"])
    result = reviewer.review(
        "This problem can be solved with Python pandas", "group_abc", {"alice", "bob"}
    )
    assert result.passed


def test_reviewer_dm_allows_all(privacy_env):
    reviewer = PrivacyReviewer(config=privacy_env["config"], store=privacy_env["store"])
    result = reviewer.review(
        "You are hiking with Charlie tomorrow at 14:00", "dm_alice", {"alice"}
    )
    assert result.passed


def test_reviewer_social_engineering_defense(privacy_env):
    """T8: Social engineering defense (from content perspective)."""
    # The reviewer only checks whether the content leaks info, not the intent of the question (that's the Context layer's job)
    # But if the response contains private information, it should be blocked
    reviewer = PrivacyReviewer(config=privacy_env["config"], store=privacy_env["store"])
    # Assume the model tried to answer with schedule info
    result = reviewer.review(
        "Alice is going to Central Park tomorrow", "group_abc", {"alice", "bob"}
    )
    assert not result.passed
