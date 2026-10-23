"""Versioned heuristic, not a prediction or a YouTube-provided metric."""
import math
import re
import unicodedata
from datetime import datetime

SCORE_VERSION = "heuristic-v1"
SCORE_NOTICE = (
    "Independent 0–100 heuristic within the fetched candidates; not a viral success "
    "probability or a YouTube metric. Daily views are lifetime views / age, not recent growth."
)
RIGHTS_NOTICE = (
    "Creative Commons metadata is not proof of all usage rights. Verify the original "
    "source, applicable license, attribution and third-party rights before reuse. "
    "Discovery does not authorize downloading."
)


def relevance(keyword: str, title: str, description: str) -> float:
    def normal(text):
        return unicodedata.normalize("NFKC", text).casefold()

    terms = set(re.findall(r"\w+", normal(keyword)))
    if not terms:
        return 0.0
    title, description = normal(title), normal(description)
    return sum(1.0 if term in title else 0.5 if term in description else 0 for term in terms) / len(terms)


def score_video(keyword, title, description, views, published_at: datetime, now: datetime):
    age = max((now - published_at).total_seconds() / 86400, 1.0)
    daily = max(views, 0) / age
    rel = relevance(keyword, title, description)
    volume = min(math.log1p(max(views, 0)) / math.log1p(10_000_000), 1)
    velocity = min(math.log1p(daily) / math.log1p(100_000), 1)
    recency = math.exp(-age / 90)
    score = 100 * (0.30 * volume + 0.30 * velocity + 0.15 * recency + 0.25 * rel)
    return round(min(max(score, 0), 100), 2), {
        "age_days": round(age, 4),
        "average_daily_views": round(daily, 2),
        "keyword_relevance": round(rel, 4),
    }
