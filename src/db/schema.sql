-- TrustSignal Enterprise Misinformation Defense Platform Database Schema
-- Compatible with SQLite and PostgreSQL syntax

CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    source_id TEXT,
    source_name TEXT,
    source_domain TEXT,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT NOT NULL,
    raw_content TEXT,
    author TEXT,
    url TEXT,
    published_at TEXT,
    ingested_at TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    country TEXT,
    category TEXT DEFAULT 'General',
    image_url TEXT,
    content_hash TEXT NOT NULL,
    status TEXT DEFAULT 'NEW'
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT NOT NULL UNIQUE,
    category TEXT,
    country TEXT,
    article_count INTEGER DEFAULT 0,
    historical_fake_count INTEGER DEFAULT 0,
    historical_real_count INTEGER DEFAULT 0,
    confirmed_fake_count INTEGER DEFAULT 0,
    confirmed_real_count INTEGER DEFAULT 0,
    source_risk_score REAL DEFAULT 50.0,
    reliability_tier TEXT DEFAULT 'UNRATED',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    entities TEXT,  -- JSON list of named entities
    topic TEXT,
    time_reference TEXT,
    location TEXT,
    claim_type TEXT DEFAULT 'statement',
    importance REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    source TEXT NOT NULL,
    source_domain TEXT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    snippet TEXT NOT NULL,
    stance TEXT DEFAULT 'NEUTRAL',  -- SUPPORTS | CONTRADICTS | NEUTRAL
    relevance_score REAL DEFAULT 0.5,
    retrieved_at TEXT NOT NULL,
    FOREIGN KEY(claim_id) REFERENCES claims(id)
);

CREATE TABLE IF NOT EXISTS fact_checks (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    rating TEXT,
    match_score REAL DEFAULT 0.0,
    retrieved_at TEXT NOT NULL,
    FOREIGN KEY(claim_id) REFERENCES claims(id)
);

CREATE TABLE IF NOT EXISTS predictions (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL UNIQUE,
    model_version TEXT NOT NULL,
    ml_probability_fake REAL NOT NULL,
    ml_label TEXT NOT NULL,
    evidence_score REAL NOT NULL,
    source_risk_score REAL NOT NULL,
    risk_score REAL NOT NULL,
    confidence REAL NOT NULL,
    verdict TEXT NOT NULL,  -- LIKELY REAL | LIKELY FAKE | UNCERTAIN
    threshold REAL NOT NULL,
    uncertainty_margin REAL NOT NULL,
    reasons TEXT NOT NULL,  -- JSON array of explanation strings
    human_review_required INTEGER DEFAULT 0,
    analyzed_at TEXT NOT NULL,
    FOREIGN KEY(article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS story_clusters (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    representative_title TEXT NOT NULL,
    dominant_claims TEXT,  -- JSON array
    article_count INTEGER DEFAULT 1,
    source_count INTEGER DEFAULT 1,
    average_risk REAL DEFAULT 50.0,
    status TEXT DEFAULT 'ACTIVE',
    first_seen_at TEXT NOT NULL,
    last_updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_articles (
    story_id TEXT NOT NULL,
    article_id TEXT NOT NULL,
    PRIMARY KEY(story_id, article_id),
    FOREIGN KEY(story_id) REFERENCES story_clusters(id),
    FOREIGN KEY(article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL,  -- CONFIRMED REAL | CONFIRMED FAKE | UNCERTAIN | NEED MORE EVIDENCE
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    article_id TEXT,
    story_id TEXT,
    alert_type TEXT NOT NULL,  -- HIGH_RISK_CLAIM | RAPID_GROWTH | EVIDENCE_CONFLICT | FACT_CHECK_CONTRADICTION
    severity TEXT NOT NULL,    -- HIGH | MEDIUM | LOW
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    acknowledged INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS media_assets (
    id TEXT PRIMARY KEY,
    media_type TEXT NOT NULL,  -- text | url | image | audio | video
    filename TEXT,
    mime_type TEXT,
    size_bytes INTEGER DEFAULT 0,
    sha256 TEXT NOT NULL,
    source_url TEXT,
    created_at TEXT NOT NULL,
    status TEXT DEFAULT 'READY'
);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    media_type TEXT NOT NULL,
    status TEXT DEFAULT 'QUEUED',  -- QUEUED | PROCESSING | COMPLETED | FAILED
    progress REAL DEFAULT 0.0,
    extracted_text TEXT,
    transcript TEXT,
    analysis_result TEXT,  -- JSON payload
    warnings TEXT,         -- JSON array
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(asset_id) REFERENCES media_assets(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details TEXT  -- JSON details
);

-- Indexes for high-throughput query performance
CREATE INDEX IF NOT EXISTS idx_articles_ingested ON articles(ingested_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_domain ON articles(source_domain);
CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_claims_article ON claims(article_id);
CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_predictions_verdict ON predictions(verdict);
CREATE INDEX IF NOT EXISTS idx_predictions_risk ON predictions(risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_story_articles_story ON story_articles(story_id);
CREATE INDEX IF NOT EXISTS idx_alerts_unread ON alerts(acknowledged, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON analysis_jobs(status, created_at);
