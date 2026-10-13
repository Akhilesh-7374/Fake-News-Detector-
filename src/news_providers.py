#!/usr/bin/env python3
"""Free, zero-key public News and Evidence Providers for real-time intelligence."""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
import urllib.parse

import requests

from realtime_models import Article, Claim, Evidence, content_hash, utc_now_iso


class NewsProvider(Protocol):
    def fetch_latest(self) -> list[Article]:
        ...


class EvidenceProvider(Protocol):
    def search(self, claim: Claim) -> list[Evidence]:
        ...


class FactCheckProvider(Protocol):
    def search(self, claim: Claim) -> dict:
        ...


def clean_html(raw_html: str) -> str:
    """Strip HTML tags and unescape entities."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class GoogleNewsRSSProvider:
    """Real-time news provider using official Google News RSS feeds.
    
    100% Free, zero API key required, updates every few minutes.
    Feeds available: Top Stories, Business, Technology, World, Politics.
    """
    
    TOPICS = {
        "TOP": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        "BUSINESS": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en",
        "TECHNOLOGY": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en",
        "WORLD": "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en",
        "POLITICS": "https://news.google.com/rss/headlines/section/topic/POLITICS?hl=en-US&gl=US&ceid=US:en",
    }

    def __init__(self, topic: str = "TOP", limit: int = 25) -> None:
        self.url = self.TOPICS.get(topic.upper(), self.TOPICS["TOP"])
        self.limit = limit

    def fetch_latest(self) -> list[Article]:
        articles: list[Article] = []
        try:
            resp = requests.get(
                self.url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TrustSignal/2.0"},
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            for item in items[: self.limit]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pub_elem = item.find("pubDate")
                desc_elem = item.find("description")
                source_elem = item.find("source")

                raw_title = title_elem.text if title_elem is not None and title_elem.text else "Untitled"
                source_name = source_elem.text if source_elem is not None and source_elem.text else ""
                
                # Google News titles usually have "Headline - Source Name"
                if " - " in raw_title and not source_name:
                    parts = raw_title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source_name = parts[1].strip()
                else:
                    title = raw_title.strip()

                url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                content = clean_html(desc_elem.text) if desc_elem is not None and desc_elem.text else title
                published_at = pub_elem.text if pub_elem is not None and pub_elem.text else utc_now_iso()

                articles.append(
                    Article(
                        id=f"gn-{content_hash(url or title)[:16]}",
                        title=title,
                        content=content,
                        url=url,
                        source_name=source_name or "Google News",
                        source_domain="news.google.com",
                        published_at=published_at,
                        ingested_at=utc_now_iso(),
                        language="en",
                        category="General",
                        content_hash=content_hash(f"{title} {content}"),
                    )
                )
        except Exception:
            pass
        return articles


class BBCNewsRSSProvider:
    """Real-time news provider using BBC News World RSS feeds.
    
    100% Free, zero API key required, highly respected global wire feed.
    """
    
    URL = "https://feeds.bbci.co.uk/news/world/rss.xml"

    def __init__(self, limit: int = 20) -> None:
        self.limit = limit

    def fetch_latest(self) -> list[Article]:
        articles: list[Article] = []
        try:
            resp = requests.get(
                self.URL,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TrustSignal/2.0"},
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            for item in items[: self.limit]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pub_elem = item.find("pubDate")
                desc_elem = item.find("description")

                title = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled"
                url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                content = clean_html(desc_elem.text) if desc_elem is not None and desc_elem.text else title
                published_at = pub_elem.text if pub_elem is not None and pub_elem.text else utc_now_iso()

                articles.append(
                    Article(
                        id=f"bbc-{content_hash(url or title)[:16]}",
                        title=title,
                        content=content,
                        url=url,
                        source_name="BBC News",
                        source_domain="bbc.com",
                        published_at=published_at,
                        ingested_at=utc_now_iso(),
                        language="en",
                        category="World",
                        content_hash=content_hash(f"{title} {content}"),
                    )
                )
        except Exception:
            pass
        return articles


class WikipediaEvidenceProvider:
    """Real-time factual evidence verification via Wikipedia Search API.
    
    100% Free, zero API key required. Queries Wikipedia to verify entities,
    historical claims, and background context in real time.
    """

    SEARCH_API = "https://en.wikipedia.org/w/api.php"
    _CACHE: dict[str, list[Evidence]] = {}

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
                timeout=3,
            )
            if resp.status_code == 200:
                data = resp.json()
                search_results = data.get("query", {}).get("search", [])
                for item in search_results:
                    snippet = clean_html(item.get("snippet", ""))
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
    """Instant answers & disambiguation context from DuckDuckGo API.
    
    100% Free, zero API key required.
    """

    API_URL = "https://api.duckduckgo.com/"

    def search(self, claim: Claim) -> list[Evidence]:
        evidence_list: list[Evidence] = []
        query = " ".join(claim.entities[:3]) if claim.entities else claim.claim_text[:60]
        if not query.strip():
            return []

        try:
            params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
            resp = requests.get(
                self.API_URL,
                params=params,
                headers={"User-Agent": "TrustSignal/2.0"},
                timeout=5,
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
                            title=data.get("Heading", "Instant Answer"),
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


class CompositeNewsProvider:
    """Aggregates multiple real-time news feeds with automatic fallback."""

    def __init__(self, providers: list[NewsProvider] | None = None) -> None:
        self.providers = providers or [
            GoogleNewsRSSProvider(topic="TOP", limit=20),
            BBCNewsRSSProvider(limit=15),
        ]

    def fetch_latest(self) -> list[Article]:
        all_articles: list[Article] = []
        seen_titles = set()
        for provider in self.providers:
            try:
                articles = provider.fetch_latest()
                for art in articles:
                    normalized = re.sub(r"[^a-zA-Z0-9]", "", art.title.lower())
                    if normalized and normalized not in seen_titles:
                        seen_titles.add(normalized)
                        all_articles.append(art)
            except Exception:
                continue
        return all_articles
