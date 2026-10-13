"""Test suite for FastAPI REST API endpoints."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient
from realtime_api import app

client = TestClient(app)


def test_api_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_api_metrics():
    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200
    assert "holdout_test" in resp.json()


def test_api_model_info():
    resp = client.get("/api/v1/model-info")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("ONLINE", "OFFLINE")


def test_api_analyze_text():
    resp = client.post(
        "/api/v1/analyze",
        json={
            "text": "WASHINGTON (Reuters) - The U.S. Federal Reserve announced updated fiscal reserve requirements on Tuesday.",
            "source_name": "Reuters",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert "verdict" in data
    assert "risk_score" in data
    assert "reasons" in data


def test_api_articles_list():
    resp = client.get("/api/v1/articles?limit=10")
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_api_sources():
    resp = client.get("/api/v1/sources")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_alerts():
    resp = client.get("/api/v1/alerts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
