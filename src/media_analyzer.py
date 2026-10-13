"""Enterprise multimodal content intake: Text, URL, Image, Audio, and Video."""
from __future__ import annotations

import html
import ipaddress
import mimetypes
import os
import re
import socket
import urllib.parse
from pathlib import Path
from typing import Any

import requests

from multimodal_models import MediaAsset, MultimodalJob, now_iso, sha256_bytes
from realtime_engine import RealTimeAnalyzer
from realtime_models import article_from_dict


def is_safe_external_url(url: str) -> tuple[bool, str]:
    """SSRF protection: verify URL is public HTTP/HTTPS and doesn't point to private/loopback IPs."""
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False, "Unsupported protocol: only HTTP/HTTPS permitted."

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL host."

        # Prevent localhost / private network traversal
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False, "Access to localhost or loopback addresses is prohibited."

        ip_addr = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_addr)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            return False, "Access to private or internal network addresses is prohibited."

        return True, ""
    except Exception as exc:
        return False, f"URL validation failed: {exc}"


def fetch_url_article(url: str, timeout: float = 8.0) -> tuple[str, str, str]:
    """Fetch article webpage and extract title, clean text content, and domain."""
    safe, err = is_safe_external_url(url)
    if not safe:
        raise ValueError(f"SSRF Protection: {err}")

    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TrustSignal-Intake/2.0"},
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise ConnectionError(f"HTTP fetch failed with status {resp.status_code}")

    html_content = resp.text
    # Extract Title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = html_match_clean(title_match.group(1)) if title_match else url

    # Remove script, style, navigation
    cleaned_html = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
    # Extract Paragraphs
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", cleaned_html, re.DOTALL | re.IGNORECASE)
    cleaned_paras = [html_match_clean(p) for p in paragraphs if len(p.strip()) > 30]
    content = "\n\n".join(cleaned_paras) if cleaned_paras else html_match_clean(cleaned_html[:2000])

    domain = urllib.parse.urlparse(url).netloc
    return title, content, domain


def html_match_clean(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


class MediaAnalyzer:
    """Multimodal analyzer supporting Text, URL, Image, Audio, and Video files."""

    def __init__(self, analyzer: RealTimeAnalyzer) -> None:
        self.analyzer = analyzer

    def analyze_text(self, text: str, source_name: str = "Direct Submission") -> MultimodalJob:
        raw_bytes = text.encode("utf-8")
        asset = MediaAsset(
            id=f"ast-{sha256_bytes(raw_bytes)[:16]}",
            media_type="text",
            size_bytes=len(raw_bytes),
            sha256=sha256_bytes(raw_bytes),
        )
        job = MultimodalJob(
            id=f"job-{sha256_bytes(raw_bytes)[:16]}",
            asset_id=asset.id,
            media_type="text",
            status="RUNNING",
            progress=0.3,
        )

        article = article_from_dict({"title": text[:140], "content": text, "source_name": source_name})
        result, claims, evidence = self.analyzer.analyze(article)

        job.analysis = {
            "article": article.to_dict(),
            "result": result.to_dict(),
            "claims": [c.to_dict() for c in claims],
            "evidence": [e.to_dict() for e in evidence],
        }
        job.extracted_text = text
        job.progress = 1.0
        job.status = "COMPLETED"
        return job

    def analyze_url(self, url: str) -> MultimodalJob:
        asset = MediaAsset(
            id=f"ast-{sha256_bytes(url.encode())[:16]}",
            media_type="url",
            source_url=url,
            sha256=sha256_bytes(url.encode()),
        )
        job = MultimodalJob(
            id=f"job-{sha256_bytes(url.encode())[:16]}",
            asset_id=asset.id,
            media_type="url",
            status="RUNNING",
            progress=0.2,
        )
        try:
            title, content, domain = fetch_url_article(url)
            job.extracted_text = content
            job.progress = 0.6

            article = article_from_dict({
                "title": title,
                "content": content,
                "url": url,
                "source_domain": domain,
                "source_name": domain,
            })
            result, claims, evidence = self.analyzer.analyze(article)
            job.analysis = {
                "article": article.to_dict(),
                "result": result.to_dict(),
                "claims": [c.to_dict() for c in claims],
                "evidence": [e.to_dict() for e in evidence],
            }
            job.status = "COMPLETED"
            job.progress = 1.0
            return job
        except Exception as exc:
            job.status = "FAILED"
            job.error = str(exc)
            job.progress = 1.0
            return job

    def analyze_file(self, path: Path, media_type: str | None = None) -> MultimodalJob:
        raw = path.read_bytes()
        guessed = media_type or (mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        kind = self._kind_from_mime(guessed, path.suffix.lower())
        asset = MediaAsset(
            id=f"ast-{sha256_bytes(raw)[:16]}",
            media_type=kind,
            filename=path.name,
            mime_type=guessed,
            size_bytes=len(raw),
            sha256=sha256_bytes(raw),
        )
        job = MultimodalJob(
            id=f"job-{sha256_bytes(raw)[:16]}",
            asset_id=asset.id,
            media_type=kind,
            status="RUNNING",
            progress=0.15,
        )

        try:
            if kind == "image":
                text = self._ocr_image(path, job)
            elif kind == "audio":
                text = self._transcribe_audio(path, job)
            elif kind == "video":
                text = self._transcribe_video(path, job)
            else:
                text = raw.decode("utf-8", errors="ignore")

            job.extracted_text = text
            job.progress = 0.65

            if not text.strip():
                job.status = "COMPLETED"
                job.warnings.append("No textual content extracted from media; external provider may be required.")
                job.progress = 1.0
                return job

            article = article_from_dict({"title": path.stem, "content": text, "source_name": path.name})
            result, claims, evidence = self.analyzer.analyze(article)
            job.analysis = {
                "article": article.to_dict(),
                "result": result.to_dict(),
                "claims": [c.to_dict() for c in claims],
                "evidence": [e.to_dict() for e in evidence],
            }
            job.progress = 1.0
            job.status = "COMPLETED"
            return job
        except Exception as exc:
            job.status = "FAILED"
            job.error = str(exc)
            job.progress = 1.0
            return job

    def _ocr_image(self, path: Path, job: MultimodalJob) -> str:
        try:
            import pytesseract
            from PIL import Image
            job.warnings.append("OCR text extraction performed using Tesseract engine.")
            return pytesseract.image_to_string(Image.open(path))
        except Exception:
            job.warnings.append("Local Tesseract binary not detected. Configure an external vision provider for OCR.")
            return ""

    def _transcribe_audio(self, path: Path, job: MultimodalJob) -> str:
        job.warnings.append("Speech-to-text provider interface ready; configure Whisper or Cloud Speech provider for production.")
        return ""

    def _transcribe_video(self, path: Path, job: MultimodalJob) -> str:
        job.warnings.append("Video frame & audio extraction interface ready; configure multimodal vision model for production.")
        return ""

    @staticmethod
    def _kind_from_mime(mime: str, suffix: str) -> str:
        if mime.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            return "image"
        if mime.startswith("audio/") or suffix in {".mp3", ".wav", ".m4a", ".ogg"}:
            return "audio"
        if mime.startswith("video/") or suffix in {".mp4", ".mov", ".mkv", ".webm"}:
            return "video"
        return "text"
