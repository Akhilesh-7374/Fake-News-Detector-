# Real-Time News Ingestion & Evidence Retrieval

## 1. Ingestion Pipeline

```text
[ Google News RSS ]  ──┐
[ BBC World Wire ]   ──┼──> [ CompositeNewsProvider ] ──> [ Deduplication Engine ]
[ Optional NewsAPI ] ──┘                                        ↓
                                                       [ Database Storage ]
                                                                ↓
                                                     [ RealTimeAnalyzer ]
```

## 2. Supported Live Providers

1. **Google News RSS Feed:** Real-time top headlines across World, Business, Technology, and Politics. Refreshes every 3 minutes.
2. **BBC News World RSS:** Verified international reporting from BBC World Service.
3. **Wikipedia Knowledge API:** Real-time query endpoint (`https://en.wikipedia.org/w/api.php`) for factual background checks and entity confirmation.

## 3. Rate Limiting & Backoff

* All network requests use non-blocking HTTP timeouts (3–8 seconds).
* Wikipedia query caching prevents duplicate requests for recurring entities across articles.
* The deduplication engine eliminates redundant inference on articles with identical content hashes or canonical URLs.
