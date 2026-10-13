#!/usr/bin/env python3
"""Multimodal ingestion/job models for the real-time platform."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any
from datetime import datetime, timezone
import hashlib


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(slots=True)
class MediaAsset:
    id: str
    media_type: str  # text|image|audio|video|url
    filename: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    sha256: str = ""
    source_url: str = ""
    created_at: str = field(default_factory=now_iso)
    status: str = "READY"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MultimodalJob:
    id: str
    asset_id: str
    media_type: str
    status: str = "QUEUED"
    progress: float = 0.0
    transcript: str = ""
    extracted_text: str = ""
    frame_count: int = 0
    duration_seconds: float = 0.0
    analysis: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
