import unicodedata
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    keyword: str = Field(min_length=1, max_length=200)
    published_after: datetime | None = None
    published_before: datetime | None = None
    min_duration_seconds: int = Field(default=1, ge=1, le=86400)
    max_duration_seconds: int = Field(default=86400, ge=1, le=86400)
    min_views: int = Field(default=0, ge=0, le=10**15)
    max_results: int = Field(default=50, ge=1, le=50)
    relevance_language: Literal["en", "ko", "ja"] | None = None

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value):
        value = " ".join(unicodedata.normalize("NFC", value).split())
        if not value or any(unicodedata.category(c) == "Cc" for c in value):
            raise ValueError("keyword must contain searchable text")
        return value

    @field_validator("published_after", "published_before")
    @classmethod
    def aware_utc(cls, value):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Use an ISO 8601 timestamp with a timezone")
            return value.astimezone(timezone.utc)
        return value

    @model_validator(mode="after")
    def ordered_ranges(self):
        if self.min_duration_seconds > self.max_duration_seconds:
            raise ValueError("min_duration_seconds must not exceed max_duration_seconds")
        if self.published_after and self.published_before and self.published_after >= self.published_before:
            raise ValueError("published_after must precede published_before")
        return self


class ScoreComponents(BaseModel):
    age_days: float
    average_daily_views: float
    keyword_relevance: float


class Video(BaseModel):
    video_id: str
    url: str
    title: str
    description: str
    channel_id: str
    channel_title: str
    thumbnail_url: str | None
    published_at: datetime
    view_count: int
    duration_seconds: int
    license: Literal["creativeCommon"]
    metadata_fetched_at: datetime
    recommendation_score: float = Field(ge=0, le=100)
    score_components: ScoreComponents


class SearchResponse(BaseModel):
    search_id: str
    items: list[Video]
    total: int
    cache_hit: bool
    fetched_at: datetime
    expires_at: datetime
    scanned_count: int
    pages_fetched: int
    limited: bool
    score_version: str
    score_notice: str
    rights_notice: str


class HistoryEntry(BaseModel):
    search_id: str
    requested_at: datetime
    request: SearchRequest
    result_count: int | None
    cache_hit: bool
    status: str
    error_code: str | None


class HistoryResponse(BaseModel):
    items: list[HistoryEntry]
    next_before_id: int | None
