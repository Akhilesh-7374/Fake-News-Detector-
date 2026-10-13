# TrustSignal Security & Threat Model

## 1. Security Architecture Overview

TrustSignal is designed with defense-in-depth principles for enterprise deployment.

---

## 2. Server-Side Request Forgery (SSRF) Protection

When users submit URLs for automated scraping and verification, the system enforces multi-layered SSRF defenses in `src/media_analyzer.py`:

* **Protocol Whitelist:** Only standard `http` and `https` schemes are accepted. Protocols like `file://`, `ftp://`, or `gopher://` are rejected immediately.
* **DNS Resolution & IP Verification:** Before initiating an HTTP connection, the domain is resolved to an IP address. Any attempt to reach loopback (`127.0.0.1`, `localhost`, `::1`), RFC-1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), or link-local/multicast ranges is blocked with an explicit security alert.
* **Strict Socket Timeouts:** Outbound scraping enforces an 8-second timeout to prevent resource exhaustion attacks.

---

## 3. Deserialization & ML Model Integrity

* **Cryptographic SHA-256 Sidecars:** Serialized model artifacts (`outputs/pipeline.joblib`) are verified against their SHA-256 digest (`outputs/pipeline.joblib.sha256`) before loading.
* **Tamper Prevention:** Any discrepancy between the file checksum and the recorded signature raises a `ValueError` and prevents model execution.

---

## 4. API Security & Input Sanitization

* **Input Length & MIME Validation:** REST endpoints enforce strict Pydantic payload constraints. Multimodal file uploads are capped at 50 MB to prevent denial-of-service (DoS).
* **HTML Stripping & XSS Defense:** All raw web content and RSS descriptions are sanitized using regular expression tag removal and HTML entity unescaping before reaching the database or frontend.
* **Secret Management:** Sensitive credentials (such as optional `NEWS_API_KEY` and `FACT_CHECK_API_KEY`) are loaded via environment variables and never exposed to the frontend or persisted in client sessions.

---

## 5. Reporting Security Issues

To report vulnerabilities or security concerns, open an issue in the project repository or contact the lead security architect.
