"""Small discovery-to-existing-engine boundary; no rendering or cloud dependencies."""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, field_validator

from .errors import DiscoveryError
from .youtube import parse_video

SOURCE_FILE = ".discovery-source.json"


class DiscoverySource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    url: str = Field(max_length=200)
    title: str = Field(max_length=200)
    channel_title: str = Field(max_length=200)
    license: str = Field(pattern=r"^creativeCommon$")
    metadata_fetched_at: datetime
    download_authorized: StrictBool

    @field_validator("metadata_fetched_at")
    @classmethod
    def timestamp_with_zone(cls, value):
        if value.tzinfo is None:
            raise ValueError("metadata timestamp must include timezone")
        return value


def verify_source(payload, url, service):
    """One fresh videos.list call, using P1's atomic daily budget; fail closed."""
    try:
        source = DiscoverySource.model_validate(payload)
    except ValidationError:
        raise DiscoveryError("invalid_discovery_source", "Invalid discovery source metadata.", 422) from None
    canonical = f"https://www.youtube.com/watch?v={source.video_id}"
    if source.url != canonical or url != canonical:
        raise DiscoveryError("invalid_discovery_source", "Discovery source URL does not match its video ID.", 422)
    if not source.download_authorized:
        raise DiscoveryError("download_not_confirmed", "Separately confirm downloading is permitted, or upload a lawful original file.", 400)
    if not service.settings.api_key:
        raise DiscoveryError("provider_not_configured", "Set YOUTUBE_API_KEY on the processing server for a fresh source check.", 503)
    now = datetime.fromtimestamp(service.clock(), timezone.utc)
    items = service.youtube.details([source.video_id])["items"]
    item = next((item for item in items if item.get("id") == source.video_id), None)
    if item is None:
        raise DiscoveryError("source_unavailable", "The original video is unavailable; search again or upload a lawful original.", 409)
    status = item.get("status")
    if not isinstance(status, dict) or status.get("license") != "creativeCommon":
        raise DiscoveryError("source_license_changed", "The source license changed or cannot be verified; confirm rights again.", 409)
    video = parse_video(item, now)
    if video is None:
        raise DiscoveryError("source_unavailable", "The original is no longer a public, processed video with verifiable metadata.", 409)
    # Retain what the person saw as well as authoritative fresh metadata. No keys or cookies.
    return {**source.model_dump(mode="json"), "selected_metadata": source.model_dump(mode="json"),
            **video, "rights_confirmed_at": now.isoformat()}


def save_source(output_dir, source):
    path = Path(output_dir) / SOURCE_FILE
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def read_source(job):
    if "discovery_source" in job:
        return job["discovery_source"]
    if not job.get("output_dir"):
        return None
    try:
        return json.loads((Path(job["output_dir"]) / SOURCE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def available_result(job_id, job):
    """Annotate missing local results without shifting existing engine clip indices."""
    result = job.get("result")
    if not result or not isinstance(result.get("clips"), list):
        return result, 0
    root = Path(job["output_dir"]).resolve()
    prefix = f"/videos/{job_id}/"
    clips = []
    for clip in result["clips"]:
        available = False
        try:
            path = unquote(urlsplit(clip.get("video_url") or "").path)
            if path.startswith(prefix):
                file = (root / path[len(prefix):]).resolve()
                available = file.is_relative_to(root) and file.is_file() and file.stat().st_size > 0
        except (OSError, ValueError):
            pass
        clips.append({**clip, "unavailable": not available})
    return {**result, "clips": clips}, sum(clip["unavailable"] for clip in clips)
