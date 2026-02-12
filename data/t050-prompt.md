# Task t050: Explore API Proxy for Native Format Support

You are tasked with exploring the `api-proxy` codebase to prepare for a major refactor: supporting native formats (Anthropic & OpenAI) directly without cross-conversion, and adding GLM-5 support.

## Objective
Analyze the current codebase to identify where format conversion happens and plan the new dual-route structure.

## Context
Repo: `/home/ubuntu/api-proxy`
Current state: The proxy likely converts everything to a common format or converts OpenAI requests to Anthropic format (or vice versa). We want to stop this.
Goal:
- `/v1/messages` -> Pass through to Anthropic-compatible providers (Claude).
- `/v1/chat/completions` -> Pass through to OpenAI-compatible providers (GLM-5, Kimi, DeepSeek).

## Actions
1. **Analyze Codebase**:
   - Read `src/proxy.py`, `src/app.py`, `src/main.py` (or similar entry points).
   - Locate the format conversion logic.
   - Understand how upstream providers are currently configured and selected.

2. **Identify Changes**:
   - What code needs to be deleted (conversion logic)?
   - What code needs to be added (routing logic based on endpoint)?
   - How to configure GLM-5?

3. **Output**:
   - Create a plan file: `data/api-proxy-refactor-plan.md` describing the proposed changes.

## Constraints
- Do NOT make changes yet. This is an exploration phase.
- Only read files.

## Completion
1. When the plan is written, run the completion command.
2. Send a notification to the task chat.

## Planner Callback
- On success: python3 /home/ubuntu/.openclaw/workspace/scripts/planner.py step-done oc_32156f6d4dfc8b49ffdf8523abdcab36 1 "Exploration complete. Plan saved to data/api-proxy-refactor-plan.md"
- On failure: python3 /home/ubuntu/.openclaw/workspace/scripts/planner.py step-fail oc_32156f6d4dfc8b49ffdf8523abdcab36 1 "<error reason>"
- Do NOT use the message tool to send messages
- Final reply MUST be NO_REPLY
