import pytest
from memgate.privacy_review import PrivacyReviewer
from memgate.knowledge_store import KnowledgeStore, KnowledgeItem


@pytest.fixture
def reviewer():
    # Mock store not needed for pattern tests, but initialized anyway
    return PrivacyReviewer(config={"review": {"enabled": True}})


class TestPatternMatching:
    """Test regex pattern matching for privacy leaks"""

    def test_phone_numbers(self, reviewer):
        # Should block (2 participants to force review)
        assert not reviewer.review(
            "My phone number is 13800138000", "ch1", {"user1", "user2"}
        ).passed
        assert not reviewer.review(
            "Call me at 98765432", "ch1", {"user1", "user2"}
        ).passed

        # Should pass
        assert reviewer.review("The year is 2026", "ch1", {"user1", "user2"}).passed

    def test_email_addresses(self, reviewer):
        # Should block
        assert not reviewer.review(
            "Email me at bob@example.com", "ch1", {"user1", "user2"}
        ).passed

        # Should pass
        assert reviewer.review(
            "I like example.com website", "ch1", {"user1", "user2"}
        ).passed

    def test_financial_info(self, reviewer):
        # Should block
        assert not reviewer.review("My salary is 50k", "ch1", {"user1", "user2"}).passed
        assert not reviewer.review(
            "My salary is $5000", "ch1", {"user1", "user2"}
        ).passed
        assert not reviewer.review(
            "Account balance is 100 yuan", "ch1", {"user1", "user2"}
        ).passed

        # Should pass
        assert reviewer.review(
            "Look at that high salary report", "ch1", {"user1", "user2"}
        ).passed

    def test_calendar_info(self, reviewer):
        # Should block
        assert not reviewer.review(
            "Meeting a client tomorrow afternoon", "ch1", {"user1", "user2"}
        ).passed
        assert not reviewer.review(
            "I have a meeting at 3pm", "ch1", {"user1", "user2"}
        ).passed
        assert not reviewer.review(
            "Schedule for next week", "ch1", {"user1", "user2"}
        ).passed

        # Should pass
        assert reviewer.review(
            "I like meetings generally", "ch1", {"user1", "user2"}
        ).passed

    def test_address_info(self, reviewer):
        # Should block
        assert not reviewer.review(
            "I live in Pudong New District, Shanghai", "ch1", {"user1", "user2"}
        ).passed
        assert not reviewer.review(
            "My address is 123 Main St", "ch1", {"user1", "user2"}
        ).passed


class TestEntityMatching:
    """Test entity-based matching (checking against private knowledge store)"""

    @pytest.fixture
    def populated_reviewer(self, tmp_path):
        # Setup store with some private data
        store_dir = tmp_path / "privacy" / "knowledge"
        store_dir.mkdir(parents=True)
        store = KnowledgeStore(base_dir=store_dir)

        # Add a private family member
        store.add(
            KnowledgeItem(
                id="1",
                user="alice",
                content="My son is Timothy",
                visibility="private",
                category="family",
                source="test",
                created="",
            )
        )

        # Add a private location
        store.add(
            KnowledgeItem(
                id="2",
                user="alice",
                content="Hidden Base",
                visibility="private",
                category="location",
                source="test",
                created="",
            )
        )

        return PrivacyReviewer(config={"review": {"enabled": True}}, store=store)

    def test_private_entity_leak(self, populated_reviewer):
        # "Timothy" is in Alice's private memory (family)
        result = populated_reviewer.review(
            "Is Timothy coming to the party?", "group_chat", {"alice", "stranger"}
        )
        assert not result.passed
        assert "family" in str(result.violations)

    def test_safe_conversation(self, populated_reviewer):
        # "Python" is not private
        result = populated_reviewer.review(
            "Is Python installed?", "group_chat", {"alice", "stranger"}
        )
        assert result.passed
