#!/usr/bin/env python3
"""Tests for lark_common.py — 验证公共模块的核心功能。

运行: python3 scripts/test_lark_common.py
"""

import json
import os
import sys
import time

# 确保能 import lark_common
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lark_common import (
    get_tenant_token,
    get_user_token,
    get_app_token,
    get_bot_info,
    get_chat_info,
    get_chat_members,
    send_message,
    lark_api,
    LarkAPIError,
    APP_ID,
    APP_SECRET,
    BASE_URL,
    BOT_OPEN_ID,
    CARL_OPEN_ID,
    CARL_MAIN_CHAT,
    USER_TOKEN_FILE,
    WORKSPACE,
)

passed = 0
failed = 0
errors = []


def test(name):
    """Decorator for test functions."""
    def decorator(fn):
        global passed, failed
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {name}: {e}")
            failed += 1
            errors.append((name, str(e)))
        except Exception as e:
            print(f"  ❌ {name}: {type(e).__name__}: {e}")
            failed += 1
            errors.append((name, f"{type(e).__name__}: {e}"))
    return decorator


# ─── Token 获取测试 ─────────────────────────────────────────────────────────────

print("\n🔑 Token 获取")


@test("tenant_token 返回非空字符串")
def _():
    token = get_tenant_token()
    assert isinstance(token, str) and len(token) > 10, f"Got: {token!r}"


@test("tenant_token 缓存生效（第二次不发请求）")
def _():
    t1 = get_tenant_token()
    t2 = get_tenant_token()
    assert t1 == t2, "Cache miss: tokens differ"


@test("tenant_token force_refresh 返回有效 token")
def _():
    token = get_tenant_token(force_refresh=True)
    assert isinstance(token, str) and len(token) > 10


@test("user_token 返回非空字符串")
def _():
    token = get_user_token()
    assert isinstance(token, str) and len(token) > 10


@test("app_token 返回非空字符串")
def _():
    token = get_app_token()
    assert isinstance(token, str) and len(token) > 10


# ─── 常量验证 ────────────────────────────────────────────────────────────────

print("\n📋 常量验证")


@test("APP_ID 格式正确")
def _():
    assert APP_ID.startswith("cli_"), f"Got: {APP_ID}"


@test("BASE_URL 包含 larksuite")
def _():
    assert "larksuite.com" in BASE_URL


@test("BOT_OPEN_ID 与实际匹配")
def _():
    info = get_bot_info()
    bot = info.get("bot", info)
    actual_id = bot.get("open_id")
    assert actual_id == BOT_OPEN_ID, f"Expected {BOT_OPEN_ID}, got {actual_id}"


@test("USER_TOKEN_FILE 存在")
def _():
    assert USER_TOKEN_FILE.exists(), f"Not found: {USER_TOKEN_FILE}"


@test("WORKSPACE 是有效目录")
def _():
    assert WORKSPACE.is_dir(), f"Not a dir: {WORKSPACE}"


# ─── lark_api 通用调用 ──────────────────────────────────────────────────────────

print("\n🌐 lark_api 通用调用")


@test("lark_api GET bot/v3/info 返回 bot 数据")
def _():
    data = lark_api("GET", "/bot/v3/info")
    assert "bot" in data or "open_id" in str(data), f"Unexpected: {list(data.keys())}"


@test("lark_api 支持 raw=True 返回完整响应")
def _():
    resp = lark_api("GET", "/bot/v3/info", raw=True)
    assert "code" in resp, f"Missing 'code' in raw response"
    assert resp["code"] == 0


@test("lark_api 无效 path 抛出 LarkAPIError")
def _():
    try:
        lark_api("GET", "/nonexistent/v1/fake")
        assert False, "Should have raised"
    except LarkAPIError:
        pass


@test("lark_api token_type='user' 自动获取 user_token")
def _():
    # 用日历 API 验证 user_token 能工作
    data = lark_api("GET", "/calendar/v4/calendars", token_type="user", raw=True)
    assert data.get("code") == 0, f"Calendar API failed: {data.get('msg')}"


# ─── 便捷函数 ──────────────────────────────────────────────────────────────────

print("\n🛠️ 便捷函数")


@test("get_chat_info 返回群名")
def _():
    info = get_chat_info(CARL_MAIN_CHAT)
    assert "name" in info, f"Missing 'name' in: {list(info.keys())}"


@test("get_chat_members 返回成员列表")
def _():
    members = get_chat_members(CARL_MAIN_CHAT)
    assert isinstance(members, list) and len(members) > 0, f"Got {len(members)} members"
    # 应至少包含 Carl
    member_ids = [m.get("member_id") for m in members]
    assert CARL_OPEN_ID in member_ids, f"Carl not found in members: {member_ids}"


@test("get_bot_info 返回正确 open_id")
def _():
    info = get_bot_info()
    bot = info.get("bot", info)
    assert bot.get("open_id") == BOT_OPEN_ID


# ─── LarkAPIError ──────────────────────────────────────────────────────────

print("\n⚠️ LarkAPIError")


@test("LarkAPIError 携带 code 和 response")
def _():
    try:
        # 用一个会返回错误的 API 调用
        lark_api("GET", "/im/v1/chats/invalid_chat_id_xxx")
        assert False, "Should have raised"
    except LarkAPIError as e:
        assert e.code is not None, "Missing error code"
        assert isinstance(e.response, dict), "Missing response dict"


@test("LarkAPIError 可以被 str() 转换")
def _():
    err = LarkAPIError("test error", code=99, response={"msg": "bad"})
    assert "test error" in str(err)
    assert err.code == 99


# ─── 结果汇总 ────────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
total = passed + failed
print(f"Results: {passed}/{total} passed, {failed} failed")

if errors:
    print("\nFailed tests:")
    for name, err in errors:
        print(f"  • {name}: {err}")

sys.exit(0 if failed == 0 else 1)
