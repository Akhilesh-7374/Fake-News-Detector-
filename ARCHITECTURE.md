# Architecture & System Design

TrustSignal is an enterprise-grade real-time multimodal misinformation intelligence and claim verification platform.

---

## 1. System Overview

```text
                                [ Live Feeds / Inputs ]
                  (Google News RSS, BBC World, User Text, URL, Media)
                                         ↓
                       [ Ingestion & Normalization Layer ]
                                         ↓
                         [ Deduplication & Hash Engine ]
                                         ↓
                         [ Claim & Entity Segmentation ]
                                         ↓
  ┌──────────────────────────── Parallel Analysis ────────────────────────────┐
  │ • Baseline TF-IDF + Logistic Regression Classifier (With Checksum Safety)  │
  │ • Semantic Similarity & Story Cluster Engine                               │
  │ • Wikipedia Knowledge Evidence Provider & DuckDuckGo Context Engine        │
  │ • ClaimReview FactCheck Provider Interface                                 │
  │ • Source Intelligence & Publisher Reputation History                       │
  └───────────────────────────────────────────────────────────────────────────┘
                                         ↓
                     [ Transparent Signal Fusion Engine ]
                                         ↓
                         [ Uncertainty Decision Engine ]
                         (LIKELY REAL / LIKELY FAKE / UNCERTAIN)
                                         ↓
                        [ Explanation & Audit Logging ]
                                         ↓
                    [ Persistence Layer: SQLite / PostgreSQL ]
                                         ↓
            ┌───────────────────── Serving Interfaces ────────────────────┐
            │ • Streamlit SaaS Operations Dashboard                       │
            │ • FastAPI Production REST API (OpenAPI /docs)               │
            │ • Unified CLI Tool (src/cli.py)                             │
            │ • Background Job Worker & Alert Dispatcher                  │
            └─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Architectural Principles

1. **Responsible ML Decision Support:** The system never claims to know absolute truth. All outputs are calibrated style-risk estimates (`LIKELY REAL`, `LIKELY FAKE`, or `UNCERTAIN`).
2. **Zero-Key Public Default:** The entire pipeline functions out-of-the-box using free, zero-key public APIs (Google News RSS, BBC World RSS, Wikipedia API, DuckDuckGo API). Optional paid credentials (`NEWS_API_KEY`, `FACT_CHECK_API_KEY`) can be plugged in without architectural changes.
3. **No Magic Numbers:** All risk scores are calculated using an explicit, transparent formula combining ML probability, factual evidence stance, and source reputation.
4. **Auditability & Explainability:** Every prediction records why the decision was made, what evidence was retrieved, and allows human analysts to verify and override determinations.
