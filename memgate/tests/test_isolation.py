#!/usr/bin/env python3
"""
Privacy Guard — 自我攻防测试

12 个测试场景覆盖正常使用、隔离验证、边界情况和攻击防御。
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_store import KnowledgeStore, KnowledgeItem, KnowledgeTagger
from privacy_context import PrivacyContext, ChannelInfo
from privacy_review import PrivacyReviewer, ReviewResult


class TestFixture:
    """测试环境"""

    def __init__(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="privacy_test_"))
        self.knowledge_dir = self.tmp_dir / "knowledge"
        self.knowledge_dir.mkdir()
        self.store = KnowledgeStore(self.knowledge_dir)
        self.config = {
            "enabled": True,
            "review": {"enabled": True, "block_on_violation": True},
            "defaults": {"visibility": "private"},
        }
        self._setup_test_data()

    def _setup_test_data(self):
        """创建测试数据"""
        # Carl's public knowledge
        self.store.add(KnowledgeItem(
            id="k_carl_001", user="carl",
            content="会 Python 和 JavaScript 编程",
            visibility="public", category="skill",
            source="user_declared", created="2026-02-10T08:00:00+08:00"
        ))
        self.store.add(KnowledgeItem(
            id="k_carl_002", user="carl",
            content="喜欢徒步和户外运动",
            visibility="public", category="preference",
            source="user_declared", created="2026-02-10T08:00:00+08:00"
        ))

        # Carl's private knowledge
        self.store.add(KnowledgeItem(
            id="k_carl_003", user="carl",
            content="明天 14:00 和马原在 Kent Ridge Park 徒步",
            visibility="private", category="calendar",
            source="calendar_sync", created="2026-02-10T08:00:00+08:00"
        ))
        self.store.add(KnowledgeItem(
            id="k_carl_004", user="carl",
            content="儿子元宝每周日 9:30 上架子鼓课",
            visibility="private", category="family",
            source="user_declared", created="2026-02-10T08:00:00+08:00"
        ))
        self.store.add(KnowledgeItem(
            id="k_carl_005", user="carl",
            content="月薪 50000 新币",
            visibility="private", category="finance",
            source="user_declared", created="2026-02-10T08:00:00+08:00"
        ))

        # Alex's public knowledge
        self.store.add(KnowledgeItem(
            id="k_alex_001", user="alex",
            content="擅长数据分析和 R 语言",
            visibility="public", category="skill",
            source="user_declared", created="2026-02-10T08:00:00+08:00"
        ))

        # Alex's private knowledge
        self.store.add(KnowledgeItem(
            id="k_alex_002", user="alex",
            content="下周二看牙医",
            visibility="private", category="health",
            source="calendar_sync", created="2026-02-10T08:00:00+08:00"
        ))

    def cleanup(self):
        shutil.rmtree(self.tmp_dir)


def run_tests():
    fixture = TestFixture()
    results = []
    
    def test(name, fn):
        try:
            fn()
            results.append(("✅", name))
            print(f"  ✅ {name}")
        except AssertionError as e:
            results.append(("❌", f"{name}: {e}"))
            print(f"  ❌ {name}: {e}")
        except Exception as e:
            results.append(("💥", f"{name}: {type(e).__name__}: {e}"))
            print(f"  💥 {name}: {type(e).__name__}: {e}")

    print("=" * 60)
    print("Privacy Guard — 自我攻防测试")
    print("=" * 60)

    # ── 正常使用 ──
    print("\n🟢 正常使用场景")

    def t1():
        """T1: 私聊中可以访问私有知识"""
        ch = ChannelInfo("dm_carl", {"carl"}, "dm")
        ctx = PrivacyContext(ch, fixture.store)
        knowledge = ctx.get_accessible_knowledge()
        categories = {k.category for k in knowledge}
        assert "calendar" in categories, "私聊应能看到日程"
        assert "family" in categories, "私聊应能看到家庭信息"
        assert "skill" in categories, "私聊应能看到技能"
    test("T1: 私聊可访问所有知识", t1)

    def t4():
        """T4: 群聊中可访问公共知识"""
        ch = ChannelInfo("group_abc", {"carl", "alex"}, "group")
        ctx = PrivacyContext(ch, fixture.store)
        knowledge = ctx.get_accessible_knowledge()
        public_items = [k for k in knowledge if k.visibility == "public"]
        assert len(public_items) > 0, "群聊应能看到公共知识"
        # Check both users' public knowledge is present
        users = {k.user for k in public_items}
        assert "carl" in users, "应包含 Carl 的公共知识"
        assert "alex" in users, "应包含 Alex 的公共知识"
    test("T4: 群聊可访问公共知识", t4)

    def t5():
        """T5: 私聊中可提及自己参与的群聊内容"""
        ch = ChannelInfo("dm_carl", {"carl"}, "dm")
        ctx = PrivacyContext(ch, fixture.store)
        assert ctx.is_private, "应识别为私聊"
        knowledge = ctx.get_accessible_knowledge()
        assert len(knowledge) > 0, "私聊应有知识可用"
    test("T5: 私聊中可引用群聊内容", t5)

    def t12():
        """T12: 已标记公共知识在群聊中可用"""
        ch = ChannelInfo("group_abc", {"carl", "alex"}, "group")
        ctx = PrivacyContext(ch, fixture.store)
        knowledge = ctx.get_accessible_knowledge()
        skill_items = [k for k in knowledge if k.category == "skill"]
        assert len(skill_items) >= 2, f"群聊应看到标记为 public 的技能知识 (found {len(skill_items)})"
    test("T12: 标记公共知识群聊可用", t12)

    # ── 隔离验证 ──
    print("\n🛡️ 隔离验证")

    def t2():
        """T2: 群聊中不能看到任何人的私有知识"""
        ch = ChannelInfo("group_abc", {"carl", "alex"}, "group")
        ctx = PrivacyContext(ch, fixture.store)
        knowledge = ctx.get_accessible_knowledge()
        private_items = [k for k in knowledge if k.visibility == "private"]
        assert len(private_items) == 0, \
            f"群聊不应看到私有知识，但找到 {len(private_items)} 条: {[k.content[:20] for k in private_items]}"
    test("T2: 群聊不可访问私有知识", t2)

    def t3():
        """T3: 群聊中即使是本人也不能暴露私有知识"""
        ch = ChannelInfo("group_abc", {"carl", "alex"}, "group")
        ctx = PrivacyContext(ch, fixture.store)
        # Carl's calendar should not be accessible even though Carl is in the group
        knowledge = ctx.get_accessible_knowledge()
        carl_private = [k for k in knowledge if k.user == "carl" and k.visibility == "private"]
        assert len(carl_private) == 0, "群聊中 Carl 的私有知识也不应可见"
    test("T3: 群聊中本人私有知识也不可见", t3)

    def t9():
        """T9: 交叉引用攻击 — 审查器拦截"""
        reviewer = PrivacyReviewer(config=fixture.config, store=fixture.store)
        result = reviewer.review(
            "Carl 明天 14:00 和马原在 Kent Ridge Park 徒步",
            "group_abc", {"carl", "alex"}
        )
        assert not result.passed, "审查应拦截包含日程信息的消息"
    test("T9: 交叉引用攻击被拦截", t9)

    def t11():
        """T11: 未标记的知识默认私有"""
        tagger = KnowledgeTagger()
        vis = tagger.classify("Carl 最近在看一本书", source="dm")
        assert vis == "private", f"未标记的知识应默认私有, got: {vis}"
    test("T11: 未标记知识默认私有", t11)

    # ── 分类器测试 ──
    print("\n🏷️ 分类器测试")

    def t_tag_calendar():
        """分类器正确识别日程"""
        tagger = KnowledgeTagger()
        assert tagger.classify("明天和朋友约了吃饭") == "private"
        assert tagger.classify("下周二有个会议") == "private"
        assert tagger.detect_category("明天去见马原") == "calendar"
    test("分类器: 日程 → 始终私有", t_tag_calendar)

    def t_tag_finance():
        """分类器正确识别财务"""
        tagger = KnowledgeTagger()
        assert tagger.classify("月薪 50000") == "private"
        assert tagger.classify("投资了一只基金") == "private"
    test("分类器: 财务 → 始终私有", t_tag_finance)

    def t_tag_skill_public():
        """分类器: 技能可标记为公共"""
        tagger = KnowledgeTagger()
        assert tagger.classify("会 Python #public") == "public"
        assert tagger.classify("擅长数据分析", user_override="public") == "public"
    test("分类器: 技能可标记公共", t_tag_skill_public)

    def t_tag_always_private_override():
        """分类器: 始终私有的类别不可被覆盖"""
        tagger = KnowledgeTagger()
        # Even with #public tag, calendar stays private
        assert tagger.classify("明天的日程 #public") == "private"
        # Even with user override
        assert tagger.classify("工资 50000", user_override="public") == "private"
    test("分类器: 始终私有不可覆盖", t_tag_always_private_override)

    # ── 审查器测试 ──
    print("\n🔍 审查器测试")

    def t_review_group_blocks_calendar():
        """审查器在群聊中拦截日程信息"""
        reviewer = PrivacyReviewer(config=fixture.config, store=fixture.store)
        result = reviewer.review(
            "Carl 明天下午3点要去见一个朋友",
            "group_abc", {"carl", "alex"}
        )
        assert not result.passed, f"应拦截日程, violations: {result.violations}"
    test("审查器: 群聊拦截日程", t_review_group_blocks_calendar)

    def t_review_group_allows_public():
        """审查器在群聊中允许公共信息"""
        reviewer = PrivacyReviewer(config=fixture.config, store=fixture.store)
        result = reviewer.review(
            "这个问题可以用 Python 的 pandas 库来解决",
            "group_abc", {"carl", "alex"}
        )
        assert result.passed, f"公共信息应通过, violations: {result.violations}"
    test("审查器: 群聊允许公共信息", t_review_group_allows_public)

    def t_review_dm_allows_all():
        """审查器在私聊中不审查"""
        reviewer = PrivacyReviewer(config=fixture.config, store=fixture.store)
        result = reviewer.review(
            "你明天 14:00 要和马原在 Kent Ridge Park 徒步",
            "dm_carl", {"carl"}
        )
        assert result.passed, "私聊中不应审查"
    test("审查器: 私聊不审查", t_review_dm_allows_all)

    def t_review_disabled():
        """审查器可关闭"""
        config = {**fixture.config, "review": {"enabled": False}}
        reviewer = PrivacyReviewer(config=config, store=fixture.store)
        result = reviewer.review(
            "Carl 月薪 50000 新币",
            "group_abc", {"carl", "alex"}
        )
        assert result.passed, "审查关闭时应全部通过"
    test("审查器: 开关关闭时全部通过", t_review_disabled)

    # ── 攻击防御 ──
    print("\n🔴 攻击防御")

    def t_social_engineering():
        """社工攻击: 请求假装私聊"""
        reviewer = PrivacyReviewer(config=fixture.config, store=fixture.store)
        # The reviewer checks the actual channel state, not the message content
        result = reviewer.review(
            "Carl 的日程安排是什么？他明天要去哪？",
            "group_abc", {"carl", "alex"}
        )
        assert not result.passed, "应拦截群聊中的日程请求"
    test("T8: 社工攻击防御", t_social_engineering)

    def t_context_isolation():
        """上下文隔离: can_access_item 正确过滤"""
        ch = ChannelInfo("group_abc", {"carl", "alex"}, "group")
        ctx = PrivacyContext(ch, fixture.store)

        # Carl's public item → accessible
        public_item = KnowledgeItem(
            id="test1", user="carl", content="test",
            visibility="public", category="skill",
            source="test", created="2026-01-01"
        )
        assert ctx.can_access_item(public_item), "公共条目应可访问"

        # Carl's private item → not accessible in group
        private_item = KnowledgeItem(
            id="test2", user="carl", content="test",
            visibility="private", category="calendar",
            source="test", created="2026-01-01"
        )
        assert not ctx.can_access_item(private_item), "私有条目不应可访问"

        # Unknown user's item → not accessible
        unknown_item = KnowledgeItem(
            id="test3", user="bob", content="test",
            visibility="public", category="skill",
            source="test", created="2026-01-01"
        )
        assert not ctx.can_access_item(unknown_item), "非参与者的条目不应可访问"
    test("T10: 上下文隔离验证", t_context_isolation)

    # ── Summary ──
    print("\n" + "=" * 60)
    passed = sum(1 for s, _ in results if s == "✅")
    failed = sum(1 for s, _ in results if s != "✅")
    total = len(results)
    print(f"结果: {passed}/{total} 通过, {failed} 失败")

    if failed > 0:
        print("\n失败项:")
        for status, name in results:
            if status != "✅":
                print(f"  {status} {name}")

    print("=" * 60)

    fixture.cleanup()
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
