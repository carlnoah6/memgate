#!/usr/bin/env python3
"""
MemGate × OpenClaw — Agent Privacy Integration
================================================

This example demonstrates how to integrate MemGate into an OpenClaw
agent's message pipeline to enforce privacy-aware knowledge isolation
across different chat channels.

OpenClaw Architecture
---------------------
OpenClaw agents handle messages across multiple platforms (Feishu, Discord,
Slack, WhatsApp).  Each channel has different participants, and MemGate
ensures that the agent never leaks private information in public contexts.

::

    ┌─────────────────────────────────────────────────────┐
    │                    OpenClaw Agent                    │
    │                                                     │
    │  Feishu DM ──────┐                                  │
    │  Feishu Group ───┤     ┌─────────────────────┐      │
    │  Discord DM ─────┼────→│     MemGate Layer   │      │
    │  Discord Group ──┤     │                     │      │
    │  WhatsApp ───────┘     │  • Knowledge filter │      │
    │                        │  • Output review    │      │
    │                        │  • Context summary  │      │
    │                        └─────────────────────┘      │
    └─────────────────────────────────────────────────────┘

Integration points
------------------
1. **Session start** — inject privacy context into system prompt
2. **Knowledge loading** — filter accessible knowledge by channel
3. **Before reply** — review outgoing messages for privacy violations
4. **Context switch** — update privacy rules when channel changes

Running
-------
::

    cd memgate/
    python3 examples/openclaw_example.py

No API keys or OpenClaw installation needed — everything is mocked.

Dependencies
------------
- ``memgate >= 0.3`` (this repo)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from memgate.knowledge_store import KnowledgeStore, KnowledgeItem  # noqa: E402
from memgate.privacy_context import ChannelInfo, PrivacyContext  # noqa: E402
from memgate.privacy_review import PrivacyReviewer, ReviewResult  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════
# Simulated OpenClaw types
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class OpenClawChannel:
    """Represents an OpenClaw chat channel."""

    channel_id: str
    channel_type: str  # "dm" | "group"
    platform: str  # "feishu" | "discord" | "slack" | "whatsapp"
    participants: set[str] = field(default_factory=set)
    name: str = ""

    def __str__(self) -> str:
        ptype = "🔒 DM" if self.channel_type == "dm" else "🌐 Group"
        return f"{ptype} [{self.platform}] {self.name or self.channel_id}"


@dataclass
class OpenClawMessage:
    """Represents an incoming message."""

    channel: OpenClawChannel
    sender: str
    content: str
    message_id: str = ""


@dataclass
class OpenClawReply:
    """Represents an outgoing reply."""

    content: str
    channel: OpenClawChannel
    reviewed: bool = False
    blocked: bool = False
    violations: list = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# MemGate OpenClaw Integration
# ═══════════════════════════════════════════════════════════════════════════


class MemGateAgent:
    """OpenClaw agent with MemGate privacy integration.

    This class shows the recommended integration pattern:

    1. On session start → generate privacy-aware system prompt
    2. On message received → load filtered knowledge context
    3. Before sending reply → review for privacy violations

    Usage in AGENTS.md / plugin config::

        # In your OpenClaw workspace AGENTS.md:
        ## Privacy
        - MemGate is enabled for all channels
        - Group chats: only public knowledge accessible
        - DMs: full knowledge access for that user
        - Always run privacy review before sending

    Usage in code::

        agent = MemGateAgent()

        # Handle incoming message
        reply = agent.handle_message(incoming_msg)

        # Reply is automatically privacy-reviewed
        if not reply.blocked:
            send(reply)  # safe to send
    """

    def __init__(
        self,
        *,
        store: KnowledgeStore | None = None,
        reviewer: PrivacyReviewer | None = None,
        fallback: str = "I can't share that information in this context.",
    ):
        self.store = store or KnowledgeStore()
        self.reviewer = reviewer or PrivacyReviewer(store=self.store)
        self.fallback = fallback

        # Violation log (in production, send to monitoring)
        self.violation_log: list[dict] = []

    def _make_channel_info(self, channel: OpenClawChannel) -> ChannelInfo:
        """Convert OpenClaw channel to MemGate ChannelInfo."""
        return ChannelInfo(
            channel_id=channel.channel_id,
            participants=channel.participants,
            channel_type=channel.channel_type,
        )

    # ── Integration Point 1: System Prompt ──

    def get_system_prompt(self, channel: OpenClawChannel) -> str:
        """Generate a privacy-aware system prompt for this channel.

        Call this when starting a new session or switching channels.
        The returned string should be prepended/appended to your
        agent's system prompt.

        Example output (group chat)::

            [Privacy] Group mode (participants: alice, bob, charlie)
            — Only use participants' public knowledge
            — Do not reveal any private information

            Available knowledge:
            - [alice] Python and Rust developer (skill)
            - [bob] Frontend developer (skill)
        """
        info = self._make_channel_info(channel)
        ctx = PrivacyContext(info, self.store)

        parts = [ctx.get_context_summary()]

        # Add accessible knowledge
        items = ctx.get_accessible_knowledge()
        if items:
            parts.append("\nAvailable knowledge:")
            for item in items:
                parts.append(f"  - [{item.user}] {item.content} ({item.category})")

        if channel.channel_type == "group":
            parts.append(
                "\n⚠️ STRICT: Do not mention schedules, finances, health, "
                "family details, or contact info for any participant."
            )

        return "\n".join(parts)

    # ── Integration Point 2: Knowledge Loading ──

    def get_knowledge(self, channel: OpenClawChannel) -> list[KnowledgeItem]:
        """Load knowledge items accessible in this channel context.

        Use this to populate RAG context or memory for your LLM calls.
        """
        info = self._make_channel_info(channel)
        ctx = PrivacyContext(info, self.store)
        return ctx.get_accessible_knowledge()

    # ── Integration Point 3: Reply Review ──

    def review_reply(
        self,
        draft: str,
        channel: OpenClawChannel,
    ) -> OpenClawReply:
        """Review a draft reply before sending.

        Returns an OpenClawReply with review metadata.
        If the reply is blocked, the content is replaced with a fallback.
        """
        result: ReviewResult = self.reviewer.review(
            message=draft,
            channel_id=channel.channel_id,
            participants=channel.participants,
            sender="assistant",
        )

        if result.passed:
            return OpenClawReply(
                content=draft,
                channel=channel,
                reviewed=True,
                blocked=False,
            )

        # Log violation
        violation_info = {
            "channel": str(channel),
            "channel_id": channel.channel_id,
            "categories": [v.category for v in result.violations],
            "matched": [v.matched for v in result.violations],
        }
        self.violation_log.append(violation_info)

        print(
            f"  ⚠️  MemGate blocked reply in {channel}: {violation_info['categories']}",
            file=sys.stderr,
        )

        return OpenClawReply(
            content=self.fallback,
            channel=channel,
            reviewed=True,
            blocked=True,
            violations=result.violations,
        )

    # ── Full Pipeline ──

    def handle_message(
        self,
        msg: OpenClawMessage,
        draft_reply: str,
    ) -> OpenClawReply:
        """Full message handling pipeline.

        In a real OpenClaw agent, this would be called from the message
        handler after the LLM generates a draft reply.

        Steps:
        1. Load knowledge context (for logging/debugging)
        2. Review the draft reply
        3. Return reviewed reply
        """
        # Step 1: Log knowledge context (useful for debugging)
        _ = self.get_knowledge(msg.channel)

        # Step 2: Review draft
        reply = self.review_reply(draft_reply, msg.channel)

        return reply


# ═══════════════════════════════════════════════════════════════════════════
# Demo
# ═══════════════════════════════════════════════════════════════════════════


def setup_demo_knowledge(store: KnowledgeStore) -> None:
    """Set up multi-user knowledge for the demo."""
    users = {
        "alice": [
            ("Python/Rust developer, 5 years experience", "skill", "public"),
            ("Enjoys hiking and photography", "preference", "public"),
            ("Meeting with CTO tomorrow 10am", "calendar", "private"),
            ("Phone: 13812345678", "contact_private", "private"),
        ],
        "bob": [
            ("React/Vue frontend expert", "skill", "public"),
            ("Chess enthusiast, rated 1800", "preference", "public"),
            ("Annual salary: $120,000", "finance", "private"),
            ("Son starts kindergarten next month", "family", "private"),
        ],
        "charlie": [
            ("DevOps engineer, Kubernetes specialist", "skill", "public"),
            ("Loves cooking Italian food", "preference", "public"),
            ("Doctor appointment Friday 2pm", "health", "private"),
        ],
    }

    for user, items in users.items():
        for content, category, visibility in items:
            store.add(
                KnowledgeItem.from_dict(
                    {
                        "user": user,
                        "content": content,
                        "category": category,
                        "visibility": visibility,
                        "source": "demo",
                    }
                )
            )


def print_header(text: str) -> None:
    width = max(len(text) + 4, 55)
    print(f"\n╔{'═' * width}╗")
    print(f"║  {text:<{width - 2}}║")
    print(f"╚{'═' * width}╝")


def main() -> None:
    import tempfile

    print("=" * 65)
    print("  MemGate × OpenClaw — Agent Privacy Integration Demo")
    print("=" * 65)

    with tempfile.TemporaryDirectory() as tmpdir:
        store = KnowledgeStore(base_dir=Path(tmpdir))
        setup_demo_knowledge(store)

        agent = MemGateAgent(
            store=store,
            fallback="⚠️ I can't share that information in this channel.",
        )

        # ── Define channels ──
        feishu_group = OpenClawChannel(
            channel_id="oc_group_team",
            channel_type="group",
            platform="feishu",
            participants={"alice", "bob", "charlie"},
            name="Team Chat",
        )

        alice_dm = OpenClawChannel(
            channel_id="oc_dm_alice",
            channel_type="dm",
            platform="feishu",
            participants={"alice"},
            name="Alice DM",
        )

        discord_group = OpenClawChannel(
            channel_id="disc_general",
            channel_type="group",
            platform="discord",
            participants={"alice", "bob"},
            name="#general",
        )

        # ── Demo 1: System Prompt Generation ──
        print_header("1. System Prompt Generation")

        print("\n  [Group Chat — Team]")
        prompt = agent.get_system_prompt(feishu_group)
        for line in prompt.split("\n"):
            print(f"    {line}")

        print("\n  [Alice DM]")
        prompt = agent.get_system_prompt(alice_dm)
        for line in prompt.split("\n"):
            print(f"    {line}")

        # ── Demo 2: Knowledge Isolation ──
        print_header("2. Knowledge Isolation")

        print(
            f"\n  [Group] Accessible knowledge ({len(agent.get_knowledge(feishu_group))} items):"
        )
        for item in agent.get_knowledge(feishu_group):
            print(f"    🔓 [{item.user}] {item.content}")

        print(
            f"\n  [Alice DM] Accessible knowledge ({len(agent.get_knowledge(alice_dm))} items):"
        )
        for item in agent.get_knowledge(alice_dm):
            vis = "🔓" if item.visibility == "public" else "🔒"
            print(f"    {vis} [{item.user}] {item.content}")

        # ── Demo 3: Reply Review ──
        print_header("3. Reply Review — Group Chat")

        test_replies = [
            ("Safe", "Alice is great at Python and Bob is a React expert!"),
            ("Schedule", "Alice has a meeting with the CTO tomorrow at 10am."),
            ("Finance", "Bob earns a salary of $120,000 per year."),
            ("Family", "Bob's son is starting kindergarten next month."),
            ("Mixed", "Alice knows Python. Her phone is 13812345678."),
        ]

        for label, draft in test_replies:
            reply = agent.review_reply(draft, feishu_group)
            status = "✅" if not reply.blocked else "🚫"
            print(f"\n  [{label}] {status}")
            print(f'    Draft:  "{draft}"')
            print(f'    Sent:   "{reply.content}"')
            if reply.blocked:
                cats = [v.category for v in reply.violations]
                print(f"    Reason: {cats}")

        # ── Demo 4: Same message, different contexts ──
        print_header("4. Context-Dependent Behavior")

        test_msg = "Alice has a meeting tomorrow at 10am with the CTO."
        print(f'\n  Message: "{test_msg}"')

        channels = [
            ("Feishu Group (3 people)", feishu_group),
            ("Discord Group (2 people)", discord_group),
            ("Alice DM (private)", alice_dm),
        ]

        for label, channel in channels:
            reply = agent.review_reply(test_msg, channel)
            status = "✅ PASSED" if not reply.blocked else "🚫 BLOCKED"
            print(f"\n    {label}: {status}")

        # ── Demo 5: Full Pipeline ──
        print_header("5. Full Message Pipeline")

        msg = OpenClawMessage(
            channel=feishu_group,
            sender="user123",
            content="Tell me about Alice",
        )

        # Simulate LLM generating a safe reply
        safe_draft = "Alice is a Python and Rust developer who enjoys hiking."
        reply = agent.handle_message(msg, safe_draft)
        print("\n  [Safe draft]")
        print(f'    Input:  "{safe_draft}"')
        print(f'    Output: "{reply.content}"')
        print(f"    Status: {'✅ Sent' if not reply.blocked else '🚫 Blocked'}")

        # Simulate LLM leaking private info
        leak_draft = "Alice has a meeting tomorrow at 10am. Her phone is 13812345678."
        reply = agent.handle_message(msg, leak_draft)
        print("\n  [Leak draft]")
        print(f'    Input:  "{leak_draft}"')
        print(f'    Output: "{reply.content}"')
        print(f"    Status: {'✅ Sent' if not reply.blocked else '🚫 Blocked'}")

        # ── Violation log ──
        print_header("6. Violation Log")
        print(f"\n  Total violations caught: {len(agent.violation_log)}")
        for i, v in enumerate(agent.violation_log, 1):
            print(f"    {i}. {v['channel']} — categories: {v['categories']}")

        # ── Integration guide ──
        print("\n" + "=" * 65)
        print("  Integration Guide for OpenClaw")
        print("=" * 65)
        print("""
  To integrate MemGate into your OpenClaw agent:

  1. Add to AGENTS.md:
     ```
     ## Privacy
     MemGate privacy layer is active.
     - Group chats: only public knowledge
     - DMs: full access for that user
     ```

  2. In your workspace, create a privacy hook:
     ```python
     # scripts/privacy-hook.sh
     # Called before each reply
     python3 scripts/privacy-check.py review \\
       --message "$DRAFT" \\
       --channel-type "$CHANNEL_TYPE" \\
       --participants "$PARTICIPANTS"
     ```

  3. Add knowledge for users:
     ```bash
     memgate add --user alice \\
       --content "Python developer" \\
       --category skill \\
       --visibility public
     ```

  4. The agent will automatically:
     - Load filtered knowledge per channel
     - Review all outgoing messages
     - Block any privacy violations
""")


if __name__ == "__main__":
    main()
