#!/usr/bin/env python3
"""CLI worker for periodic news ingestion and automatic analysis with real live APIs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from news_providers import (
    BBCNewsRSSProvider,
    CompositeNewsProvider,
    GoogleNewsRSSProvider,
    WikipediaEvidenceProvider,
)
from realtime_engine import InMemoryNewsProvider, RealTimeAnalyzer, deduplicate_articles
from realtime_models import Article, utc_now_iso
from realtime_store import Store


def load_demo_articles(path: Path) -> list[Article]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Article(**item) for item in payload]


def get_provider(provider_type: str, demo_path: Path):
    pt = provider_type.lower()
    if pt == "google_news":
        return GoogleNewsRSSProvider(topic="TOP", limit=25)
    elif pt == "bbc":
        return BBCNewsRSSProvider(limit=25)
    elif pt == "demo":
        return InMemoryNewsProvider(load_demo_articles(demo_path))
    else:  # "composite" or "live"
        return CompositeNewsProvider([
            GoogleNewsRSSProvider(topic="TOP", limit=20),
            BBCNewsRSSProvider(limit=15),
        ])


def run_once(pipeline: Path, provider_type: str, demo_source: Path, db: Path, seen: set[str]) -> dict:
    provider = get_provider(provider_type, demo_source)
    raw_articles = provider.fetch_latest()
    # Fall back to demo if live feed is unavailable
    if not raw_articles and demo_source.exists():
        raw_articles = load_demo_articles(demo_source)

    articles, duplicates = deduplicate_articles(raw_articles, seen)
    analyzer = RealTimeAnalyzer(
        pipeline_path=pipeline,
        evidence_provider=WikipediaEvidenceProvider(),
    )
    store = Store(db)
    processed = 0
    for article in articles:
        result, claims, evidence = analyzer.analyze(article)
        now = utc_now_iso()
        store.save_article(article.to_dict(), now)
        store.save_analysis(result.to_dict(), now)
        store.save_claims([c.to_dict() for c in claims])
        store.save_evidence([e.to_dict() for e in evidence])
        seen.add(article.content_hash)
        processed += 1
    return {"provider": provider_type, "processed": processed, "duplicates": duplicates, "total_seen": len(seen)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the real-time news analysis worker with live Free APIs.")
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--pipeline", type=Path, default=root / "outputs" / "pipeline.joblib")
    parser.add_argument("--provider", type=str, default="composite", choices=["composite", "google_news", "bbc", "demo"], help="News provider to use.")
    parser.add_argument("--source", type=Path, default=root / "demo" / "news.json")
    parser.add_argument("--db", type=Path, default=root / "outputs" / "realtime.db")
    parser.add_argument("--interval", type=float, default=0.0, help="Seconds between ingestion cycles; 0 runs once.")
    args = parser.parse_args()

    seen: set[str] = set()
    while True:
        stats = run_once(args.pipeline, args.provider, args.source, args.db, seen)
        print(json.dumps(stats, indent=2))
        if args.interval <= 0:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
