#!/usr/bin/env python3
"""Provider-neutral real-time ingestion, claims, evidence, and decision engine."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Iterable, Protocol
from urllib.parse import urlparse

from detect_fake_news import classify_probability, predict_one
from realtime_models import Article, Claim, Evidence, AnalysisResult, utc_now_iso


class NewsProvider(Protocol):
    def fetch_latest(self) -> list[Article]: ...


class EvidenceProvider(Protocol):
    def search(self, claim: Claim) -> list[Evidence]: ...


class FactCheckProvider(Protocol):
    def search(self, claim: Claim) -> dict: ...


@dataclass(slots=True)
class InMemoryNewsProvider:
    articles: list[Article]

    def fetch_latest(self) -> list[Article]:
        return list(self.articles)


class NullEvidenceProvider:
    def search(self, claim: Claim) -> list[Evidence]:
        return []


class NullFactCheckProvider:
    def search(self, claim: Claim) -> dict:
        return {"status": "UNAVAILABLE", "matches": []}


def split_claims(text: str) -> list[str]:
    """Lightweight, dependency-free claim segmentation for MVP/demo use."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    claims = [s.strip() for s in sentences if len(s.strip()) >= 30]
    return claims[:10]


def extract_claims(article: Article) -> list[Claim]:
    source_text = f"{article.title}. {article.content}".strip()
    claims: list[Claim] = []
    for idx, text in enumerate(split_claims(source_text), start=1):
        entities = sorted(set(re.findall(r"\b[A-Z][A-Za-z0-9&.-]{2,}\b", text)))
        claims.append(
            Claim(
                id=f"{article.id}-c{idx}",
                article_id=article.id,
                claim_text=text,
                entities=entities[:12],
                importance=1.0 if idx <= 3 else 0.7,
            )
        )
    if not claims and article.title.strip():
        claims.append(
            Claim(id=f"{article.id}-c1", article_id=article.id, claim_text=article.title.strip())
        )
    return claims


def deduplicate_articles(articles: Iterable[Article], seen_hashes: set[str] | None = None) -> tuple[list[Article], int]:
    seen = set(seen_hashes or set())
    unique: list[Article] = []
    duplicates = 0
    for article in articles:
        fingerprint = article.content_hash or hashlib.sha256(article.content.encode("utf-8")).hexdigest()
        if article.url and article.url in seen:
            duplicates += 1
            continue
        if fingerprint in seen:
            duplicates += 1
            continue
        seen.add(fingerprint)
        if article.url:
            seen.add(article.url)
        unique.append(article)
    return unique, duplicates


def source_risk_score(article: Article) -> float:
    """Heuristic source risk proxy. This is not a truth score."""
    domain = (article.source_domain or urlparse(article.url).netloc).lower()
    score = 50.0
    if not domain:
        return score
    if domain.endswith(".gov") or domain.endswith(".edu"):
        score -= 20
    elif domain.endswith(".org"):
        score -= 5
    if any(token in domain for token in ("blog", "rumor", "viral", "click")):
        score += 15
    return max(0.0, min(100.0, score))


def fuse_signals(
    ml_prob_fake: float,
    evidence: list[Evidence],
    source_risk: float,
    fact_check_status: str,
    threshold: float = 0.5,
    uncertainty_margin: float = 0.10,
) -> AnalysisResult:
    contradiction = sum(e.relevance_score for e in evidence if e.stance == "CONTRADICTS")
    support = sum(e.relevance_score for e in evidence if e.stance == "SUPPORTS")
    total = contradiction + support
    evidence_score = 0.5 if total <= 0 else contradiction / total

    label = classify_probability(ml_prob_fake, threshold, uncertainty_margin)
    reasons: list[str] = [f"ML classifier fake probability is {ml_prob_fake:.1%}."]
    if contradiction > support and contradiction > 0:
        reasons.append("Retrieved evidence contains more contradictory than supporting signals.")
    elif support > contradiction and support > 0:
        reasons.append("Retrieved evidence contains more supporting than contradictory signals.")
    else:
        reasons.append("Evidence is unavailable or balanced, so external verification is limited.")

    if fact_check_status == "CONTRADICTED":
        reasons.append("A fact-check provider reports a conflicting verdict.")
    elif fact_check_status == "SUPPORTED":
        reasons.append("A fact-check provider reports a supporting verdict.")

    risk = 100.0 * (
        0.55 * ml_prob_fake
        + 0.25 * evidence_score
        + 0.20 * (source_risk / 100.0)
    )
    risk = max(0.0, min(100.0, risk))

    if fact_check_status == "CONTRADICTED":
        risk = min(100.0, risk + 15.0)
    elif fact_check_status == "SUPPORTED":
        risk = max(0.0, risk - 12.0)

    if label == "UNCERTAIN" or total == 0:
        verdict = "UNCERTAIN"
    elif risk >= 60:
        verdict = "LIKELY FAKE"
    else:
        verdict = "LIKELY REAL"

    confidence = max(0.0, min(1.0, abs(ml_prob_fake - 0.5) * 2.0))
    human_review = verdict == "UNCERTAIN" or fact_check_status in {"CONTRADICTED", "SUPPORTED"} or source_risk >= 70

    return AnalysisResult(
        article_id="",
        verdict=verdict,
        risk_score=round(risk, 2),
        confidence=round(confidence, 4),
        ml_probability_fake=ml_prob_fake,
        ml_label=label,
        evidence_score=round(evidence_score, 4),
        source_risk_score=round(source_risk, 2),
        fact_check_status=fact_check_status,
        reasons=reasons,
        human_review_required=human_review,
        analyzed_at=utc_now_iso(),
    )


class RealTimeAnalyzer:
    def __init__(
        self,
        pipeline_path,
        evidence_provider: EvidenceProvider | None = None,
        fact_check_provider: FactCheckProvider | None = None,
        threshold: float = 0.5,
        uncertainty_margin: float = 0.10,
    ) -> None:
        self.pipeline_path = pipeline_path
        self.evidence_provider = evidence_provider or NullEvidenceProvider()
        self.fact_check_provider = fact_check_provider or NullFactCheckProvider()
        self.threshold = threshold
        self.uncertainty_margin = uncertainty_margin
        from model_compat import load_pipeline
        self._pipeline = load_pipeline(pipeline_path) if Path(pipeline_path).exists() else None

    def analyze(self, article: Article) -> tuple[AnalysisResult, list[Claim], list[Evidence]]:
        text = f"{article.title}\n{article.content}".strip()
        if self._pipeline is not None:
            prob_fake = float(self._pipeline.predict_proba([text])[0, 1])
            label = classify_probability(prob_fake, self.threshold, self.uncertainty_margin)
        else:
            prediction = predict_one(
                self.pipeline_path,
                text,
                self.threshold,
                self.uncertainty_margin,
            )
            prob_fake = float(prediction["prob_fake"])
            label = str(prediction["label"])
        claims = extract_claims(article)
        evidence: list[Evidence] = []
        fact_status = "NOT_CHECKED"
        for claim in claims[:2]:
            evidence.extend(self.evidence_provider.search(claim))
            result = self.fact_check_provider.search(claim)
            status = str(result.get("status", "NO_MATCH")).upper()
            if status in {"CONTRADICTED", "SUPPORTED"}:
                fact_status = status
        fused = fuse_signals(
            prob_fake,
            evidence,
            source_risk_score(article),
            fact_status,
            self.threshold,
            self.uncertainty_margin,
        )
        fused.article_id = article.id
        fused.model_version = "tfidf-logreg-baseline"
        return fused, claims, evidence
