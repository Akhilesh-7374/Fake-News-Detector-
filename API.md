# TrustSignal REST API Reference

The TrustSignal REST API is powered by FastAPI, with interactive Swagger OpenAPI documentation available at `/docs` and ReDoc at `/redoc`.

---

## 1. Analysis Endpoints

### `POST /api/v1/analyze`
Analyze raw news text or headline through the ML and Wikipedia evidence fusion engine.

**Request:**
```json
{
  "text": "WASHINGTON (Reuters) - Federal Reserve officials approved a 25 basis point benchmark rate cut on Wednesday.",
  "source_name": "Reuters",
  "threshold": 0.50,
  "uncertainty_margin": 0.10
}
```

**Response:**
```json
{
  "status": "COMPLETED",
  "article_id": "b0af624986a1428b6648",
  "verdict": "LIKELY REAL",
  "risk_score": 24.15,
  "confidence": 0.8359,
  "ml_probability_fake": 0.082,
  "ml_label": "REAL",
  "reasons": [
    "Baseline TF-IDF/LR classifier estimated fake-style probability at 8.2%.",
    "External factual evidence was verified through Wikipedia context."
  ],
  "human_review_required": false,
  "claims_count": 2,
  "evidence_count": 2
}
```

### `POST /api/v1/analyze/url`
Scrape public web article with SSRF protection and execute analysis.
```json
{
  "url": "https://www.bbc.com/news/world-us-canada"
}
```

### `POST /api/v1/multimodal/analyze-file`
Multipart file upload accepting image (`.png`, `.jpg`, `.webp`), audio (`.mp3`, `.wav`), or video (`.mp4`, `.mov`). Max limit: 50 MB.

---

## 2. Articles & Evidence Endpoints

* `GET /api/v1/articles` — Paginated list of ingested articles (`?limit=25&offset=0`)
* `GET /api/v1/articles/{id}` — Full article record by ID
* `GET /api/v1/articles/{id}/claims` — Extracted claims and entities
* `GET /api/v1/articles/{id}/evidence` — Retrieved Wikipedia/web evidence and stance
* `GET /api/v1/articles/{id}/analysis` — Fused decision result and reasons

---

## 3. Sources & Story Clusters

* `GET /api/v1/sources` — List tracked news sources and reliability scores
* `GET /api/v1/sources/{id_or_domain}` — Source profile and historical distributions
* `GET /api/v1/stories` — Clustered news events with article counts and dominant claims
* `GET /api/v1/stories/{id}` — Story cluster detail

---

## 4. Reviews & Alerts

* `GET /api/v1/alerts` — Active consistency and threat alerts
* `POST /api/v1/reviews` — Submit human analyst verification:
```json
{
  "article_id": "b0af624986a1428b6648",
  "reviewer": "Jane Doe, Lead Analyst",
  "decision": "CONFIRMED REAL",
  "notes": "Verified against official central bank press release."
}
```

---

## 5. System Health & Model Telemetry

* `GET /api/v1/metrics` — Model accuracy, confusion matrix, and confounding scores
* `GET /api/v1/model-info` — Pipeline version, joblib checksum status
* `GET /api/v1/health` — Liveness probe
* `GET /api/v1/ready` — Readiness probe
