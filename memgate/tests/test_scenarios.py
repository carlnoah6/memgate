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
    # Carl's public knowledge
    store.add(
        KnowledgeItem(
            id="k_carl_001",
            user="carl",
            content="会 Python 和 JavaScript 编程",
            visibility="public",
            category="skill",
            source="user_declared",
            created="2026-02-10T08:00:00+08:00",
        )
    )
    # Carl's private knowledge
    store.add(
        KnowledgeItem(
            id="k_carl_003",
            user="carl",
            content="明天 14:00 和马原在 Kent Ridge Park 徒步",
            visibility="private",
            category="calendar",
            source="calendar_sync",
            created="2026-02-10T08:00:00+08:00",
        )
    )
    store.add(
        KnowledgeItem(
            id="k_carl_005",
            user="carl",
            content="月薪 50000 新币",
            visibility="private",
            category="finance",
            source="user_declared",
            created="2026-02-10T08:00:00+08:00",
        )
    )

    # Alex's public knowledge
    store.add(
        KnowledgeItem(
            id="k_alex_001",
            user="alex",
            content="擅长数据分析和 R 语言",
            visibility="public",
            category="skill",
            source="user_declared",
            created="2026-02-10T08:00:00+08:00",
        )
    )

    yield {"store": store, "config": config, "tmp_dir": tmp_dir}

    # Cleanup
    shutil.rmtree(tmp_dir)


# ── 正常使用 (Normal Usage) ──


def test_dm_access_private_knowledge(privacy_env):
    """T1: 私聊中可以访问私有知识"""
    ch = ChannelInfo("dm_carl", {"carl"}, "dm")
    ctx = PrivacyContext(ch, privacy_env["store"])
    knowledge = ctx.get_accessible_knowledge()
    categories = {k.category for k in knowledge}

    assert "calendar" in categories
    assert "finance" in categories
    assert "skill" in categories


def test_group_access_public_knowledge(privacy_env):
    """T4: 群聊中可访问公共知识"""
    ch = ChannelInfo("group_abc", {"carl", "alex"}, "group")
    ctx = PrivacyContext(ch, privacy_env["store"])
    knowledge = ctx.get_accessible_knowledge()

    public_items = [k for k in knowledge if k.visibility == "public"]
    assert len(public_items) > 0

    users = {k.user for k in public_items}
    assert "carl" in users
    assert "alex" in users


def test_dm_can_reference_group_context(privacy_env):
    """T5: 私聊中可提及自己参与的群聊内容 (基本上下文检查)"""
    ch = ChannelInfo("dm_carl", {"carl"}, "dm")
    ctx = PrivacyContext(ch, privacy_env["store"])
    assert ctx.is_private
    assert len(ctx.get_accessible_knowledge()) > 0


# ── 隔离验证 (Isolation Verification) ──


def test_group_blocks_private_knowledge(privacy_env):
    """T2: 群聊中不能看到任何人的私有知识"""
    ch = ChannelInfo("group_abc", {"carl", "alex"}, "group")
    ctx = PrivacyContext(ch, privacy_env["store"])
    knowledge = ctx.get_accessible_knowledge()

    private_items = [k for k in knowledge if k.visibility == "private"]
    assert len(private_items) == 0


def test_group_blocks_own_private_knowledge(privacy_env):
    """T3: 群聊中即使是本人也不能暴露私有知识"""
    ch = ChannelInfo("group_abc", {"carl", "alex"}, "group")
    ctx = PrivacyContext(ch, privacy_env["store"])
    knowledge = ctx.get_accessible_knowledge()

    carl_private = [
        k for k in knowledge if k.user == "carl" and k.visibility == "private"
    ]
    assert len(carl_private) == 0


def test_cross_reference_attack_blocked(privacy_env):
    """T9: 交叉引用攻击 — 审查器拦截"""
    reviewer = PrivacyReviewer(config=privacy_env["config"], store=privacy_env["store"])
    result = reviewer.review(
        "Carl 明天 14:00 和马原在 Kent Ridge Park 徒步", "group_abc", {"carl", "alex"}
    )
    assert not result.passed


def test_untagged_knowledge_is_private():
    """T11: 未标记的知识默认私有"""
    tagger = KnowledgeTagger()
    vis = tagger.classify("Carl 最近在看一本书", source="dm")
    assert vis == "private"


# ── 分类器测试 (Classifier) ──


def test_classifier_patterns():
    tagger = KnowledgeTagger()
    assert tagger.classify("明天和朋友约了吃饭") == "private"  # calendar
    assert tagger.classify("月薪 50000") == "private"  # finance

    # Skills can be public
    assert tagger.classify("会 Python #public") == "public"

    # Always private overrides
    assert tagger.classify("工资 50000", user_override="public") == "private"


# ── 审查器测试 (Reviewer) ──


def test_reviewer_group_blocks_calendar(privacy_env):
    reviewer = PrivacyReviewer(config=privacy_env["config"], store=privacy_env["store"])
    result = reviewer.review(
        "Carl 明天下午3点要去见一个朋友", "group_abc", {"carl", "alex"}
    )
    assert not result.passed


def test_reviewer_group_allows_public(privacy_env):
    reviewer = PrivacyReviewer(config=privacy_env["config"], store=privacy_env["store"])
    result = reviewer.review(
        "这个问题可以用 Python 的 pandas 库来解决", "group_abc", {"carl", "alex"}
    )
    assert result.passed


def test_reviewer_dm_allows_all(privacy_env):
    reviewer = PrivacyReviewer(config=privacy_env["config"], store=privacy_env["store"])
    result = reviewer.review(
        "你明天 14:00 要和马原在 Kent Ridge Park 徒步", "dm_carl", {"carl"}
    )
    assert result.passed


def test_reviewer_social_engineering_defense(privacy_env):
    """T8: 社工攻击防御 (从内容角度)"""
    # 审查器本身只看内容是否泄露，不看提问意图（这是 Context 层的责任）
    # 但如果回复包含了私有信息，应该被拦截
    reviewer = PrivacyReviewer(config=privacy_env["config"], store=privacy_env["store"])
    # 假设模型试图回答日程
    result = reviewer.review(
        "Carl 明天要去 Kent Ridge Park", "group_abc", {"carl", "alex"}
    )
    assert not result.passed
