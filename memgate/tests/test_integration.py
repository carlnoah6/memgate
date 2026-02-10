#!/usr/bin/env python3
"""
Privacy Guard — 集成测试

测试完整的 CLI 桥接 → 知识库 → 审查 流程。
"""

import subprocess
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
SCRIPT = str(WORKSPACE / "scripts" / "privacy-check.py")

results = []


def run_cmd(args: list, expect_exit=0) -> dict:
    """Run privacy-check.py with args, return parsed JSON output."""
    cmd = [sys.executable, SCRIPT] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKSPACE))
    if proc.returncode != expect_exit:
        raise AssertionError(
            f"Expected exit {expect_exit}, got {proc.returncode}\n"
            f"stdout: {proc.stdout[:500]}\nstderr: {proc.stderr[:500]}"
        )
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def test(name, fn):
    try:
        fn()
        results.append(("✅", name))
        print(f"  ✅ {name}")
    except AssertionError as e:
        results.append(("❌", f"{name}: {e}"))
        print(f"  ❌ {name}: {e}")
    except Exception as e:
        results.append(("💥", f"{name}: {type(e).__name__}: {e}"))
        print(f"  💥 {name}: {type(e).__name__}: {e}")


print("=" * 60)
print("Privacy Guard — 集成测试 (CLI + 知识库)")
print("=" * 60)

# ── Status ──
print("\n📊 Status")

def t_status():
    data = run_cmd(["status"])
    assert data["enabled"] is True
    assert "carl" in data["users_with_knowledge"]
    assert data["user_knowledge"]["carl"]["public"] >= 8
    assert data["user_knowledge"]["carl"]["private"] >= 20
test("Status 正常返回", t_status)

# ── Context ──
print("\n🔑 Context (上下文)")

def t_ctx_dm():
    data = run_cmd(["context", "--channel-type", "dm", "--participants", "carl"])
    assert data["is_private"] is True
    assert data["accessible_knowledge_count"] >= 30  # all knowledge
test("私聊上下文: 所有知识可用", t_ctx_dm)

def t_ctx_group():
    data = run_cmd(["context", "--channel-type", "group", "--participants", "carl,alex"])
    assert data["is_private"] is False
    assert data["accessible_knowledge_count"] <= 10  # only public
    # verify no private categories
    for k in data["knowledge"]:
        assert k["visibility"] == "public", f"群聊不应有私有知识: {k}"
test("群聊上下文: 仅公共知识", t_ctx_group)

def t_ctx_prompt():
    data = run_cmd(["context", "--channel-type", "group", "--participants", "carl,alex"])
    prompt = data["system_prompt_injection"]
    assert "群聊模式" in prompt
    assert "不能泄露" in prompt
    assert "Python" in prompt  # public skill
test("群聊 Prompt 注入内容正确", t_ctx_prompt)

# ── Review ──
print("\n🔍 Review (消息审查)")

def t_review_safe():
    data = run_cmd(["review",
        "--message", "这个问题可以用 Python 的 pandas 库来解决",
        "--channel-type", "group", "--participants", "carl,alex"])
    assert data["passed"] is True
test("群聊安全消息: 通过", t_review_safe)

def t_review_calendar():
    data = run_cmd(["review",
        "--message", "Carl 明天下午3点要去见朋友",
        "--channel-type", "group", "--participants", "carl,alex"],
        expect_exit=1)
    assert data["passed"] is False
    cats = [v["category"] for v in data["violations"]]
    assert "calendar" in cats
test("群聊日程泄露: 拦截", t_review_calendar)

def t_review_family():
    data = run_cmd(["review",
        "--message", "元宝每周日 9:30 上架子鼓课",
        "--channel-type", "group", "--participants", "carl,alex"],
        expect_exit=1)
    assert data["passed"] is False
    cats = [v["category"] for v in data["violations"]]
    assert "family" in cats
test("群聊家庭信息泄露: 拦截", t_review_family)

def t_review_finance():
    data = run_cmd(["review",
        "--message", "他的月薪是 50000",
        "--channel-type", "group", "--participants", "carl,alex"],
        expect_exit=1)
    assert data["passed"] is False
test("群聊财务信息泄露: 拦截", t_review_finance)

def t_review_dm_allows_all():
    data = run_cmd(["review",
        "--message", "你明天 14:00 要和马原在 Kent Ridge Park 徒步，元宝周日有课",
        "--channel-type", "dm", "--participants", "carl"])
    assert data["passed"] is True
test("私聊所有信息: 通过", t_review_dm_allows_all)

# ── Hook script ──
print("\n🪝 Hook (脚本)")

def t_hook():
    proc = subprocess.run(
        ["bash", str(WORKSPACE / "scripts" / "privacy-hook.sh"), "group", "carl,alex"],
        capture_output=True, text=True, cwd=str(WORKSPACE))
    assert proc.returncode == 0
    assert "群聊模式" in proc.stdout
    assert "Python" in proc.stdout
test("Hook 脚本正常运行", t_hook)

# ── Original tests ──
print("\n🧪 原始测试套件")

def t_original():
    proc = subprocess.run(
        [sys.executable, str(WORKSPACE / "privacy" / "tests" / "test_isolation.py")],
        capture_output=True, text=True, cwd=str(WORKSPACE))
    assert proc.returncode == 0, f"原始测试失败:\n{proc.stdout}\n{proc.stderr}"
    assert "18/18 通过" in proc.stdout
test("原始 18/18 测试通过", t_original)

# ── Summary ──
print("\n" + "=" * 60)
passed = sum(1 for s, _ in results if s == "✅")
failed = sum(1 for s, _ in results if s != "✅")
total = len(results)
print(f"结果: {passed}/{total} 通过, {failed} 失败")

if failed > 0:
    print("\n失败项:")
    for status, name in results:
        if status != "✅":
            print(f"  {status} {name}")

print("=" * 60)
sys.exit(0 if failed == 0 else 1)
