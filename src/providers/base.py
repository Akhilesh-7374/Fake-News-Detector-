"""Provider abstractions and protocols for the Misinformation Intelligence Platform."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from realtime_models import Article, Claim, Evidence


@runtime_checkable
class NewsProvider(Protocol):
    def fetch_latest(self) -> list[Article]:
        """Fetch latest news articles from provider."""
        ...


@runtime_checkable
class EvidenceProvider(Protocol):
    def search(self, claim: Claim) -> list[Evidence]:
        """Retrieve external evidence items for a given claim."""
        ...


@runtime_checkable
class FactCheckProvider(Protocol):
    def search(self, claim: Claim) -> dict[str, Any]:
        """Search fact-check databases (e.g. ClaimReview) for claim matches."""
        ...


@runtime_checkable
class VisionProvider(Protocol):
    def extract_text(self, file_path: str) -> str:
        """Extract text from image/screenshot using OCR or vision model."""
        ...


@runtime_checkable
class TranscriptionProvider(Protocol):
    def transcribe(self, file_path: str) -> str:
        """Transcribe speech/audio file to text."""
        ...


@runtime_checkable
class NotificationProvider(Protocol):
    def send_alert(self, title: str, message: str, severity: str) -> bool:
        """Send urgent notification (Slack, Webhook, Email)."""
        ...
