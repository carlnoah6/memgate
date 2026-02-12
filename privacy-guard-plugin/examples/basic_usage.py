"""
Basic usage examples for Privacy Guard Plugin
"""

import json
from pathlib import Path

# Example 1: Basic plugin setup
def example_basic_setup():
    """Basic plugin setup example"""
    from privacy_guard import PrivacyGuardPlugin
    
    # Create plugin instance
    plugin = PrivacyGuardPlugin()
    
    # Configure plugin
    config = {
        "enabled": True,
        "review": {
            "enabled": True,
            "llm_self_review": False,
            "block_on_violation": True,
        },
        "knowledge_base": {
            "path": "./privacy/knowledge",
            "auto_tag": True,
        },
        "defaults": {
            "visibility": "private",
            "always_private_categories": [
                "calendar", "family", "finance", "health",
                "auth", "contact_private", "dm_content",
            ],
        },
    }
    
    # Setup plugin
    plugin.setup(config)
    
    print("✓ Plugin setup complete")
    return plugin


# Example 2: Adding knowledge
def example_add_knowledge(plugin):
    """Example of adding knowledge items"""
    
    # Add public knowledge
    result = plugin.add_knowledge(
        user="carl",
        content="会 Python 编程",
        category="skill",
        visibility="public",
        source="manual",
    )
    print(f"✓ Added public knowledge: {result['item']['id']}")
    
    # Add private knowledge
    result = plugin.add_knowledge(
        user="carl",
        content="明天 14:00 要见马原",
        category="calendar",
        visibility="private",  # Will be private by default
        source="calendar_sync",
    )
    print(f"✓ Added private knowledge: {result['item']['id']}")
    
    # Add another user's knowledge
    result = plugin.add_knowledge(
        user="alex",
        content="喜欢喝咖啡",
        category="preference",
        visibility="public",
        source="manual",
    )
    print(f"✓ Added Alex's knowledge: {result['item']['id']}")


# Example 3: Session management
def example_session_management(plugin):
    """Example of session initialization and context"""
    
    # Private chat session
    private_session = {
        "channel_id": "dm_carl",
        "participants": ["carl"],
        "prompt": "You are a helpful assistant.",
    }
    
    updated_session = plugin.on_session_init(private_session)
    print(f"✓ Private session context: {updated_session['privacy_context']}")
    
    # Get privacy context
    context = plugin.get_privacy_context(private_session)
    print(f"✓ Is private: {context['is_private']}")
    print(f"✓ Participants: {context['participants']}")
    print(f"✓ Accessible knowledge items: {len(context['accessible_knowledge'])}")
    
    # Group chat session
    group_session = {
        "channel_id": "group_abc",
        "participants": ["carl", "alex"],
        "prompt": "You are a helpful assistant.",
    }
    
    updated_session = plugin.on_session_init(group_session)
    print(f"\n✓ Group session context: {updated_session['privacy_context']}")
    
    context = plugin.get_privacy_context(group_session)
    print(f"✓ Is private: {context['is_private']}")
    print(f"✓ Participants: {context['participants']}")
    print(f"✓ Accessible knowledge items: {len(context['accessible_knowledge'])}")


# Example 4: Message review
def example_message_review(plugin):
    """Example of message review"""
    
    # Safe message in group chat
    result = plugin.review_message(
        message="Carl 会 Python 编程",
        channel_type="group",
        participants=["carl", "alex"],
    )
    print(f"✓ Safe message review: {'PASSED' if result['passed'] else 'FAILED'}")
    
    # Private information in group chat (should fail)
    result = plugin.review_message(
        message="Carl 明天 14:00 要见马原",
        channel_type="group",
        participants=["carl", "alex"],
    )
    print(f"✓ Private message review: {'PASSED' if result['passed'] else 'FAILED'}")
    if not result['passed']:
        print(f"  Violations: {result['violations']}")
    
    # Private information in private chat (should pass)
    result = plugin.review_message(
        message="明天 14:00 要见马原",
        channel_type="dm",
        participants=["carl"],
    )
    print(f"✓ Private chat review: {'PASSED' if result['passed'] else 'FAILED'}")


