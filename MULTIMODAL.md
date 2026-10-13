# Multimodal Intake Architecture

TrustSignal accepts multiple content formats through a unified analysis abstraction:

---

## 1. Input Types

| Format | Handler | Processing Mechanism |
|---|---|---|
| **Raw Text** | `analyze_text()` | TextCleaner → Claim Extraction → TF-IDF + LR Inference |
| **Web URL** | `analyze_url()` | SSRF-Protected Fetch → HTML Tag Stripping → Title & Paragraph Extraction |
| **Image / Screenshot** | `analyze_file()` | Best-effort OCR with Pillow & Tesseract |
| **Audio** | `analyze_file()` | Provider interface ready for speech-to-text transcription |
| **Video** | `analyze_file()` | Provider interface ready for frame keyframe extraction & audio stream processing |

---

## 2. SSRF Protection For URL Analysis

To prevent Server-Side Request Forgery (SSRF) when scraping user-provided links:
* Only `http` and `https` protocols are permitted.
* Hostnames resolving to loopback (`127.0.0.1`, `localhost`), private (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), or multicast IPs are blocked immediately before socket connection.
* Outbound requests enforce strict timeouts (8 seconds max).

---

## 3. Truthful Reporting Principle

If a speech model or local Tesseract binary is not installed on the system, the platform records:
`"No textual content extracted from media; external provider may be required."`
The system never fabricates transcriptions or simulated OCR text.
