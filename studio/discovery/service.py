import hashlib
import json
import threading
import time
from datetime import datetime, timezone

from .errors import DiscoveryError
from .ranking import RIGHTS_NOTICE, SCORE_NOTICE, SCORE_VERSION, score_video
from .repository import Repository
from .schemas import SearchResponse
from .youtube import VIDEO_ID, YouTube, parse_video


class DiscoveryService:
    def __init__(self, settings, clock=time.time, transport=None):
        self.settings, self.clock = settings, clock
        self.repository = Repository(settings)
        self.youtube = YouTube(settings, self.repository, clock, transport)
        # One metadata search at a time per process; SQLite budgets also cover other processes.
        self._search_lock = threading.Lock()

    def search(self, request):
        if not self.settings.api_key:
            raise DiscoveryError("provider_not_configured", "Set YOUTUBE_API_KEY on the server to enable YouTube discovery.", 503)
        now = self.clock()
        search_id = self.repository.begin_search(request, now)
        if not self._search_lock.acquire(timeout=1):
            self.repository.finish_search(search_id, error_code="discovery_busy")
            raise DiscoveryError("discovery_busy", "A discovery search is in progress; retry shortly.", 429, True)
        try:
            key_material = {"request": request.model_dump(mode="json"), "score_version": SCORE_VERSION,
                            "max_pages": self.settings.max_pages}
            key = hashlib.sha256(json.dumps(key_material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            cached = self.repository.cached_search(key, self.clock())
            if cached:
                cached.update(search_id=search_id, cache_hit=True)
                response = SearchResponse.model_validate(cached)
            else:
                response = self._fetch(request, search_id)
                self.repository.cache_search(key, response.model_dump(mode="json"), response.expires_at.timestamp())
            self.repository.finish_search(search_id, len(response.items), response.cache_hit)
            return response
        except DiscoveryError as error:
            self.repository.finish_search(search_id, error_code=error.code)
            raise
        finally:
            self._search_lock.release()

    def _fetch(self, request, search_id):
        now = datetime.fromtimestamp(self.clock(), timezone.utc)
        seen, tokens, candidates = set(), set(), []
        token, pages, limited = None, 0, False
        expires = now.timestamp() + self.settings.cache_ttl_seconds
        for _ in range(self.settings.max_pages):
            page = self.youtube.search(request, token)
            pages += 1
            ids = []
            for item in page["items"]:
                identity = item.get("id", {})
                video_id = identity.get("videoId") if isinstance(identity, dict) else None
                if isinstance(video_id, str) and VIDEO_ID.fullmatch(video_id) and video_id not in seen:
                    ids.append(video_id)
                    seen.add(video_id)
            metadata = self.repository.cached_videos(ids, self.clock())
            missing = [video_id for video_id in ids if video_id not in metadata]
            if missing:
                fetched = []
                for item in self.youtube.details(missing)["items"]:
                    video = parse_video(item, now)
                    if video and video["video_id"] in missing:
                        metadata[video["video_id"]] = video
                        fetched.append(video)
                self.repository.cache_videos(fetched, now.timestamp() + self.settings.cache_ttl_seconds)
            for video_id in ids:
                video = metadata.get(video_id)
                if not video:
                    continue
                published = datetime.fromisoformat(video["published_at"])
                if video["view_count"] < request.min_views or not request.min_duration_seconds <= video["duration_seconds"] <= request.max_duration_seconds:
                    continue
                if request.published_after and published < request.published_after:
                    continue
                if request.published_before and published >= request.published_before:
                    continue
                score, components = score_video(request.keyword, video["title"], video["description"], video["view_count"], published, now)
                candidates.append({**video, "recommendation_score": score, "score_components": components})
                # Query caching must never extend the lifetime of reused metadata.
                expires = min(expires, datetime.fromisoformat(video["metadata_fetched_at"]).timestamp() + self.settings.cache_ttl_seconds)
            next_token = page.get("nextPageToken")
            if not next_token:
                break
            if not isinstance(next_token, str) or len(next_token) > 1024:
                raise DiscoveryError("invalid_provider_response", "YouTube returned an invalid page token.")
            limited = True
            if len(candidates) >= request.max_results or next_token in tokens:
                break
            tokens.add(next_token)
            token = next_token
            limited = False
        else:
            limited = bool(page.get("nextPageToken"))
        candidates.sort(key=lambda v: (-v["recommendation_score"], v["video_id"]))
        limited = limited or len(candidates) > request.max_results
        return SearchResponse(
            search_id=search_id, items=candidates[:request.max_results], total=min(len(candidates), request.max_results),
            cache_hit=False, fetched_at=now, expires_at=datetime.fromtimestamp(expires, timezone.utc),
            scanned_count=len(seen), pages_fetched=pages, limited=limited,
            score_version=SCORE_VERSION, score_notice=SCORE_NOTICE, rights_notice=RIGHTS_NOTICE,
        )

    def history(self, limit=20, before_id=None):
        return self.repository.history(limit, before_id, self.clock())
