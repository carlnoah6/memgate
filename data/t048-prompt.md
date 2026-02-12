# Task t048: Refactor Daily Report Engine

You are tasked with refactoring the monolithic `scripts/daily-report-engine.py` into a modular package structure. This script is critical for daily operations, so stability is paramount.

## Objective
Split `scripts/daily-report-engine.py` (~1126 lines) into a Python package `scripts/daily_report/` with 5 modules, while keeping `scripts/daily-report-engine.py` as the CLI entry point.

## Target Structure
Create directory `scripts/daily_report/` and the following files:

1. **`scripts/daily_report/config.py`**
   - Move all constants (WORKSPACE, API_PROXY, KEYS, DIRS, EXTS, etc.) here.
   - Also include the common utility functions (`log`, `call_llm`, `run_cmd`, `read_file`) here as they are used globally.

2. **`scripts/daily_report/data_collector.py`**
   - Move `class DataCollector` here.
   - Import necessary libs and `config`.

3. **`scripts/daily_report/analyzer.py`**
   - Move `class LLMAnalyzer` here.
   - Import `config`.

4. **`scripts/daily_report/formatter.py`**
   - Move `class ReportAssembler` here.
   - Import `config`.

5. **`scripts/daily_report/delivery.py`**
   - Move `class ReportDelivery` here.
   - Import `config`.

6. **`scripts/daily-report-engine.py` (Entry Point)**
   - Keep this file at the root of `scripts/`.
   - Clear its content and rewrite it to import from `daily_report.*`.
   - It should contain the `main()` function and argument parsing logic.
   - Ensure it adds `scripts/` (or current dir) to sys.path if needed to resolve the package.

## Execution Steps
1. Create the `scripts/daily_report` directory.
2. Read `scripts/daily-report-engine.py` to get the source code.
3. Write the 5 module files (`config.py`, `data_collector.py`, etc.) with the extracted code. Ensure imports are correct (e.g., `from .config import log, run_cmd`).
4. Overwrite `scripts/daily-report-engine.py` with the new entry point code.
5. **Verification**: Run `python3 scripts/daily-report-engine.py --dry-run --fast` to ensure it still runs correctly.
   - If it fails, fix the import errors or bugs.
   - The output must end with "日报生成完成" (even in dry-run).

## Constraints
- Do NOT change the logic or functionality. This is a pure refactor.
- Maintain all logging output.
- Ensure `lark_common` usage (if you see any recent changes) is preserved. Note: The file I just read uses `lark-user-token.json` directly, which is fine, but if you see hardcoded credentials, check if you should use `lark_common`. (The current file reads token from json file, which is safe).

## Completion
Once the dry-run passes:
1. Run the task completion command provided in the footer.
2. Send a notification to the task chat.

## Planner Callback
- On success: python3 /home/ubuntu/.openclaw/workspace/scripts/planner.py step-done oc_7f3ebd31a5cf2fec9170952b29eb2700 7 "Refactored daily-report-engine.py into scripts/daily_report/ package (5 modules). Verified with --dry-run."
- On failure: python3 /home/ubuntu/.openclaw/workspace/scripts/planner.py step-fail oc_7f3ebd31a5cf2fec9170952b29eb2700 7 "<error reason>"
- Do NOT use the message tool to send messages
- Final reply MUST be NO_REPLY
