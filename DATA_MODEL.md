# Data Model & Schema Architecture

TrustSignal uses a relational schema compatible with both SQLite and PostgreSQL.

---

## 1. Relational Entities

```text
[ articles ] ──< has >── [ claims ] ──< has >── [ evidence ]
     │                        │
     │                        └──< has >── [ fact_checks ]
     ├──< has >── [ predictions ]
     ├──< has >── [ reviews ]
     └──< belongs_to >── [ story_clusters ]
```

### Table: `articles`
* `id`: Unique SHA-256 derived article identifier
* `title`: Normalized headline
* `content`: Cleaned article text used for inference
* `raw_content`: Preserved original uncleaned text
* `source_domain`: Normalized domain name (e.g. `bbc.com`)
* `url`: Canonical source URL
* `ingested_at`: UTC ISO timestamp
* `content_hash`: SHA-256 fingerprint for deduplication

### Table: `claims`
* `id`: Unique claim identifier
* `article_id`: Foreign key to `articles(id)`
* `claim_text`: Specific verifiable assertion
* `entities`: JSON array of extracted entities (e.g. `["Federal Reserve", "Jerome Powell"]`)
* `importance`: Float weight (1.0 for headline claims, 0.7 for secondary)

### Table: `evidence`
* `id`: Unique evidence identifier
* `claim_id`: Foreign key to `claims(id)`
* `source`: Provider name (e.g. `Wikipedia`, `Web`)
* `title`: Article title
* `url`: Direct source link
* `snippet`: Contextual excerpt
* `stance`: `SUPPORTS`, `CONTRADICTS`, or `NEUTRAL`
* `relevance_score`: Relevance coefficient (0.0 to 1.0)

### Table: `predictions`
* `article_id`: Target article ID
* `model_version`: Active model architecture tag
* `ml_probability_fake`: Raw probability from Logistic Regression
* `risk_score`: Fused composite score (0 to 100)
* `verdict`: `LIKELY REAL`, `LIKELY FAKE`, or `UNCERTAIN`
* `reasons`: JSON array of explanatory audit justifications
* `human_review_required`: Flag indicating analyst review needed

### Table: `reviews`
* `id`: Review identifier
* `article_id`: Target article ID
* `reviewer`: Analyst name
* `decision`: `CONFIRMED REAL`, `CONFIRMED FAKE`, `UNCERTAIN`, `NEED MORE EVIDENCE`
* `notes`: Explanation and audit justification
