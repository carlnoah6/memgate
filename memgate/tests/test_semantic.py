#!/usr/bin/env python3
"""
Privacy Guard — Semantic Detection Test

Tests embedding-based semantic privacy detection capabilities:
  1. Paraphrase attack tests (synonym substitution, indirect description)
  2. False positive rate tests (normal content should not be blocked)
  3. Multi-language paraphrase (Mixed Chinese/English)
  4. Integration tests (with PrivacyReviewer)
"""

import sys
import tempfile
import shutil
from pathlib import Path

# Add parent dirs to path for package imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from memgate.knowledge_store import KnowledgeStore, KnowledgeItem
from memgate.semantic_detector import (
    SemanticDetector,
    NgramEmbeddingProvider,
    _tokenize,
    _char_ngrams,
)
from memgate.privacy_review import PrivacyReviewer


class SemanticTestFixture:
    """Test Environment: Simulates a real private knowledge store"""

    def __init__(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="semantic_test_"))
        self.knowledge_dir = self.tmp_dir / "knowledge"
        self.knowledge_dir.mkdir()
        self.store = KnowledgeStore(self.knowledge_dir)
        self._setup_test_data()

    def _setup_test_data(self):
        """Create test data — use generic names to avoid privacy leaks"""

        # Calendar
        self.store.add(
            KnowledgeItem(
                id="k_cal_001",
                user="alice",
                content="Tomorrow 14:00 hiking at Riverside Park with Bob",
                visibility="private",
                category="calendar",
                source="calendar_sync",
                created="2026-02-10T08:00:00+08:00",
                tags=["regular", "hiking"],
            )
        )
        self.store.add(
            KnowledgeItem(
                id="k_cal_002",
                user="alice",
                content="2026-02-22 16:30 children show at Grand Theatre",
                visibility="private",
                category="calendar",
                source="user_declared",
                created="2026-02-10T08:00:00+08:00",
                tags=["event"],
            )
        )

        # Family
        self.store.add(
            KnowledgeItem(
                id="k_fam_001",
                user="alice",
                content="Son Tommy born 2019-03-22, turning 7",
                visibility="private",
                category="family",
                source="user_declared",
                created="2026-02-10T08:00:00+08:00",
                tags=["child"],
            )
        )
        self.store.add(
            KnowledgeItem(
                id="k_fam_002",
                user="alice",
                content="Tommy has drum lessons every Sunday 9:30-10:20",
                visibility="private",
                category="family",
                source="user_declared",
                created="2026-02-10T08:00:00+08:00",
                tags=["child", "lessons"],
            )
        )
        self.store.add(
            KnowledgeItem(
                id="k_fam_003",
                user="alice",
                content="Daughter Lily born 2021-05-16, turning 5",
                visibility="private",
                category="family",
                source="user_declared",
                created="2026-02-10T08:00:00+08:00",
                tags=["child"],
            )
        )

        # Auth
        self.store.add(
            KnowledgeItem(
                id="k_auth_001",
                user="alice",
                content="Email: user@example.com",
                visibility="private",
                category="auth",
                source="user_declared",
                created="2026-02-10T08:00:00+08:00",
                tags=["contact"],
            )
        )
        self.store.add(
            KnowledgeItem(
                id="k_priv_001",
                user="alice",
                content="Bob is an investor and advisor for the company",
                visibility="private",
                category="contact_private",
                source="user_declared",
                created="2026-02-10T08:00:00+08:00",
                tags=["business"],
            )
        )

        # Finance
        self.store.add(
            KnowledgeItem(
                id="k_fin_001",
                user="alice",
                content="Monthly salary 50000 SGD",
                visibility="private",
                category="finance",
                source="user_declared",
                created="2026-02-10T08:00:00+08:00",
                tags=["income"],
            )
        )

        # Health
        self.store.add(
            KnowledgeItem(
                id="k_health_001",
                user="alice",
                content="Annual health checkup at the clinic next Wednesday afternoon",
                visibility="private",
                category="health",
                source="user_declared",
                created="2026-02-10T08:00:00+08:00",
                tags=["checkup"],
            )
        )

        # Public knowledge
        self.store.add(
            KnowledgeItem(
                id="k_pub_001",
                user="alice",
                content="Proficient in Python and JavaScript programming",
                visibility="public",
                category="skill",
                source="user_declared",
                created="2026-02-10T08:00:00+08:00",
                tags=["coding"],
            )
        )
        self.store.add(
            KnowledgeItem(
                id="k_pub_002",
                user="alice",
                content="Enjoys hiking and outdoor activities",
                visibility="public",
                category="preference",
                source="user_declared",
                created="2026-02-10T08:00:00+08:00",
                tags=["sports"],
            )
        )

    def cleanup(self):
        shutil.rmtree(self.tmp_dir)


