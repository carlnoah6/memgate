#!/usr/bin/env python3
"""
Privacy Guard CLI
Exposes privacy logic as command-line tools for OpenClaw.
"""

import sys
import argparse
import json
from pathlib import Path

# Add current directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent))

from privacy_context import PrivacyContext, ChannelInfo
from privacy_review import PrivacyReviewer

def parse_participants(participants_str):
    if not participants_str:
        return set()
    return set(p.strip() for p in participants_str.split(",") if p.strip())

def cmd_context(args):
    """Handle 'context' command: Get accessible knowledge/privacy context"""
    participants = parse_participants(args.participants)
    channel = ChannelInfo(
        channel_id=args.channel_id or "unknown",
        participants=participants,
        channel_type=args.channel_type
    )
    
    ctx = PrivacyContext(channel)
    
    # Generate report
    summary = ctx.get_context_summary()
    accessible_paths = list(ctx.get_accessible_paths())
    
    result = {
        "summary": summary,
        "is_private": ctx.is_private,
        "accessible_paths": accessible_paths,
        "participants": list(participants)
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))

def cmd_review(args):
    """Handle 'review' command: Check message for privacy violations"""
    participants = parse_participants(args.participants)
    
    reviewer = PrivacyReviewer()
    result = reviewer.review(
        message=args.message,
        channel_id=args.channel_id or "unknown",
        participants=participants,
        sender=args.sender
    )
    
    output = {
        "passed": result.passed,
        "message": result.message,
        "violations": [
            {"category": v.category, "matched": v.matched, "description": v.description}
            for v in result.violations
        ],
        "suggestion": result.suggestion
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))

def cmd_filter(args):
    """Handle 'filter' command: Filter memory search results"""
    try:
        results = json.loads(args.results_json)
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON in results-json"}, ensure_ascii=False))
        sys.exit(1)
        
    participants = parse_participants(args.participants)
    channel = ChannelInfo(
        channel_id=args.channel_id or "unknown",
        participants=participants,
        channel_type=args.channel_type
    )
    
    ctx = PrivacyContext(channel)
    filtered = ctx.filter_memory_results(results)
    
    print(json.dumps(filtered, ensure_ascii=False, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Privacy Guard CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Common arguments
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--channel-id", help="Channel ID")
    parent_parser.add_argument("--channel-type", choices=["dm", "group"], required=True, help="Channel type")
    parent_parser.add_argument("--participants", required=True, help="Comma-separated user IDs")

    # Command: context
    subparsers.add_parser("context", parents=[parent_parser], help="Get privacy context")
    
    # Command: review
    review_parser = subparsers.add_parser("review", parents=[parent_parser], help="Review message for privacy")
    review_parser.add_argument("--message", required=True, help="Message to review")
    review_parser.add_argument("--sender", default="assistant", help="Sender ID")
    
    # Command: filter
    filter_parser = subparsers.add_parser("filter", parents=[parent_parser], help="Filter search results")
    filter_parser.add_argument("--results-json", required=True, help="JSON string of search results")
    
    args = parser.parse_args()
    
    if args.command == "context":
        cmd_context(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "filter":
        cmd_filter(args)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
