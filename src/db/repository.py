#!/usr/bin/env python3
"""Enterprise persistence repository supporting SQLite and PostgreSQL compatibility."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Repository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            # Check if legacy schema exists
            cols = [r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()]
            if cols and "ingested_at" not in cols:
                # Migrate legacy articles to articles_legacy
                conn.execute("ALTER TABLE articles RENAME TO articles_legacy;")
            schema_file = Path(__file__).resolve().parent / "schema.sql"
            if schema_file.exists():
                schema_sql = schema_file.read_text(encoding="utf-8")
                conn.executescript(schema_sql)

    # ── Articles ─────────────────────────────────────────────────────────────
    def save_article(self, article: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO articles (
                    id, source_id, source_name, source_domain, title, description,
                    content, raw_content, author, url, published_at, ingested_at,
                    language, country, category, image_url, content_hash, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    content=excluded.content,
                    status=excluded.status
                """,
                (
                    article["id"],
                    article.get("source_id", ""),
                    article.get("source_name", ""),
                    article.get("source_domain", ""),
                    article["title"],
                    article.get("description", ""),
                    article["content"],
                    article.get("raw_content", article["content"]),
                    article.get("author", ""),
                    article.get("url", ""),
                    article.get("published_at", ""),
                    article.get("ingested_at", ""),
                    article.get("language", "en"),
                    article.get("country", ""),
                    article.get("category", "General"),
                    article.get("image_url", ""),
                    article.get("content_hash", ""),
                    article.get("status", "NEW"),
                ),
            )

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
            return dict(row) if row else None

    def list_articles(self, limit: int = 50, offset: int = 0, status: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM articles WHERE status = ? ORDER BY ingested_at DESC LIMIT ? OFFSET ?",
                    (status, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM articles ORDER BY ingested_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            return [dict(r) for r in rows]

    def count_articles(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM articles").fetchone()
            return row[0] if row else 0

    # ── Sources ──────────────────────────────────────────────────────────────
    def record_source_activity(self, domain: str, name: str, verdict: str) -> None:
        if not domain:
            return
        now = article_now()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sources WHERE domain = ?", (domain,)).fetchone()
            if not row:
                source_id = f"src-{domain.replace('.', '-')}"
                is_fake = 1 if "FAKE" in verdict.upper() else 0
                is_real = 1 if "REAL" in verdict.upper() else 0
                conn.execute(
                    """
                    INSERT INTO sources (
                        id, name, domain, article_count, historical_fake_count, historical_real_count,
                        source_risk_score, reliability_tier, created_at, updated_at
                    ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        name or domain,
                        domain,
                        is_fake,
                        is_real,
                        75.0 if is_fake else 35.0,
                        "MODERATE",
                        now,
                        now,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE sources SET
                        article_count = article_count + 1,
                        historical_fake_count = historical_fake_count + ?,
                        historical_real_count = historical_real_count + ?,
                        updated_at = ?
                    WHERE domain = ?
                    """,
                    (1 if "FAKE" in verdict.upper() else 0, 1 if "REAL" in verdict.upper() else 0, now, domain),
                )

    def list_sources(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM sources ORDER BY article_count DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_source(self, source_id_or_domain: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE id = ? OR domain = ?",
                (source_id_or_domain, source_id_or_domain),
            ).fetchone()
            return dict(row) if row else None

    # ── Claims & Evidence ────────────────────────────────────────────────────
    def save_claims(self, claims: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            for c in claims:
                entities_str = json.dumps(c.get("entities", [])) if isinstance(c.get("entities"), list) else c.get("entities", "[]")
                conn.execute(
                    """
                    INSERT INTO claims (id, article_id, claim_text, entities, topic, time_reference, location, claim_type, importance, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET claim_text=excluded.claim_text
                    """,
                    (
                        c["id"],
                        c["article_id"],
                        c["claim_text"],
                        entities_str,
                        c.get("topic", ""),
                        c.get("time_reference", ""),
                        c.get("location", ""),
                        c.get("claim_type", "statement"),
                        c.get("importance", 1.0),
                        c.get("created_at", article_now()),
                    ),
                )

    def get_claims_for_article(self, article_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM claims WHERE article_id = ? ORDER BY importance DESC", (article_id,)).fetchall()
            claims = []
            for r in rows:
                item = dict(r)
                try:
                    item["entities"] = json.loads(item.get("entities") or "[]")
                except Exception:
                    item["entities"] = []
                claims.append(item)
            return claims

    def save_evidence(self, evidence_list: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            for ev in evidence_list:
                conn.execute(
                    """
                    INSERT INTO evidence (id, claim_id, source, source_domain, title, url, snippet, stance, relevance_score, retrieved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        ev["id"],
                        ev["claim_id"],
                        ev.get("source", "Web"),
                        ev.get("source_domain", ""),
                        ev.get("title", ""),
                        ev.get("url", ""),
                        ev.get("snippet", ""),
                        ev.get("stance", "NEUTRAL"),
                        ev.get("relevance_score", 0.5),
                        ev.get("retrieved_at", article_now()),
                    ),
                )

    def get_evidence_for_article(self, article_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT e.* FROM evidence e
                JOIN claims c ON e.claim_id = c.id
                WHERE c.article_id = ?
                """,
                (article_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Predictions / Fused Analysis ─────────────────────────────────────────
    def save_prediction(self, pred: dict[str, Any]) -> None:
        with self._connect() as conn:
            reasons_str = json.dumps(pred.get("reasons", [])) if isinstance(pred.get("reasons"), list) else pred.get("reasons", "[]")
            pred_id = pred.get("id") or f"pred-{pred['article_id']}"
            conn.execute(
                """
                INSERT INTO predictions (
                    id, article_id, model_version, ml_probability_fake, ml_label,
                    evidence_score, source_risk_score, risk_score, confidence,
                    verdict, threshold, uncertainty_margin, reasons, human_review_required, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    model_version=excluded.model_version,
                    risk_score=excluded.risk_score,
                    confidence=excluded.confidence,
                    verdict=excluded.verdict,
                    reasons=excluded.reasons,
                    human_review_required=excluded.human_review_required,
                    analyzed_at=excluded.analyzed_at
                """,
                (
                    pred_id,
                    pred["article_id"],
                    pred.get("model_version", "baseline"),
                    float(pred.get("ml_probability_fake", 0.5)),
                    pred.get("ml_label", "UNCERTAIN"),
                    float(pred.get("evidence_score", 0.5)),
                    float(pred.get("source_risk_score", 50.0)),
                    float(pred.get("risk_score", 50.0)),
                    float(pred.get("confidence", 0.0)),
                    pred.get("verdict", "UNCERTAIN"),
                    float(pred.get("threshold", 0.5)),
                    float(pred.get("uncertainty_margin", 0.1)),
                    reasons_str,
                    1 if pred.get("human_review_required") else 0,
                    pred.get("analyzed_at", article_now()),
                ),
            )

    def get_prediction(self, article_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM predictions WHERE article_id = ?", (article_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            try:
                item["reasons"] = json.loads(item.get("reasons") or "[]")
            except Exception:
                item["reasons"] = []
            item["human_review_required"] = bool(item.get("human_review_required"))
            return item

    # ── Feed & Detailed Articles Query ────────────────────────────────────────
    def get_recent_intelligence(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.id, a.title, a.content, a.url, a.source_name, a.source_domain,
                       a.author, a.published_at, a.ingested_at,
                       p.verdict, p.risk_score, p.confidence, p.ml_probability_fake,
                       p.reasons, p.human_review_required, p.analyzed_at
                FROM articles a
                LEFT JOIN predictions p ON p.article_id = a.id
                ORDER BY a.ingested_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            
            feed: list[dict[str, Any]] = []
            for r in rows:
                reasons = []
                if r["reasons"]:
                    try:
                        reasons = json.loads(r["reasons"])
                    except Exception:
                        reasons = []
                feed.append({
                    "article": {
                        "id": r["id"],
                        "title": r["title"],
                        "content": r["content"],
                        "url": r["url"],
                        "source_name": r["source_name"],
                        "source_domain": r["source_domain"],
                        "author": r["author"],
                        "published_at": r["published_at"],
                        "ingested_at": r["ingested_at"],
                    },
                    "analysis": {
                        "article_id": r["id"],
                        "verdict": r["verdict"] or "PENDING",
                        "risk_score": float(r["risk_score"] or 0.0),
                        "confidence": float(r["confidence"] or 0.0),
                        "ml_probability_fake": float(r["ml_probability_fake"] or 0.5),
                        "reasons": reasons,
                        "human_review_required": bool(r["human_review_required"]),
                        "analyzed_at": r["analyzed_at"] or "",
                    } if r["verdict"] else None
                })
            return feed

    # ── Human Reviews ────────────────────────────────────────────────────────
    def save_review(self, article_id: str, reviewer: str, decision: str, notes: str = "") -> str:
        import uuid
        now = article_now()
        review_id = f"rev-{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO reviews (id, article_id, reviewer, decision, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (review_id, article_id, reviewer, decision, notes, now),
            )
            # Log audit trail
            conn.execute(
                "INSERT INTO audit_logs (id, timestamp, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?, ?)",
                (f"audit-{uuid.uuid4().hex[:12]}", now, "HUMAN_REVIEW", "article", article_id, json.dumps({"decision": decision, "reviewer": reviewer, "notes": notes})),
            )
        return review_id

    def list_reviews(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.*, a.title FROM reviews r
                JOIN articles a ON r.article_id = a.id
                ORDER BY r.created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Alerts ───────────────────────────────────────────────────────────────
    def create_alert(self, article_id: str | None, story_id: str | None, alert_type: str, severity: str, message: str) -> str:
        import uuid
        alert_id = f"alt-{uuid.uuid4().hex[:12]}"
        now = article_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO alerts (id, article_id, story_id, alert_type, severity, message, created_at, acknowledged) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                (alert_id, article_id, story_id, alert_type, severity, message, now),
            )
        return alert_id

    def list_alerts(self, limit: int = 50, unacknowledged_only: bool = False) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if unacknowledged_only:
                rows = conn.execute("SELECT * FROM alerts WHERE acknowledged = 0 ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ── Stories / Clusters ───────────────────────────────────────────────────
    def save_story(self, story_id: str, topic: str, representative_title: str, dominant_claims: list[str], average_risk: float, article_ids: list[str]) -> None:
        now = article_now()
        claims_str = json.dumps(dominant_claims)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO story_clusters (id, topic, representative_title, dominant_claims, article_count, average_risk, first_seen_at, last_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    article_count=excluded.article_count,
                    average_risk=excluded.average_risk,
                    last_updated_at=excluded.last_updated_at
                """,
                (story_id, topic, representative_title, claims_str, len(article_ids), average_risk, now, now),
            )
            for aid in article_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO story_articles (story_id, article_id) VALUES (?, ?)",
                    (story_id, aid),
                )

    def list_stories(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM story_clusters ORDER BY last_updated_at DESC LIMIT ?", (limit,)).fetchall()
            stories = []
            for r in rows:
                item = dict(r)
                try:
                    item["dominant_claims"] = json.loads(item.get("dominant_claims") or "[]")
                except Exception:
                    item["dominant_claims"] = []
                stories.append(item)
            return stories


def article_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def time_now() -> float:
    import time
    return time.time()
