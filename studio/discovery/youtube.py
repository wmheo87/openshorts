"""Fixed-origin metadata API client. Never fetches videos or user-supplied URLs."""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from .errors import DiscoveryError

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


def duration_seconds(value):
    match = DURATION.fullmatch(value)
    if not match or not any(match.groups()):
        raise ValueError("Invalid ISO 8601 video duration")
    days, hours, minutes, seconds = (float(v or 0) for v in match.groups())
    return int(days * 86400 + hours * 3600 + minutes * 60 + seconds)


def parse_video(item, now):
    """Fail closed on unavailable/non-public/live/unknown-license metadata."""
    try:
        video_id = item["id"]
        if not isinstance(video_id, str) or not VIDEO_ID.fullmatch(video_id):
            return None
        snippet, status = item["snippet"], item["status"]
        if status.get("license") != "creativeCommon" or status.get("privacyStatus") != "public" or status.get("uploadStatus") != "processed":
            return None
        if snippet.get("liveBroadcastContent") != "none":
            return None
        published = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
        if published.tzinfo is None or published > now:
            return None
        duration = duration_seconds(item["contentDetails"]["duration"])
        views = int(item["statistics"]["viewCount"])
        if duration < 1 or views < 0:
            return None
        thumbnail = None
        for size in ("high", "medium", "default"):
            candidate = snippet.get("thumbnails", {}).get(size, {}).get("url", "")
            parsed = urlparse(candidate)
            if parsed.scheme == "https" and parsed.hostname in {"i.ytimg.com", "i9.ytimg.com", "img.youtube.com"} and not parsed.username:
                thumbnail = candidate
                break
        return {
            "video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": str(snippet["title"])[:200], "description": str(snippet.get("description", ""))[:5000],
            "channel_id": str(snippet["channelId"])[:100], "channel_title": str(snippet["channelTitle"])[:200],
            "thumbnail_url": thumbnail, "published_at": published.astimezone(timezone.utc).isoformat(),
            "view_count": views, "duration_seconds": duration, "license": "creativeCommon",
            "metadata_fetched_at": now.isoformat(),
        }
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        return None


class YouTube:
    def __init__(self, settings, repository, clock, transport=None):
        self.settings, self.repository, self.clock, self.transport = settings, repository, clock, transport

    def get(self, resource, params):
        # Reserve BEFORE attempting the request: failures also consume the local budget.
        self.repository.reserve_api_call(100 if resource == "search" else 1, self.clock())
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds, transport=self.transport,
                              follow_redirects=False) as client:
                # Keep the credential out of URLs, access logs, cache keys and errors.
                response = client.get(f"https://www.googleapis.com/youtube/v3/{resource}", params=params,
                                      headers={"X-Goog-Api-Key": self.settings.api_key})
        except httpx.TimeoutException:
            raise DiscoveryError("provider_timeout", "YouTube API timed out.", 504, True) from None
        except httpx.HTTPError:
            raise DiscoveryError("provider_unavailable", "Could not reach YouTube API.", 502, True) from None
        try:
            body = response.json()
        except ValueError:
            if response.status_code == 200:
                raise DiscoveryError("invalid_provider_response", "YouTube returned an invalid response.") from None
            body = {}  # Classify HTTP errors even when an intermediary returns HTML.
        if response.status_code != 200:
            error = body.get("error", {}) if isinstance(body, dict) else {}
            errors = error.get("errors", []) if isinstance(error, dict) else []
            reasons = {e["reason"] for e in errors if isinstance(e, dict) and isinstance(e.get("reason"), str)} if isinstance(errors, list) else set()
            if reasons & {"quotaExceeded", "dailyLimitExceeded", "dailyLimitExceededUnreg"}:
                self.repository.block_day(self.clock())
                raise DiscoveryError("youtube_quota_exceeded", "YouTube API quota exhausted; check the provider quota console.", 429, True)
            if response.status_code == 429 or reasons & {"rateLimitExceeded", "userRateLimitExceeded"}:
                raise DiscoveryError("provider_rate_limited", "YouTube API rate limit reached.", 429, True)
            if response.status_code in {400, 401, 403}:
                raise DiscoveryError("provider_access_denied", "YouTube API rejected the request; verify the server API key, restrictions and API enablement.", 502)
            raise DiscoveryError("provider_unavailable", "YouTube API request failed.", 502, response.status_code >= 500)
        if not isinstance(body, dict) or not isinstance(body.get("items"), list):
            raise DiscoveryError("invalid_provider_response", "YouTube returned an invalid response.")
        if len(body["items"]) > 50 or any(not isinstance(item, dict) for item in body["items"]):
            raise DiscoveryError("invalid_provider_response", "YouTube returned invalid metadata.")
        return body

    def search(self, request, page_token=None):
        params = {"part": "snippet", "type": "video", "q": request.keyword,
                  "maxResults": 50, "videoLicense": "creativeCommon", "order": "relevance"}
        if request.relevance_language:
            params["relevanceLanguage"] = request.relevance_language
        for field, name in ((request.published_after, "publishedAfter"), (request.published_before, "publishedBefore")):
            if field:
                params[name] = field.isoformat().replace("+00:00", "Z")
        if page_token:
            params["pageToken"] = page_token
        return self.get("search", params)

    def details(self, ids):
        return self.get("videos", {"part": "snippet,contentDetails,statistics,status", "id": ",".join(ids), "maxResults": 50})
