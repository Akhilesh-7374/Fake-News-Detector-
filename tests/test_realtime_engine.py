from pathlib import Path

from realtime_engine import deduplicate_articles, extract_claims, fuse_signals
from realtime_models import Article, Evidence, content_hash


def test_article_hash_is_deterministic():
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("world")


def test_deduplication_removes_exact_content_duplicates():
    a = Article(id="1", title="A", content="same")
    b = Article(id="2", title="B", content="same")
    unique, dupes = deduplicate_articles([a, b])
    assert len(unique) == 1
    assert dupes == 1


def test_claim_extraction_has_stable_article_relationship():
    article = Article(id="x", title="", content="This is a sufficiently long factual statement for testing.")
    claims = extract_claims(article)
    assert claims
    assert claims[0].article_id == "x"


def test_fusion_returns_uncertain_without_evidence_near_boundary():
    result = fuse_signals(0.5, [], 50.0, "NOT_CHECKED")
    assert result.verdict == "UNCERTAIN"
    assert result.human_review_required


def test_fusion_can_flag_contradicted_high_risk_case():
    ev = [Evidence(id="e1", claim_id="c1", title="x", url="https://x", source="x", snippet="x", stance="CONTRADICTS", relevance_score=0.9)]
    result = fuse_signals(0.9, ev, 70.0, "CONTRADICTED")
    assert result.verdict == "LIKELY FAKE"
    assert result.risk_score >= 60
