import pytest
from datetime import datetime
from memgate.knowledge_store import KnowledgeStore, KnowledgeItem


# Use a temporary directory for testing
@pytest.fixture
def test_store(tmp_path):
    # Setup
    store_dir = tmp_path / "privacy" / "knowledge"
    store_dir.mkdir(parents=True)
    store = KnowledgeStore(base_dir=store_dir)
    return store


def test_add_and_retrieve_private(test_store):
    item = KnowledgeItem(
        id="test1",
        user="alice",
        content="My password is 123456",
        visibility="private",
        category="auth",
        source="test",
        created=datetime.now().isoformat(),
    )
    test_store.add(item)

    private_items = test_store.get_private("alice")
    assert len(private_items) == 1
    assert private_items[0].content == "My password is 123456"

    public_items = test_store.get_public("alice")
    assert len(public_items) == 0


def test_add_and_retrieve_public(test_store):
    item = KnowledgeItem(
        id="test2",
        user="bob",
        content="I like coding",
        visibility="public",
        category="preference",
        source="test",
        created=datetime.now().isoformat(),
    )
    test_store.add(item)

    public_items = test_store.get_public("bob")
    assert len(public_items) == 1
    assert public_items[0].content == "I like coding"


def test_always_private_enforcement(test_store):
    # Even if we try to set visibility="public"
    # "finance" is in ALWAYS_PRIVATE_CATEGORIES, so it should be forced to private
    item = KnowledgeItem(
        id="test3",
        user="charlie",
        content="My salary is $100k",
        visibility="public",  # Attempt to make public
        category="finance",  # Restricted category
        source="test",
        created=datetime.now().isoformat(),
    )
    test_store.add(item)

    # Should NOT be in public
    public_items = test_store.get_public("charlie")
    assert len(public_items) == 0

    # Should be in private
    private_items = test_store.get_private("charlie")
    assert len(private_items) == 1
    assert private_items[0].visibility == "private"
