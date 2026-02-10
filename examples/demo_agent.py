#!/usr/bin/env python3
"""
MemGate Demo Agent
==================

This script demonstrates the core workflow of MemGate:
1. Setup a KnowledgeStore and seed it with Private vs Public data.
2. Simulate different Contexts (Private DM vs Group Chat).
3. Show how the PrivacyReviewer blocks sensitive data leakage.

Usage:
    python3 demo_agent.py
"""

import sys
import shutil
from pathlib import Path

# Add project root to path so we can import memgate without installation
project_root = Path(__file__).parents[1]
sys.path.insert(0, str(project_root))

try:
    from memgate.memgate.knowledge_store import KnowledgeStore, KnowledgeItem
    from memgate.memgate.privacy_context import PrivacyContext, ChannelInfo
    from memgate.memgate.privacy_review import PrivacyReviewer
except ImportError:
    # Fallback if installed via pip
    from memgate.knowledge_store import KnowledgeStore, KnowledgeItem
    from memgate.privacy_context import PrivacyContext, ChannelInfo
    from memgate.privacy_review import PrivacyReviewer


def main():
    # --- Configuration ---
    demo_dir = Path("demo_data")
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir()

    print("🚀 Starting MemGate Demo...\n")

    # ---------------------------------------------------------
    # 1. Initialize Storage & Seed Data
    # ---------------------------------------------------------
    print("💾 [1] Initializing Knowledge Store...")
    store = KnowledgeStore(base_dir=demo_dir)

    user_alice = "alice"

    # Create a PRIVATE secret
    secret_item = KnowledgeItem(
        id="secret_001",
        user=user_alice,
        content="My bank password is 'hunter2'.",
        visibility="private",
        category="auth",
        source="user_input",
        created="",
    )
    store.add(secret_item)
    print(f"   + Added PRIVATE item: [Auth] {secret_item.content}")

    # Create a PUBLIC fact
    public_item = KnowledgeItem(
        id="public_001",
        user=user_alice,
        content="I enjoy playing tennis on weekends.",
        visibility="public",
        category="hobby",
        source="user_input",
        created="",
    )
    store.add(public_item)
    print(f"   + Added PUBLIC item:  [Hobby] {public_item.content}")

    # ---------------------------------------------------------
    # 2. Context Awareness (Input Filtering)
    # ---------------------------------------------------------
    print("\n🛡️  [2] Testing Context Access...")

    # Scenario A: Alice talking to herself (Private DM)
    # Expectation: Can access everything
    dm_channel = ChannelInfo(
        channel_id="dm_alice", participants={user_alice}, channel_type="dm"
    )
    dm_ctx = PrivacyContext(dm_channel, store)
    dm_memories = dm_ctx.get_accessible_knowledge()

    print(f"   [Scenario: Private DM] Retrieved {len(dm_memories)} items.")
    for m in dm_memories:
        print(f"     - {m.visibility.upper()}: {m.content}")

    # Scenario B: Alice talking in a Group with Bob
    # Expectation: Can ONLY access Public items
    group_channel = ChannelInfo(
        channel_id="group_work", participants={user_alice, "bob"}, channel_type="group"
    )
    group_ctx = PrivacyContext(group_channel, store)
    group_memories = group_ctx.get_accessible_knowledge()

    print(f"   [Scenario: Group Chat] Retrieved {len(group_memories)} items.")
    for m in group_memories:
        print(f"     - {m.visibility.upper()}: {m.content}")

    assert len(dm_memories) == 2
    assert len(group_memories) == 1
    print("   ✅ Context filtering working correctly.")

    # ---------------------------------------------------------
    # 3. Output Review (Leak Prevention)
    # ---------------------------------------------------------
    print("\n👮 [3] Testing Output Privacy Review...")
    reviewer = PrivacyReviewer(store=store)

    # Simulated Agent Response 1: Harmless
    response_safe = "Alice likes tennis."
    print(f"   [Agent Attempt]: '{response_safe}'")
    res_safe = reviewer.review(
        response_safe, group_channel.channel_id, group_channel.participants
    )

    if res_safe.passed:
        print("     ✅ Allowed.")
    else:
        print("     ❌ Blocked.")

    # Simulated Agent Response 2: LEAKING PRIVATE INFO
    response_leak = "Alice's bank password is hunter2."
    print(f"   [Agent Attempt]: '{response_leak}'")
    res_leak = reviewer.review(
        response_leak, group_channel.channel_id, group_channel.participants
    )

    if res_leak.passed:
        print("     ❌ Allowed (Unexpected!).")
    else:
        print("     ✅ Blocked correctly!")
        print(f"     reason: {res_leak.violations[0].description}")

    # ---------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    print("\n✨ Demo finished successfully.")


if __name__ == "__main__":
    main()
