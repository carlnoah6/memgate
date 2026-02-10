#!/usr/bin/env python3
"""
Privacy Guard — CLI 桥接脚本

供 OpenClaw (Node.js) 通过 exec 调用 Privacy Guard Python 框架。

Usage:
  python3 scripts/privacy-check.py context  --channel-type group --participants "user1,user2"
  python3 scripts/privacy-check.py review   --message "..." --channel-type group --participants "user1,user2"
  python3 scripts/privacy-check.py filter   --results-json '...' --channel-type group --participants "user1,user2"
  python3 scripts/privacy-check.py status
"""

import argparse
import json
import sys

from .knowledge_store import KnowledgeStore, KNOWLEDGE_DIR, PRIVACY_DIR
from .privacy_context import PrivacyContext, ChannelInfo
from .privacy_review import PrivacyReviewer, load_config


def parse_participants(raw: str) -> set:
    """Parse comma-separated participant list."""
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


def cmd_context(args):
    """Generate privacy context for a session (to inject into system prompt)."""
    participants = parse_participants(args.participants)
    channel_type = args.channel_type or ("dm" if len(participants) <= 1 else "group")
    channel_id = args.channel_id or f"{channel_type}_session"

    channel = ChannelInfo(channel_id, participants, channel_type)
    store = KnowledgeStore(KNOWLEDGE_DIR)
    ctx = PrivacyContext(channel, store)

    # Build context output
    summary = ctx.get_context_summary()
    knowledge = ctx.get_accessible_knowledge()

    result = {
        "summary": summary,
        "is_private": ctx.is_private,
        "participants": sorted(participants),
        "accessible_knowledge_count": len(knowledge),
        "knowledge": [
            {
                "user": k.user,
                "content": k.content,
                "category": k.category,
                "visibility": k.visibility,
            }
            for k in knowledge
        ],
        "system_prompt_injection": _build_prompt_injection(ctx, knowledge),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _build_prompt_injection(ctx: PrivacyContext, knowledge: list) -> str:
    """Build the text to inject into system prompt."""
    lines = []
    lines.append("## Privacy Guard 上下文")
    lines.append("")
    lines.append(ctx.get_context_summary())
    lines.append("")

    if ctx.is_private:
        lines.append("✅ 私聊模式：可自由使用所有知识和记忆文件。")
    else:
        lines.append("⚠️ 群聊模式：")
        lines.append("- 只能使用以下公共知识，不能泄露任何人的私有信息")
        lines.append("- 不要提及任何人的日程、家庭详情、财务、健康、联系方式")
        lines.append("- 发送前需通过 privacy-check.py review 审查")
        lines.append("")

        if knowledge:
            lines.append("### 可用公共知识")
            for k in knowledge:
                lines.append(f"- [{k.user}] {k.content}")
        else:
            lines.append("（无可用公共知识）")

    return "\n".join(lines)


def cmd_review(args):
    """Review a message for privacy leaks before sending."""
    participants = parse_participants(args.participants)
    channel_type = args.channel_type or ("dm" if len(participants) <= 1 else "group")
    channel_id = args.channel_id or f"{channel_type}_session"

    config = load_config()
    store = KnowledgeStore(KNOWLEDGE_DIR)
    reviewer = PrivacyReviewer(config=config, store=store)

    result = reviewer.review(
        message=args.message,
        channel_id=channel_id,
        participants=participants,
        sender=args.sender or "assistant",
    )

    output = {
        "passed": result.passed,
        "message": result.message if result.passed else None,
        "violations": [
            {
                "category": v.category,
                "matched": v.matched,
                "description": v.description,
            }
            for v in result.violations
        ]
        if result.violations
        else [],
        "suggestion": result.suggestion,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    # Exit code 1 if blocked
    if not result.passed:
        sys.exit(1)


def cmd_filter(args):
    """Filter memory_search results based on privacy context."""
    participants = parse_participants(args.participants)
    channel_type = args.channel_type or ("dm" if len(participants) <= 1 else "group")
    channel_id = args.channel_id or f"{channel_type}_session"

    channel = ChannelInfo(channel_id, participants, channel_type)
    store = KnowledgeStore(KNOWLEDGE_DIR)
    ctx = PrivacyContext(channel, store)

    try:
        results = json.loads(args.results_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        sys.exit(2)

    filtered = ctx.filter_memory_results(results)

    output = {
        "original_count": len(results),
        "filtered_count": len(filtered),
        "removed": len(results) - len(filtered),
        "results": filtered,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_status(args):
    """Show Privacy Guard status."""
    config = load_config()
    store = KnowledgeStore(KNOWLEDGE_DIR)
    reviewer = PrivacyReviewer(config=config, store=store)

    status = reviewer.get_status()
    status["knowledge_dir"] = str(KNOWLEDGE_DIR)
    status["config_path"] = str(PRIVACY_DIR / "config.json")

    # Add per-user stats
    user_stats = {}
    for user in store.list_users():
        pub = store.get_public(user)
        priv = store.get_private(user)
        user_stats[user] = {"public": len(pub), "private": len(priv)}
    status["user_knowledge"] = user_stats

    print(json.dumps(status, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Privacy Guard CLI bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # context
    p_ctx = subparsers.add_parser("context", help="Get privacy context for a session")
    p_ctx.add_argument("--channel-type", choices=["dm", "group"], default=None)
    p_ctx.add_argument("--channel-id", default=None)
    p_ctx.add_argument("--participants", required=True, help="Comma-separated user IDs")

    # review
    p_rev = subparsers.add_parser("review", help="Review message for privacy leaks")
    p_rev.add_argument("--message", required=True, help="Message to review")
    p_rev.add_argument("--channel-type", choices=["dm", "group"], default=None)
    p_rev.add_argument("--channel-id", default=None)
    p_rev.add_argument("--participants", required=True, help="Comma-separated user IDs")
    p_rev.add_argument("--sender", default="assistant")

    # filter
    p_flt = subparsers.add_parser("filter", help="Filter memory_search results")
    p_flt.add_argument("--results-json", required=True, help="JSON array of results")
    p_flt.add_argument("--channel-type", choices=["dm", "group"], default=None)
    p_flt.add_argument("--channel-id", default=None)
    p_flt.add_argument("--participants", required=True, help="Comma-separated user IDs")

    # status
    subparsers.add_parser("status", help="Show Privacy Guard status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handlers = {
        "context": cmd_context,
        "review": cmd_review,
        "filter": cmd_filter,
        "status": cmd_status,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
