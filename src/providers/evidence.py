"""Evidence and Fact-Check Provider implementations."""
from __future__ import annotations

import html
import os
import re
import urllib.parse
from typing import Any

import requests

from realtime_models import Claim, Evidence, content_hash, utc_now_iso


def strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


class WikipediaEvidenceProvider:
    """Real-time entity and claim retrieval via Wikimedia Search API.
    
    100% Free, zero API key required, with thread-safe query caching.
    """

    SEARCH_API = "https://en.wikipedia.org/w/api.php"
    _CACHE: dict[str, list[Evidence]] = {}

    def __init__(self, timeout: float = 4.0) -> None:
        self.timeout = timeout

    def search(self, claim: Claim) -> list[Evidence]:
        query_terms = claim.entities[:3] if claim.entities else [claim.claim_text[:60]]
        query = " ".join(query_terms).strip()
        if not query:
            return []

        if query in self._CACHE:
            return self._CACHE[query]

        evidence_list: list[Evidence] = []
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "utf8": 1,
                "format": "json",
                "srlimit": 2,
            }
            resp = requests.get(
                self.SEARCH_API,
                params=params,
                headers={"User-Agent": "TrustSignal-Misinformation-Defense/2.0"},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("query", {}).get("search", []):
                    snippet = strip_html(item.get("snippet", ""))
                    page_title = item.get("title", "")
                    page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(page_title.replace(' ', '_'))}"

                    snippet_lower = snippet.lower()
                    overlap = sum(1 for e in claim.entities if e.lower() in snippet_lower)
                    stance = "SUPPORTS" if overlap >= 1 else "NEUTRAL"

                    evidence_list.append(
                        Evidence(
                            id=f"wiki-{content_hash(f'{claim.id}-{page_title}')[:14]}",
                            claim_id=claim.id,
                            title=f"Wikipedia: {page_title}",
                            url=page_url,
                            source="Wikipedia",
                            snippet=snippet,
                            stance=stance,
                            relevance_score=0.75 if stance == "SUPPORTS" else 0.50,
                            retrieved_at=utc_now_iso(),
                        )
                    )
        except Exception:
            pass

        self._CACHE[query] = evidence_list
        return evidence_list


class DuckDuckGoEvidenceProvider:
    """Instant Answer API for fast contextual definitions."""

    API_URL = "https://api.duckduckgo.com/"

    def __init__(self, timeout: float = 3.5) -> None:
        self.timeout = timeout

    def search(self, claim: Claim) -> list[Evidence]:
        query = " ".join(claim.entities[:3]) if claim.entities else claim.claim_text[:60]
        if not query.strip():
            return []

        evidence_list: list[Evidence] = []
        try:
            params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
            resp = requests.get(
                self.API_URL,
                params=params,
                headers={"User-Agent": "TrustSignal/2.0"},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText", "")
                url = data.get("AbstractURL", "")
                source = data.get("AbstractSource", "DuckDuckGo Instant Answer")
                if abstract and url:
                    evidence_list.append(
                        Evidence(
                            id=f"ddg-{content_hash(f'{claim.id}-{url}')[:14]}",
                            claim_id=claim.id,
                            title=data.get("Heading", "Instant Context"),
                            url=url,
                            source=source,
                            snippet=abstract,
                            stance="NEUTRAL",
                            relevance_score=0.60,
                            retrieved_at=utc_now_iso(),
                        )
                    )
        except Exception:
            pass
        return evidence_list


class GoogleFactCheckProvider:
    """FactCheck Tools ClaimReview API provider for teams with Google API credentials."""

    API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    def __init__(self, api_key: str | None = None, timeout: float = 4.0) -> None:
        self.api_key = api_key or os.getenv("FACT_CHECK_API_KEY", "")
        self.timeout = timeout

    def search(self, claim: Claim) -> dict[str, Any]:
        if not self.api_key:
            return {"status": "UNAVAILABLE", "matches": []}

        query = claim.claim_text[:100]
        try:
            params = {"key": self.api_key, "query": query, "languageCode": "en"}
            resp = requests.get(self.API_URL, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                claims_found = data.get("claims", [])
                if not claims_found:
                    return {"status": "NO_MATCH", "matches": []}

                matches = []
                for item in claims_found[:3]:
                    reviews = item.get("claimReview", [])
                    rating = reviews[0].get("textualRating", "") if reviews else "Unknown"
                    matches.append({
                        "text": item.get("text", ""),
                        "claimant": item.get("claimant", ""),
                        "rating": rating,
                        "url": reviews[0].get("url", "") if reviews else "",
                        "publisher": reviews[0].get("publisher", {}).get("name", "") if reviews else "",
                    })
                
                # Determine overall status
                rating_str = " ".join([m["rating"].lower() for m in matches])
                if any(w in rating_str for w in ["false", "pants on fire", "fake", "incorrect"]):
                    status = "CONTRADICTED"
                elif any(w in rating_str for w in ["true", "correct", "accurate"]):
                    status = "SUPPORTED"
                else:
                    status = "MATCHED"

                return {"status": status, "matches": matches}
        except Exception:
            pass
        return {"status": "UNAVAILABLE", "matches": []}
