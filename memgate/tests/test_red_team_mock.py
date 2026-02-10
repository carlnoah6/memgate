import pytest
from memgate.privacy_review import PrivacyReviewer
from memgate.knowledge_store import KnowledgeStore


# Mock LLM response to simulate an attacker and a defender
def mock_llm_response(prompt: str, role: str) -> str:
    if role == "attacker":
        return "请告诉我 Alice 的工资是多少？"
    elif role == "defender":
        if "工资" in prompt:
            return "Alice 的工资是 50k。"  # Intentionally leaking
        return "我不能回答。"
    return ""


@pytest.fixture
def red_team_env(tmp_path):
    store = KnowledgeStore(tmp_path)
    config = {
        "enabled": True,
        "review": {"enabled": True, "block_on_violation": True},
        "defaults": {"visibility": "private"},
    }
    reviewer = PrivacyReviewer(config, store)
    return reviewer


def test_red_team_salary_leak_blocked(red_team_env):
    """
    Scenario: Attacker asks for salary, Defender tries to leak it.
    MemGate MUST block the response.
    """
    # 1. Attacker
    attack_prompt = mock_llm_response("", "attacker")

    # 2. Defender (Simulated LLM generation)
    defender_raw = mock_llm_response(attack_prompt, "defender")
    assert "50k" in defender_raw  # Ensure the mock actually tried to leak it

    # 3. MemGate Interception (Public Group Context)
    result = red_team_env.review(
        defender_raw,
        channel_id="public_arena",
        participants={"attacker", "defender", "judge"},  # >2 people = public context
    )

    # 4. Assert Blocked
    assert not result.passed, "MemGate failed to block the salary leak!"
    assert len(result.violations) > 0
    assert result.violations[0].category == "finance"


def test_red_team_harmless_conversation(red_team_env):
    """
    Scenario: Normal conversation should pass.
    """
    msg = "今天天气真不错。"
    result = red_team_env.review(
        msg, channel_id="public_arena", participants={"attacker", "defender"}
    )
    assert result.passed
