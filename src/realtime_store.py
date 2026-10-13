#!/usr/bin/env python3
"""Unified persistence layer wrapping Repository for backward compatibility."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from db.repository import Repository


class Store:
    def __init__(self, path: str | Path) -> None:
        self.repo = Repository(path)

    def save_article(self, article: dict[str, Any], created_at: str) -> None:
        if "ingested_at" not in article:
            article["ingested_at"] = created_at
        self.repo.save_article(article)

    def save_analysis(self, analysis: dict[str, Any], created_at: str) -> None:
        if "analyzed_at" not in analysis:
            analysis["analyzed_at"] = created_at
        self.repo.save_prediction(analysis)
        # Also update source activity
        art = self.repo.get_article(analysis.get("article_id", ""))
        if art:
            self.repo.record_source_activity(
                domain=art.get("source_domain", ""),
                name=art.get("source_name", ""),
                verdict=analysis.get("verdict", ""),
            )

    def save_claims(self, claims: list[dict[str, Any]]) -> None:
        self.repo.save_claims(claims)

    def save_evidence(self, evidence: list[dict[str, Any]]) -> None:
        self.repo.save_evidence(evidence)

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.repo.get_recent_intelligence(limit=limit)
