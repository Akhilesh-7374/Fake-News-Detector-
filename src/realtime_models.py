#!/usr/bin/env python3
"""Models and persistence helpers for the real-time misinformation platform."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import re
from typing import Any


@dataclass(slots=True)
class Article:
    id: str
    title: str
    content: str
    url: str = ""
    source_name: str = ""
    source_domain: str = ""
    author: str = ""
    published_at: str = ""
    ingested_at: str = ""
    language: str = ""
    country: str = ""
    category: str = ""
    image_url: str = ""
    content_hash: str = ""
    status: str = "NEW"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Claim:
    id: str
    article_id: str
    claim_text: str
    entities: list[str] = field(default_factory=list)
    topic: str = ""
    time_reference: str = ""
    location: str = ""
    claim_type: str = "statement"
    importance: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Evidence:
    id: str
    claim_id: str
    title: str
    url: str
    source: str
    snippet: str
    stance: str = "NEUTRAL"
    relevance_score: float = 0.0
    retrieved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnalysisResult:
    article_id: str
    verdict: str
    risk_score: float
    confidence: float
    ml_probability_fake: float
    ml_label: str
    evidence_score: float
    source_risk_score: float
    fact_check_status: str = "NOT_CHECKED"
    reasons: list[str] = field(default_factory=list)
    human_review_required: bool = False
    model_version: str = "baseline"
    analyzed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


def normalized_title(title: str) -> str:
    value = re.sub(r"[^a-z0-9\s]", " ", (title or "").lower())
    return re.sub(r"\s+", " ", value).strip()


def article_from_dict(payload: dict[str, Any]) -> Article:
    now = utc_now_iso()
    title = str(payload.get("title", "")).strip()
    content = str(payload.get("content", payload.get("description", ""))).strip()
    raw = f"{title}\n{content}\n{payload.get('url', '')}"
    return Article(
        id=str(payload.get("id") or content_hash(raw)[:20]),
        title=title,
        content=content,
        url=str(payload.get("url", "")).strip(),
        source_name=str(payload.get("source_name", payload.get("source", ""))).strip(),
        source_domain=str(payload.get("source_domain", "")).strip(),
        author=str(payload.get("author", "")).strip(),
        published_at=str(payload.get("published_at", "")).strip(),
        ingested_at=str(payload.get("ingested_at", now)).strip() or now,
        language=str(payload.get("language", "")).strip(),
        country=str(payload.get("country", "")).strip(),
        category=str(payload.get("category", "")).strip(),
        image_url=str(payload.get("image_url", "")).strip(),
        content_hash=str(payload.get("content_hash") or content_hash(content or title)),
    )
