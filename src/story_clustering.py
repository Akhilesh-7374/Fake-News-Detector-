"""Story clustering and trend anomaly detection for real-time news intelligence."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from deduplication import jaccard_similarity, title_fingerprint, word_jaccard_similarity


@dataclass
class StoryCluster:
    id: str
    topic: str
    representative_title: str
    dominant_claims: list[str] = field(default_factory=list)
    article_ids: list[str] = field(default_factory=list)
    sources: set[str] = field(default_factory=set)
    risk_scores: list[float] = field(default_factory=list)
    first_seen_at: str = ""
    last_updated_at: str = ""

    @property
    def article_count(self) -> int:
        return len(self.article_ids)

    @property
    def average_risk(self) -> float:
        return sum(self.risk_scores) / len(self.risk_scores) if self.risk_scores else 50.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "representative_title": self.representative_title,
            "dominant_claims": self.dominant_claims,
            "article_count": self.article_count,
            "source_count": len(self.sources),
            "average_risk": round(self.average_risk, 2),
            "first_seen_at": self.first_seen_at,
            "last_updated_at": self.last_updated_at,
        }


class StoryClusterEngine:
    """Clusters incoming news items into topical story events using lexical similarity."""

    def __init__(self, similarity_threshold: float = 0.30) -> None:
        self.threshold = similarity_threshold
        self.stories: dict[str, StoryCluster] = {}

    def cluster_article(self, article_id: str, title: str, claims: list[str], risk_score: float, source_name: str) -> StoryCluster:
        clean_title = title_fingerprint(title)
        now = datetime.now(timezone.utc).isoformat()

        best_story: StoryCluster | None = None
        best_sim = 0.0

        for story in self.stories.values():
            story_title_fp = title_fingerprint(story.representative_title)
            sim = max(
                word_jaccard_similarity(title, story.representative_title),
                jaccard_similarity(clean_title, story_title_fp, n=3),
            )
            if sim > best_sim and sim >= self.threshold:
                best_sim = sim
                best_story = story

        if best_story is not None:
            best_story.article_ids.append(article_id)
            if source_name:
                best_story.sources.add(source_name)
            best_story.risk_scores.append(risk_score)
            for c in claims[:2]:
                if c not in best_story.dominant_claims:
                    best_story.dominant_claims.append(c)
            best_story.last_updated_at = now
            return best_story

        # Create new story cluster
        story_id = f"story-{clean_title[:18].replace(' ', '-')}-{int(datetime.now().timestamp())}"
        topic = self._extract_topic(title)
        new_story = StoryCluster(
            id=story_id,
            topic=topic,
            representative_title=title,
            dominant_claims=claims[:3],
            article_ids=[article_id],
            sources={source_name} if source_name else set(),
            risk_scores=[risk_score],
            first_seen_at=now,
            last_updated_at=now,
        )
        self.stories[story_id] = new_story
        return new_story

    def get_active_stories(self) -> list[StoryCluster]:
        return sorted(self.stories.values(), key=lambda s: s.article_count, reverse=True)

    @staticmethod
    def _extract_topic(text: str) -> str:
        words = re.findall(r"\b[A-Za-z]{4,}\b", text.lower())
        stop_words = {"this", "that", "with", "from", "have", "were", "what", "when", "after", "about", "shows", "says", "more"}
        filtered = [w.capitalize() for w in words if w not in stop_words]
        if not filtered:
            return "General News"
        top = Counter(filtered).most_common(2)
        return " & ".join([t[0] for t in top])