# Example 5: Memory search filtering
def example_memory_filtering(plugin):
    """Example of memory search filtering"""
    
    # Simulate memory search results
    results = [
        {"path": "carl/public.jsonl", "content": "会 Python 编程", "score": 0.9},
        {"path": "carl/private.jsonl", "content": "明天 14:00 要见马原", "score": 0.8},
        {"path": "alex/public.jsonl", "content": "喜欢喝咖啡", "score": 0.7},
        {"path": "alex/private.jsonl", "content": "月薪 5000 元", "score": 0.6},
        {"path": "other/public.jsonl", "content": "Other content", "score": 0.5},
    ]
    
    # Group chat session
    group_session = {
        "channel_id": "group_abc",
        "participants": ["carl", "alex"],
    }
    plugin.on_session_init(group_session)
    
    filtered = plugin.on_memory_search(results, group_session)
    print(f"✓ Original results: {len(results)}")
    print(f"✓ Filtered results: {len(filtered)}")
    print(f"✓ Filtered paths: {[r['path'] for r in filtered]}")


# Example 6: File read protection
def example_file_protection(plugin):
    """Example of file read protection"""
    
    # Private chat session
    private_session = {
        "channel_id": "dm_carl",
        "participants": ["carl"],
    }
    plugin.on_session_init(private_session)
    
    # Should be allowed in private chat
    result = plugin.on_file_read("carl/private.jsonl", private_session)
    print(f"✓ Private file in private chat: {'ALLOWED' if result['allow'] else 'DENIED'}")
    
    # Group chat session
    group_session = {
        "channel_id": "group_abc",
        "participants": ["carl", "alex"],
    }
    plugin.on_session_init(group_session)
    
    # Should be denied in group chat
    result = plugin.on_file_read("carl/private.jsonl", group_session)
    print(f"✓ Private file in group chat: {'ALLOWED' if result['allow'] else 'DENIED'}")
    if not result['allow']:
        print(f"  Reason: {result['reason']}")
    
    # Public file should be allowed
    result = plugin.on_file_read("carl/public.jsonl", group_session)
    print(f"✓ Public file in group chat: {'ALLOWED' if result['allow'] else 'DENIED'}")


# Example 7: Integration with OpenClaw
def example_openclaw_integration():
    """Example of how the plugin integrates with OpenClaw"""
    
    print("""
Privacy Guard Plugin integrates with OpenClaw through:

1. Configuration (openclaw.json):
```json
{
  "plugins": {
    "load": {
      "paths": ["/path/to/privacy-guard"]
    },
    "entries": {
      "privacy-guard": {
        "enabled": true,
        "review": {"enabled": true},
        "knowledge_base": {"path": "./privacy/knowledge"},
        "defaults": {"visibility": "private"}
      }
    }
  }
}
```

2. Automatic hooks:
   - session:init: Injects privacy context
   - message:beforeSend: Reviews messages
   - memory:search: Filters results
   - file:read: Controls access

3. Available tools:
   - privacyContext: Get current context
   - privacyReview: Review a message
   - addKnowledge: Add knowledge item

4. Knowledge storage:
   - Location: ./privacy/knowledge/
   - Format: JSONL files
   - Organization: By user and visibility
""")


def main():
    """Run all examples"""
    print("=" * 60)
    print("Privacy Guard Plugin Examples")
    print("=" * 60)
    
    try:
        # Example 1: Basic setup
        print("\n1. Basic Plugin Setup")
        print("-" * 40)
        plugin = example_basic_setup()
        
        # Example 2: Adding knowledge
        print("\n2. Adding Knowledge")
        print("-" * 40)
        example_add_knowledge(plugin)
        
        # Example 3: Session management
        print("\n3. Session Management")
        print("-" * 40)
        example_session_management(plugin)
        
        # Example 4: Message review
        print("\n4. Message Review")
        print("-" * 40)
        example_message_review(plugin)
        
        # Example 5: Memory filtering
        print("\n5. Memory Search Filtering")
        print("-" * 40)
        example_memory_filtering(plugin)
        
        # Example 6: File protection
        print("\n6. File Read Protection")
        print("-" * 40)
        example_file_protection(plugin)
        
        # Example 7: OpenClaw integration
        print("\n7. OpenClaw Integration")
        print("-" * 40)
        example_openclaw_integration()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()