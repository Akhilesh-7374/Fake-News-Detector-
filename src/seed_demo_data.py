#!/usr/bin/env python3
"""Seed realistic story clusters, alerts, and human review records for company presentation."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from db.repository import Repository
from story_clustering import StoryClusterEngine

repo = Repository(ROOT / "outputs" / "realtime.db")

# 1. Cluster Existing Ingested Articles
articles = repo.list_articles(limit=50)
engine = StoryClusterEngine(similarity_threshold=0.25)

for art in articles:
    pred = repo.get_prediction(art["id"]) or {}
    risk = pred.get("risk_score", 45.0)
    claims = [c["claim_text"] for c in repo.get_claims_for_article(art["id"])]
    engine.cluster_article(
        article_id=art["id"],
        title=art["title"],
        claims=claims,
        risk_score=risk,
        source_name=art.get("source_name", "Wire"),
    )

for story in engine.get_active_stories():
    repo.save_story(
        story_id=story.id,
        topic=story.topic,
        representative_title=story.representative_title,
        dominant_claims=story.dominant_claims,
        average_risk=story.average_risk,
        article_ids=story.article_ids,
    )

# 2. Add realistic compliance alerts if empty
if not repo.list_alerts():
    repo.create_alert(
        article_id=articles[0]["id"] if articles else None,
        story_id=None,
        alert_type="HIGH_RISK_CLAIM",
        severity="HIGH",
        message="Coordinated clickbait narrative detected with unverified monetary policy claims.",
    )
    repo.create_alert(
        article_id=articles[1]["id"] if len(articles) > 1 else None,
        story_id=None,
        alert_type="RAPID_GROWTH",
        severity="MEDIUM",
        message="Story volume grew by +350% across 6 independent digital publishers within 30 minutes.",
    )

# 3. Add realistic human review records if empty
if not repo.list_reviews() and articles:
    repo.save_review(
        article_id=articles[0]["id"],
        reviewer="Alex Chen (Senior Compliance Officer)",
        decision="CONFIRMED REAL",
        notes="Corroborated with direct wire dispatch and official government release.",
    )
    if len(articles) > 1:
        repo.save_review(
            article_id=articles[1]["id"],
            reviewer="Sarah Jenkins (Lead Misinformation Analyst)",
            decision="CONFIRMED FAKE",
            notes="Identified recycled conspiracy narrative; flagged domain for automated review.",
        )

print(f"Enrichment complete! Stories: {len(repo.list_stories())}, Reviews: {len(repo.list_reviews())}, Alerts: {len(repo.list_alerts())}")
