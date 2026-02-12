# Privacy Guard Skill

Privacy Guard acts as a firewall for your agent's memory and outputs. It ensures that private information (PII, sensitive data) is not leaked into group chats or inappropriate contexts.

## Overview

This skill provides a centralized way to:
1.  **Determine Context**: What knowledge is safe to access? (e.g., in a group chat, only public knowledge is allowed).
2.  **Review Output**: Check messages before they are sent to ensure no private info is leaked.
3.  **Filter Results**: Scrub search results from memory to hide private files.

## Tools

This skill exposes a CLI interface at `src/cli.py`.

### 1. Check Context (`context`)

Determines the privacy context for a given channel and participants.

```bash
python3 src/cli.py context --channel-type <dm|group> --participants "user1,user2"
```

**Output:**
- `summary`: A text summary to inject into the system prompt.
- `accessible_paths`: List of allowed knowledge files (e.g., only `public.jsonl` for groups).

### 2. Review Message (`review`)

Checks a pending message for privacy violations (Regex patterns + Knowledge Entity matching).

```bash
python3 src/cli.py review --message "Call me at 12345678" --channel-type group --participants "user1,user2"
```

**Output:**
- `passed`: Boolean.
- `violations`: List of detected issues.

### 3. Filter Results (`filter`)

Filters a list of memory search results against the allowed paths.

```bash
python3 src/cli.py filter --results-json '[...]' --channel-type group --participants "user1,user2"
```

## Configuration

Configuration is located in `src/config.json`.

```json
{
  "review": {
    "enabled": true,
    "block_on_violation": true
  }
}
```

## Directory Structure

- `src/`: Core logic and CLI.
- `knowledge/`: Local knowledge store (JSONL files).
- `src/patterns/`: Regex patterns for privacy detection.

## Integration Guide

To use this in your agent:

1.  **On Session Start**: Run `context` to get the safe knowledge paths and prompt summary.
2.  **Before Sending**: Run `review` if the channel contains multiple people.
3.  **On Search**: Run `filter` on any results retrieved from `memory_search` or `grep`.
