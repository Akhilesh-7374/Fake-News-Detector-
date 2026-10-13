"""Production FastAPI REST API for the Misinformation Intelligence Platform."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db.repository import Repository
from media_analyzer import MediaAnalyzer
from realtime_engine import RealTimeAnalyzer
from realtime_models import article_from_dict

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "outputs" / "pipeline.joblib"
METRICS_PATH = ROOT / "outputs" / "metrics.json"
DB_PATH = ROOT / "outputs" / "realtime.db"

app = FastAPI(
    title="TrustSignal Intelligence API",
    description="Enterprise Real-Time Multimodal Misinformation Intelligence & Claim Verification Platform REST API.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for secure web frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = Repository(DB_PATH)
analyzer = MediaAnalyzer(RealTimeAnalyzer(PIPELINE_PATH))


# ── Pydantic Request & Response Schemas ─────────────────────────────────────────

class AnalyzeTextRequest(BaseModel):
    text: str = Field(..., min_length=5, description="News text or headline to analyze")
    source_name: str = Field("Direct API", description="Optional publisher or source name")
    threshold: float = Field(0.50, ge=0.05, le=0.95, description="FAKE decision threshold")
    uncertainty_margin: float = Field(0.10, ge=0.0, le=0.30, description="Borderline margin for UNCERTAIN verdict")


class AnalyzeUrlRequest(BaseModel):
    url: str = Field(..., description="Public article URL to scrape and analyze")


class ReviewSubmissionRequest(BaseModel):
    article_id: str = Field(..., description="Target article ID")
    reviewer: str = Field(..., description="Analyst identity or username")
    decision: str = Field(..., pattern="^(CONFIRMED REAL|CONFIRMED FAKE|UNCERTAIN|NEED MORE EVIDENCE)$")
    notes: str = Field("", description="Review observations and evidence notes")


# ── Core Analysis Endpoints ───────────────────────────────────────────────────

@app.post("/api/v1/analyze", tags=["Analysis"])
def analyze_text_endpoint(req: AnalyzeTextRequest) -> dict[str, Any]:
    """Analyze raw news text through the baseline ML and Wikipedia evidence fusion pipeline."""
    if not PIPELINE_PATH.exists():
        raise HTTPException(status_code=503, detail="ML model artifact offline. Train pipeline first.")

    job = analyzer.analyze_text(req.text, source_name=req.source_name)
    res = job.analysis.get("result", {})
    art = job.analysis.get("article", {})
    now = art.get("ingested_at", "")

    # Persist in DB
    repo.save_article(art)
    if res:
        repo.save_prediction(res)
    repo.save_claims(job.analysis.get("claims", []))
    repo.save_evidence(job.analysis.get("evidence", []))

    return {
        "status": "COMPLETED",
        "article_id": art.get("id"),
        "verdict": res.get("verdict"),
        "risk_score": res.get("risk_score"),
        "confidence": res.get("confidence"),
        "ml_probability_fake": res.get("ml_probability_fake"),
        "ml_label": res.get("ml_label"),
        "reasons": res.get("reasons", []),
        "human_review_required": res.get("human_review_required", False),
        "claims_count": len(job.analysis.get("claims", [])),
        "evidence_count": len(job.analysis.get("evidence", [])),
    }


@app.post("/api/v1/analyze/url", tags=["Analysis"])
def analyze_url_endpoint(req: AnalyzeUrlRequest) -> dict[str, Any]:
    """Fetch external web article with SSRF protection and perform full verification."""
    job = analyzer.analyze_url(req.url)
    if job.status == "FAILED":
        raise HTTPException(status_code=400, detail=job.error or "URL analysis failed.")

    art = job.analysis.get("article", {})
    res = job.analysis.get("result", {})
    if art:
        repo.save_article(art)
    if res:
        repo.save_prediction(res)

    return {
        "status": job.status,
        "article": art,
        "analysis": res,
        "claims": job.analysis.get("claims", []),
        "evidence": job.analysis.get("evidence", []),
    }


@app.post("/api/v1/multimodal/analyze-file", tags=["Multimodal"])
async def analyze_file_endpoint(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload image, screenshot, audio, or video file for multimodal intelligence extraction."""
    upload_dir = ROOT / "outputs" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size exceeds 50 MB threshold.")

    file_path.write_bytes(content)
    job = analyzer.analyze_file(file_path)

    return {
        "job_id": job.id,
        "status": job.status,
        "media_type": job.media_type,
        "extracted_text": job.extracted_text,
        "warnings": job.warnings,
        "analysis": job.analysis.get("result", {}),
    }


# ── Articles & Evidence Endpoints ─────────────────────────────────────────────

