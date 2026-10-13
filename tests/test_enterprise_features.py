"""Comprehensive enterprise integration and unit tests."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest
from db.repository import Repository
from decision_engine import DecisionEngine
from deduplication import DeduplicationEngine, canonicalize_url, jaccard_similarity
from realtime_models import Article, Claim, Evidence
from story_clustering import StoryClusterEngine


@pytest.fixture
def temp_repo(tmp_path):
    db_file = tmp_path / "test_repo.db"
    return Repository(db_file)


def test_url_canonicalization():
    url1 = "https://WWW.Example.com/news/article-1/?utm_source=twitter&utm_medium=social#ref"
    url2 = "https://example.com/news/article-1"
    assert canonicalize_url(url1) == canonicalize_url(url2)


def test_jaccard_similarity():
    s1 = "Breaking news economy inflation cools"
    s2 = "Breaking news economy inflation cools down sharply"
    sim = jaccard_similarity(s1, s2)
    assert sim > 0.60


def test_deduplication_engine():
    engine = DeduplicationEngine()
    art1 = Article(id="1", title="US Tech Stocks Rise", content="Stocks rallied on Friday.", url="https://reuters.com/stocks")
    art2 = Article(id="2", title="US Tech Stocks Rise", content="Stocks rallied on Friday.", url="https://reuters.com/stocks?utm_source=news")
    
    is_dupe1, reason1 = engine.is_duplicate(art1)
    assert not is_dupe1
    engine.register(art1)

    is_dupe2, reason2 = engine.is_duplicate(art2)
    assert is_dupe2
    assert reason2 == "EXACT_URL"


def test_repository_crud(temp_repo):
    art = {
        "id": "test-101",
        "title": "Central Bank Announces Rate Decision",
        "content": "Officials decided to pause rates.",
        "source_name": "Reuters",
        "source_domain": "reuters.com",
    }
    temp_repo.save_article(art)
    fetched = temp_repo.get_article("test-101")
    assert fetched is not None
    assert fetched["title"] == "Central Bank Announces Rate Decision"

    # Prediction save
    pred = {
        "article_id": "test-101",
        "ml_probability_fake": 0.15,
        "ml_label": "REAL",
        "evidence_score": 0.5,
        "source_risk_score": 30.0,
        "risk_score": 25.0,
        "confidence": 0.7,
        "verdict": "LIKELY REAL",
        "threshold": 0.5,
        "uncertainty_margin": 0.1,
        "reasons": ["Test explanation reason"],
        "human_review_required": False,
    }
    temp_repo.save_prediction(pred)
    fetched_pred = temp_repo.get_prediction("test-101")
    assert fetched_pred is not None
    assert fetched_pred["verdict"] == "LIKELY REAL"


def test_decision_engine():
    engine = DecisionEngine(threshold=0.50, uncertainty_margin=0.10)
    
    # 1. Obvious Real Case
    res_real = engine.evaluate(
        article_id="art-real",
        ml_prob_fake=0.08,
        evidence=[Evidence(id="e1", claim_id="c1", title="Wiki", url="", source="Wikipedia", snippet="", stance="SUPPORTS", relevance_score=0.8)],
        source_risk=25.0,
    )
    assert res_real.verdict == "LIKELY REAL"
    assert res_real.risk_score < 40.0
    assert len(res_real.reasons) >= 2

    # 2. Obvious Fake Case
    res_fake = engine.evaluate(
        article_id="art-fake",
        ml_prob_fake=0.92,
        evidence=[Evidence(id="e2", claim_id="c2", title="Wiki", url="", source="Wikipedia", snippet="", stance="CONTRADICTS", relevance_score=0.9)],
        source_risk=85.0,
    )
    assert res_fake.verdict == "LIKELY FAKE"
    assert res_fake.risk_score > 60.0

    # 3. Uncertain Borderline Case
    res_uncertain = engine.evaluate(
        article_id="art-unc",
        ml_prob_fake=0.49,
        evidence=[],
        source_risk=50.0,
    )
    assert res_uncertain.verdict == "UNCERTAIN"


def test_story_clustering():
    engine = StoryClusterEngine(similarity_threshold=0.30)
    s1 = engine.cluster_article("a1", "Global Climate Summit Concludes in Geneva", ["Summit ended"], 40.0, "Reuters")
    s2 = engine.cluster_article("a2", "Global Climate Summit Ends with New Accords", ["Accords signed"], 42.0, "BBC News")

    assert s1.id == s2.id
    assert s1.article_count == 2
    assert "Reuters" in s1.sources and "BBC News" in s1.sources