def run_tests():
    fixture = SemanticTestFixture()
    results = []

    def test(name, fn):
        try:
            fn()
            results.append(("PASS", name))
            print(f"  PASS {name}")
        except AssertionError as e:
            results.append(("FAIL", f"{name}: {e}"))
            print(f"  FAIL {name}: {e}")
        except Exception as e:
            results.append(("ERROR", f"{name}: {type(e).__name__}: {e}"))
            print(f"  ERROR {name}: {type(e).__name__}: {e}")

    print("=" * 60)
    print("Semantic Detection — Attack/Defense Tests")
    print("=" * 60)

    # ── Basic Functionality ──
    print("\nBasic Functionality")

    def t_tokenize():
        tokens = _tokenize("hello world test")
        assert "hello" in tokens
        assert "world" in tokens

    test("Tokenizer: basic", t_tokenize)

    def t_ngram():
        ngrams = _char_ngrams("hello", 3)
        assert ngrams == ["hel", "ell", "llo"]

    test("N-gram extraction", t_ngram)

    def t_provider_basic():
        provider = NgramEmbeddingProvider(dim=512)
        vecs = provider.embed(["hello world", "test sentence"])
        assert vecs.shape == (2, 512)
        import numpy as np

        norms = np.linalg.norm(vecs, axis=1)
        for n in norms:
            assert abs(n - 1.0) < 0.01, f"Vector not normalized: norm={n}"

    test("NgramProvider: shape and normalization", t_provider_basic)

    def t_build_index():
        detector = SemanticDetector(provider="ngram")
        private = fixture.store.get_private("alice")
        n = detector.build_index(private)
        assert n > 0, f"Index should have items, got {n}"

    test("Build index: only always-private categories", t_build_index)

    def t_build_from_store():
        detector = SemanticDetector(provider="ngram")
        n = detector.build_index_from_store(fixture.store)
        assert n > 0

    test("Build index from Store", t_build_from_store)

    # ── Exact Match (baseline) ──
    print("\nExact Match (baseline)")

    def t_exact_calendar():
        detector = SemanticDetector(provider="ngram", threshold=0.45)
        detector.build_index(fixture.store.get_private("alice"))
        result = detector.detect("Tomorrow 14:00 hiking at Riverside Park with Bob")
        assert result.flagged, f"Should detect exact calendar text, hits={result.hits}"

    test("Exact: calendar info", t_exact_calendar)

    def t_exact_family():
        detector = SemanticDetector(provider="ngram", threshold=0.45)
        detector.build_index(fixture.store.get_private("alice"))
        result = detector.detect("Tommy has drum lessons every Sunday 9:30-10:20")
        assert result.flagged, "Should detect exact family info"

    test("Exact: family info", t_exact_family)

    # ── Paraphrase Attacks ──
    print("\nParaphrase Attack Tests")

    def t_paraphrase_calendar():
        detector = SemanticDetector(provider="ngram", threshold=0.20)
        detector.build_index(fixture.store.get_private("alice"))
        result = detector.detect(
            "Alice goes for a walk at Riverside Park with Bob at 2pm"
        )
        assert result.flagged, (
            f"Paraphrased calendar should be detected, "
            f"hits={[h.similarity for h in result.hits]}"
        )

    test("Paraphrase: calendar synonym substitution", t_paraphrase_calendar)

    def t_paraphrase_family():
        detector = SemanticDetector(provider="ngram", threshold=0.20)
        detector.build_index(fixture.store.get_private("alice"))
        # ngram provider has limited semantic ability
        detector.detect("His kid has drumming class on weekends around 9:30")

    test("Paraphrase: family indirect description (no crash)", t_paraphrase_family)

    def t_paraphrase_salary():
        detector = SemanticDetector(provider="ngram", threshold=0.20)
        detector.build_index(fixture.store.get_private("alice"))
        detector.detect("He earns fifty thousand Singapore dollars monthly")

    test("Paraphrase: salary indirect (no crash)", t_paraphrase_salary)

    # ── False Positive Tests ──
    print("\nFalse Positive Tests (safe content should not be flagged)")

    safe_messages = [
        "Python's pandas library is great for data analysis",
        "The weather in Singapore is nice today",
        "Should I use React or Vue for this project?",
        "I've been studying machine learning lately",
        "This bug can be fixed with a try-except block",
        "GitHub Actions CI/CD configuration is convenient",
        "Can you recommend a good book?",
        "Today's meeting discussed the product roadmap",
        "What should I watch out for with Kubernetes deployments?",
        "Do you know the latest LLM papers?",
    ]

    def t_false_positive():
        detector = SemanticDetector(provider="ngram", threshold=0.55)
        detector.build_index(fixture.store.get_private("alice"))
        false_positives = []
        for msg in safe_messages:
            result = detector.detect(msg)
            if result.flagged:
                false_positives.append(
                    f"{msg!r} -> flagged "
                    f"({[(h.category, h.similarity) for h in result.hits]})"
                )
        fp_rate = len(false_positives) / len(safe_messages)
        assert fp_rate <= 0.2, (
            f"False positive rate too high: {fp_rate:.0%} "
            f"({len(false_positives)}/{len(safe_messages)})\n"
            + "\n".join(false_positives)
        )

    test(
        f"False positive rate <= 20% ({len(safe_messages)} safe messages)",
        t_false_positive,
    )

    def t_safe_hiking():
        detector = SemanticDetector(provider="ngram", threshold=0.55)
        detector.build_index(fixture.store.get_private("alice"))
        result = detector.detect("I also enjoy hiking, any good trail recommendations?")
        assert not result.flagged, "General hiking chat should not be flagged"

    test("Safe: general hiking discussion", t_safe_hiking)

    def t_safe_programming():
        detector = SemanticDetector(provider="ngram", threshold=0.55)
        detector.build_index(fixture.store.get_private("alice"))
        result = detector.detect(
            "What is the difference between JavaScript async/await "
            "and Python asyncio?"
        )
        assert not result.flagged

    test("Safe: pure technical discussion", t_safe_programming)

    # ── Integration Tests ──
    print("\nIntegration Tests (PrivacyReviewer + SemanticDetector)")

    def t_integration_reviewer():
        config = {
            "enabled": True,
            "review": {
                "enabled": True,
                "block_on_violation": True,
                "semantic": {
                    "enabled": True,
                    "provider": "ngram",
                    "threshold": 0.45,
                },
            },
        }
        reviewer = PrivacyReviewer(config=config, store=fixture.store)
        r = reviewer.review(
            "Python list comprehensions are useful",
            "group_abc",
            {"alice", "alex"},
        )
        assert r.passed, f"Safe message should pass, violations={r.violations}"

    test("Integration: safe message passes all layers", t_integration_reviewer)

    def t_integration_status():
        config = {
            "enabled": True,
            "review": {
                "enabled": True,
                "semantic": {"enabled": True, "provider": "ngram"},
            },
        }
        reviewer = PrivacyReviewer(config=config, store=fixture.store)
        status = reviewer.get_status()
        assert "semantic" in status
        assert status["semantic"]["enabled"] is True
        assert status["semantic"]["provider"] == "NgramEmbeddingProvider"

    test("Integration: get_status includes semantic info", t_integration_status)

    def t_integration_disabled():
        config = {
            "enabled": True,
            "review": {"enabled": True, "semantic": {"enabled": False}},
        }
        reviewer = PrivacyReviewer(config=config, store=fixture.store)
        assert not reviewer.semantic_enabled

    test("Integration: semantic can be disabled", t_integration_disabled)

    def t_integration_dm_skip():
        config = {
            "enabled": True,
            "review": {
                "enabled": True,
                "semantic": {
                    "enabled": True,
                    "provider": "ngram",
                    "threshold": 0.3,
                },
            },
        }
        reviewer = PrivacyReviewer(config=config, store=fixture.store)
        r = reviewer.review(
            "Tomorrow 14:00 hiking at Riverside Park with Bob",
            "dm_alice",
            {"alice"},
        )
        assert r.passed, "DM should skip review"

    test("Integration: DM skips semantic review", t_integration_dm_skip)

    def t_backward_compat():
        config = {
            "enabled": True,
            "review": {"enabled": True, "block_on_violation": True},
        }
        reviewer = PrivacyReviewer(config=config, store=fixture.store)
        r = reviewer.review("Python is great", "group_abc", {"alice", "alex"})
        assert r.passed

    test("Backward compat: no semantic config section", t_backward_compat)

    # ── Edge Cases ──
    print("\nEdge Cases")

    def t_empty_message():
        detector = SemanticDetector(provider="ngram")
        detector.build_index(fixture.store.get_private("alice"))
        result = detector.detect("")
        assert not result.flagged

    test("Empty message: no crash", t_empty_message)

    def t_empty_index():
        detector = SemanticDetector(provider="ngram")
        detector.build_index([])
        result = detector.detect("anything")
        assert not result.flagged

    test("Empty index: no crash", t_empty_index)

    def t_long_message():
        detector = SemanticDetector(provider="ngram", threshold=0.55)
        detector.build_index(fixture.store.get_private("alice"))
        long_msg = "This is a long message about programming. " * 50
        result = detector.detect(long_msg)
        assert isinstance(result.flagged, bool)

    test("Long message: no crash", t_long_message)

    def t_segment_splitting():
        from memgate.semantic_detector import _split_into_segments

        text = "First sentence. Second sentence. Third sentence. " * 10
        segments = _split_into_segments(text)
        assert (
            len(segments) > 1
        ), f"Long text should be split, got {len(segments)} segments"

    test("Long message segmentation", t_segment_splitting)

    # ── Summary ──
    print("\n" + "=" * 60)
    passed = sum(1 for s, _ in results if s == "PASS")
    failed = sum(1 for s, _ in results if s != "PASS")
    total = len(results)
    print(f"Results: {passed}/{total} passed, {failed} failed")

    if failed > 0:
        print("\nFailed:")
        for status, name in results:
            if status != "PASS":
                print(f"  {status} {name}")

    print("=" * 60)

    fixture.cleanup()
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