@app.get("/api/v1/articles", tags=["Articles"])
def list_articles_endpoint(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List paginated ingested articles with analysis summaries."""
    articles = repo.list_articles(limit=limit, offset=offset)
    return {"total": repo.count_articles(), "limit": limit, "offset": offset, "items": articles}


@app.get("/api/v1/articles/{article_id}", tags=["Articles"])
def get_article_endpoint(article_id: str) -> dict[str, Any]:
    """Retrieve full article record by ID."""
    art = repo.get_article(article_id)
    if not art:
        raise HTTPException(status_code=404, detail="Article not found.")
    return art


@app.get("/api/v1/articles/{article_id}/claims", tags=["Articles"])
def get_article_claims_endpoint(article_id: str) -> list[dict[str, Any]]:
    """Retrieve segmented factual claims and named entities for an article."""
    return repo.get_claims_for_article(article_id)


@app.get("/api/v1/articles/{article_id}/evidence", tags=["Articles"])
def get_article_evidence_endpoint(article_id: str) -> list[dict[str, Any]]:
    """Retrieve retrieved external evidence and stance for an article."""
    return repo.get_evidence_for_article(article_id)


@app.get("/api/v1/articles/{article_id}/analysis", tags=["Articles"])
def get_article_analysis_endpoint(article_id: str) -> dict[str, Any]:
    """Retrieve full fused decision prediction and reasons for an article."""
    pred = repo.get_prediction(article_id)
    if not pred:
        raise HTTPException(status_code=404, detail="Analysis not found for this article.")
    return pred


# ── Sources & Stories Endpoints ───────────────────────────────────────────────

@app.get("/api/v1/sources", tags=["Sources"])
def list_sources_endpoint(limit: int = Query(50, ge=1, le=100)) -> list[dict[str, Any]]:
    """List tracked publisher sources and reliability history."""
    return repo.list_sources(limit=limit)


@app.get("/api/v1/sources/{source_id_or_domain}", tags=["Sources"])
def get_source_endpoint(source_id_or_domain: str) -> dict[str, Any]:
    """Get source intelligence profile and historical risk metrics."""
    src = repo.get_source(source_id_or_domain)
    if not src:
        raise HTTPException(status_code=404, detail="Source not found.")
    return src


@app.get("/api/v1/stories", tags=["Stories"])
def list_stories_endpoint(limit: int = Query(20, ge=1, le=50)) -> list[dict[str, Any]]:
    """List active clustered news events and aggregated risk metrics."""
    return repo.list_stories(limit=limit)


@app.get("/api/v1/stories/{story_id}", tags=["Stories"])
def get_story_endpoint(story_id: str) -> dict[str, Any]:
    """Get story cluster detail and connected articles."""
    stories = repo.list_stories(limit=100)
    match = next((s for s in stories if s["id"] == story_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Story not found.")
    return match


# ── Reviews & Alerts Endpoints ────────────────────────────────────────────────

@app.get("/api/v1/alerts", tags=["Alerts"])
def list_alerts_endpoint(unacknowledged_only: bool = False) -> list[dict[str, Any]]:
    """List active compliance alerts (high-risk content, conflicting evidence)."""
    return repo.list_alerts(unacknowledged_only=unacknowledged_only)


@app.post("/api/v1/reviews", tags=["Reviews"])
def submit_review_endpoint(req: ReviewSubmissionRequest) -> dict[str, Any]:
    """Submit analyst human-in-the-loop audit verification."""
    art = repo.get_article(req.article_id)
    if not art:
        raise HTTPException(status_code=404, detail="Target article not found.")

    review_id = repo.save_review(
        article_id=req.article_id,
        reviewer=req.reviewer,
        decision=req.decision,
        notes=req.notes,
    )
    return {"status": "RECORDED", "review_id": review_id, "decision": req.decision}


# ── System Telemetry & Model Info Endpoints ───────────────────────────────────

@app.get("/api/v1/metrics", tags=["System"])
def get_metrics_endpoint() -> dict[str, Any]:
    """Get holdout accuracy, confusion matrix, and source confounding diagnostics."""
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail="Metrics not found.")
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


@app.get("/api/v1/model-info", tags=["System"])
def get_model_info_endpoint() -> dict[str, Any]:
    """Get active baseline model version, pipeline path, and loading integrity."""
    return {
        "model_architecture": "TF-IDF (1-2 word ngrams) + Logistic Regression (C=1.0)",
        "pipeline_file": str(PIPELINE_PATH),
        "pipeline_exists": PIPELINE_PATH.exists(),
        "checksum_sidecar_exists": (PIPELINE_PATH.with_suffix(".joblib.sha256")).exists(),
        "status": "ONLINE" if PIPELINE_PATH.exists() else "OFFLINE",
    }


@app.get("/api/v1/health", tags=["System"])
@app.get("/health", tags=["System"])
def health_check() -> dict[str, Any]:
    """Liveness check probe."""
    return {"status": "healthy", "service": "trustsignal-intelligence", "version": "2.0.0"}


@app.get("/api/v1/ready", tags=["System"])
def readiness_check() -> dict[str, Any]:
    """Readiness check probe."""
    model_ready = PIPELINE_PATH.exists()
    db_ready = DB_PATH.exists() or DB_PATH.parent.exists()
    ready = model_ready and db_ready
    return {"ready": ready, "model_ready": model_ready, "db_ready": db_ready}
