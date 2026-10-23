import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    enabled: bool = False
    api_key: str = field(default="", repr=False)
    db_path: Path = Path(".studio-data/discovery.sqlite3")
    cache_ttl_seconds: int = 3600
    requests_per_minute: int = 30
    api_calls_per_day: int = 100
    quota_units_per_day: int = 9000
    max_pages: int = 3
    timeout_seconds: float = 10

    @classmethod
    def from_env(cls):
        def integer(name, default, low, high):
            value = int(os.environ.get(name, str(default)))
            if not low <= value <= high:
                raise ValueError(f"{name} must be between {low} and {high}")
            return value

        return cls(
            enabled=os.environ.get("DISCOVERY_ENABLED", "0").lower() in {"1", "true", "yes"},
            api_key=os.environ.get("YOUTUBE_API_KEY", "").strip(),
            db_path=Path(os.environ.get("DISCOVERY_DB_PATH", ".studio-data/discovery.sqlite3")),
            cache_ttl_seconds=integer("DISCOVERY_CACHE_TTL_SECONDS", 3600, 1, 86400),
            requests_per_minute=integer("DISCOVERY_REQUESTS_PER_MINUTE", 30, 1, 10000),
            api_calls_per_day=integer("DISCOVERY_API_CALLS_PER_DAY", 100, 1, 100000),
            quota_units_per_day=integer("DISCOVERY_QUOTA_UNITS_PER_DAY", 9000, 1, 1000000),
            max_pages=integer("DISCOVERY_MAX_PAGES", 3, 1, 3),
        )
