"""Enterprise deduplication engine supporting exact hash, URL canonicalization, and near-duplicate similarity."""
from __future__ import annotations

import hashlib
import re
import urllib.parse
from typing import Iterable

from realtime_models import Article


def canonicalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters, anchors, www prefix, and trailing slashes."""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url.strip())
        # Filter out common tracking query params
        query_pairs = urllib.parse.parse_qsl(parsed.query)
        clean_pairs = [
            (k, v) for k, v in query_pairs
            if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref", "source"))
        ]
        new_query = urllib.parse.urlencode(clean_pairs)
        clean_path = parsed.path.rstrip("/")
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return urllib.parse.urlunparse((
            parsed.scheme.lower(),
            netloc,
            clean_path,
            "",
            new_query,
            "",
        ))
    except Exception:
        return url.strip().lower()


def word_jaccard_similarity(text_a: str, text_b: str) -> float:
    """Calculate word token set Jaccard similarity."""
    words_a = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", text_a.lower()))
    words_b = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    return len(words_a.intersection(words_b)) / len(words_a.union(words_b))


def compute_content_hash(text: str) -> str:
    """Compute normalized SHA-256 fingerprint."""
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def title_fingerprint(title: str) -> str:
    """Strip punctuation and whitespace for resilient title matching."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", (title or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def jaccard_similarity(text_a: str, text_b: str, n: int = 3) -> float:
    """Calculate character n-gram Jaccard similarity for near-duplicate detection."""
    def get_ngrams(s: str) -> set[str]:
        s = re.sub(r"\s+", " ", s.strip().lower())
        if len(s) < n:
            return {s}
        return {s[i:i + n] for i in range(len(s) - n + 1)}

    set_a = get_ngrams(text_a)
    set_b = get_ngrams(text_b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return intersection / union if union > 0 else 0.0


class DeduplicationEngine:
    def __init__(self, near_duplicate_threshold: float = 0.82) -> None:
        self.threshold = near_duplicate_threshold
        self.seen_urls: set[str] = set()
        self.seen_content_hashes: set[str] = set()
        self.seen_titles: set[str] = set()
        self.existing_corpus: list[tuple[str, str]] = []  # (article_id, title)

    def is_duplicate(self, article: Article) -> tuple[bool, str]:
        """Check if an article is an exact or near duplicate.
        
        Returns (is_dupe, duplicate_reason).
        """
        # 1. Canonical URL match
        if article.url:
            canon = canonicalize_url(article.url)
            if canon in self.seen_urls:
                return True, "EXACT_URL"

        # 2. Exact content hash match
        c_hash = article.content_hash or compute_content_hash(article.content)
        if c_hash in self.seen_content_hashes:
            return True, "EXACT_CONTENT_HASH"

        # 3. Normalized title match
        tfp = title_fingerprint(article.title)
        if tfp in self.seen_titles:
            return True, "EXACT_NORMALIZED_TITLE"

        # 4. Near-duplicate title similarity
        if tfp:
            for prev_id, prev_tfp in self.existing_corpus:
                if jaccard_similarity(tfp, prev_tfp) >= self.threshold:
                    return True, f"NEAR_DUPLICATE_OF_{prev_id}"

        return False, "UNIQUE"

    def register(self, article: Article) -> None:
        """Register a unique article into the deduplication index."""
        if article.url:
            self.seen_urls.add(canonicalize_url(article.url))
        c_hash = article.content_hash or compute_content_hash(article.content)
        self.seen_content_hashes.add(c_hash)
        tfp = title_fingerprint(article.title)
        if tfp:
            self.seen_titles.add(tfp)
            self.existing_corpus.append((article.id, tfp))


def deduplicate_stream(articles: Iterable[Article]) -> tuple[list[Article], int]:
    """Filter out duplicate articles from an incoming stream."""
    engine = DeduplicationEngine()
    unique: list[Article] = []
    dupes = 0
    for art in articles:
        is_dupe, _ = engine.is_duplicate(art)
        if is_dupe:
            dupes += 1
            continue
        engine.register(art)
        unique.append(art)
    return unique, dupes
