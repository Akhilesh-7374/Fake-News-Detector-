#!/usr/bin/env python3
"""Multimodal API endpoints layered onto the existing real-time API."""
from __future__ import annotations
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

try:
    from fastapi import APIRouter, File, Form, HTTPException, UploadFile
except ImportError:
    APIRouter = None

from media_analyzer import MediaAnalyzer
from realtime_engine import RealTimeAnalyzer

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = Path(os.getenv("PIPELINE_PATH", ROOT / "outputs" / "pipeline.joblib"))

router = APIRouter(prefix="/api/v1/multimodal", tags=["multimodal"]) if APIRouter else None

if router:
    @router.post("/analyze-file")
    async def analyze_file(file: UploadFile = File(...), media_type: str | None = Form(default=None)) -> dict[str, Any]:
        if not file.filename:
            raise HTTPException(status_code=400, detail="filename is required")
        suffix = Path(file.filename).suffix or ".bin"
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            data = await file.read()
            if len(data) > 50 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="file exceeds 50MB safety limit")
            tmp.write(data)
            temp_path = Path(tmp.name)
        try:
            job = MediaAnalyzer(RealTimeAnalyzer(PIPELINE)).analyze_file(temp_path, media_type)
            job.analysis.setdefault("upload", {})["filename"] = file.filename
            return job.to_dict()
        finally:
            temp_path.unlink(missing_ok=True)
