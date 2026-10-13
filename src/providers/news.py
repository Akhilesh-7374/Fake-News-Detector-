"""Real-time News Provider implementations supporting free RSS and API feeds."""
from __future__ import annotations

import html
import logging
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import requests

from realtime_models import Article, content_hash, utc_now_iso

logger = logging.getLogger(__name__)


def clean_html_markup(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class GoogleNewsRSSProvider:
    """Official Google News RSS feed provider. Zero key, 100% free."""

    TOPICS = {
        "TOP": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        "BUSINESS": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en",
        "TECHNOLOGY": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en",
        "WORLD": "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en",
        "POLITICS": "https://news.google.com/rss/headlines/section/topic/POLITICS?hl=en-US&gl=US&ceid=US:en",
    }

    def __init__(self, topic: str = "TOP", limit: int = 25, timeout: float = 8.0) -> None:
        self.url = self.TOPICS.get(topic.upper(), self.TOPICS["TOP"])
        self.limit = limit
        self.timeout = timeout

    def fetch_latest(self) -> list[Article]:
        articles: list[Article] = []
        try:
            resp = requests.get(
                self.url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TrustSignal/2.0"},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[: self.limit]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pub_elem = item.find("pubDate")
                desc_elem = item.find("description")
                source_elem = item.find("source")

                raw_title = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled"
                source_name = source_elem.text.strip() if source_elem is not None and source_elem.text else ""

                if " - " in raw_title and not source_name:
                    parts = raw_title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source_name = parts[1].strip()
                else:
                    title = raw_title

                url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                content = clean_html_markup(desc_elem.text) if desc_elem is not None and desc_elem.text else title
                published_at = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else utc_now_iso()

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
        except Exception as exc:
            logger.warning("Google News fetch warning: %s", exc)
        return articles


class BBCNewsRSSProvider:
    """Official BBC World News RSS feed provider. Zero key, 100% free."""

    URL = "https://feeds.bbci.co.uk/news/world/rss.xml"

    def __init__(self, limit: int = 20, timeout: float = 8.0) -> None:
        self.limit = limit
        self.timeout = timeout

    def fetch_latest(self) -> list[Article]:
        articles: list[Article] = []
        try:
            resp = requests.get(
                self.URL,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TrustSignal/2.0"},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[: self.limit]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pub_elem = item.find("pubDate")
                desc_elem = item.find("description")

                title = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled"
                url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                content = clean_html_markup(desc_elem.text) if desc_elem is not None and desc_elem.text else title
                published_at = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else utc_now_iso()

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
        except Exception as exc:
            logger.warning("BBC News fetch warning: %s", exc)
        return articles


class NewsAPIProvider:
    """NewsAPI.org provider for users with optional NEWS_API_KEY credential."""

    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self, api_key: str | None = None, country: str = "us", limit: int = 20) -> None:
        self.api_key = api_key or os.getenv("NEWS_API_KEY", "")
        self.country = country
        self.limit = limit

    def fetch_latest(self) -> list[Article]:
        if not self.api_key:
            return []
        articles: list[Article] = []
        try:
            params = {"apiKey": self.api_key, "country": self.country, "pageSize": self.limit}
            resp = requests.get(self.BASE_URL, params=params, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("articles", []):
                    title = item.get("title") or "Untitled"
                    url = item.get("url") or ""
                    content = item.get("content") or item.get("description") or title
                    source_name = (item.get("source") or {}).get("name") or "NewsAPI"
                    published_at = item.get("publishedAt") or utc_now_iso()
                    articles.append(
                        Article(
                            id=f"napi-{content_hash(url or title)[:16]}",
                            title=title,
                            content=content,
                            url=url,
                            source_name=source_name,
                            source_domain=urllib.parse.urlparse(url).netloc,
                            published_at=published_at,
                            ingested_at=utc_now_iso(),
                            language="en",
                            category="General",
                            content_hash=content_hash(f"{title} {content}"),
                        )
                    )
        except Exception as exc:
            logger.warning("NewsAPI fetch warning: %s", exc)
        return articles


class CompositeNewsProvider:
    """Combines multiple news providers with graceful fallback and deduplication."""

    def __init__(self, providers: list[Any] | None = None) -> None:
        self.providers = providers or [
            GoogleNewsRSSProvider(topic="TOP", limit=20),
            BBCNewsRSSProvider(limit=15),
        ]

    def fetch_latest(self) -> list[Article]:
        aggregated: list[Article] = []
        seen_fingerprints: set[str] = set()

        for provider in self.providers:
            try:
                articles = provider.fetch_latest()
                for art in articles:
                    norm = re.sub(r"[^a-zA-Z0-9]", "", art.title.lower())
                    if norm and norm not in seen_fingerprints:
                        seen_fingerprints.add(norm)
                        aggregated.append(art)
            except Exception as exc:
                logger.warning("Composite provider error: %s", exc)
                continue
        return aggregated
