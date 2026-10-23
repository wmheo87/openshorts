"""Offline API/SQLite/provider contract tests. No video or commercial modules imported."""
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from studio.discovery.app import app
from studio.discovery.config import Settings
from studio.discovery.errors import DiscoveryError
from studio.discovery.ranking import relevance, score_video
from studio.discovery.router import get_service
from studio.discovery.schemas import SearchRequest
from studio.discovery.service import DiscoveryService
from studio.discovery.youtube import duration_seconds

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)
VIDEO = "abcdefghijk"
OTHER = "lmnopqrstuv"


def video(identity=VIDEO, views=10000, duration="PT10M", license="creativeCommon", **overrides):
    result = {
        "id": identity,
        "snippet": {"title": "한국 요리 Japanese cooking", "description": "料理 tutorial",
                    "channelId": "channel123", "channelTitle": "Kitchen",
                    "publishedAt": "2026-10-20T00:00:00Z", "liveBroadcastContent": "none",
                    "thumbnails": {"high": {"url": f"https://i.ytimg.com/vi/{identity}/hqdefault.jpg"}}},
        "status": {"license": license, "privacyStatus": "public", "uploadStatus": "processed"},
        "contentDetails": {"duration": duration}, "statistics": {"viewCount": str(views)},
    }
    result.update(overrides)
    return result


class Provider:
    def __init__(self, videos=None, search_pages=None):
        self.videos = videos if videos is not None else [video()]
        self.search_pages = search_pages
        self.calls = []
        self.error = None

    def __call__(self, request):
        self.calls.append(request)
        assert request.url.host == "www.googleapis.com"
        assert request.headers["x-goog-api-key"] == "fixture-key"
        assert "key" not in request.url.params
        if self.error:
            return self.error(request)
        if request.url.path.endswith("/search"):
            assert request.url.params["type"] == "video"
            assert request.url.params["videoLicense"] == "creativeCommon"
            assert request.url.params["maxResults"] == "50"
            page = self.search_pages[request.url.params.get("pageToken", "first")] if self.search_pages else {
                "items": [{"id": {"videoId": v["id"]}} for v in self.videos]
            }
            return httpx.Response(200, json=page)
        assert request.url.params["part"] == "snippet,contentDetails,statistics,status"
        ids = request.url.params["id"].split(",")
        return httpx.Response(200, json={"items": [v for v in self.videos if v["id"] in ids]})


@pytest.fixture
def setup(tmp_path):
    provider = Provider()
    clock = [NOW.timestamp()]
    settings = Settings(enabled=True, api_key="fixture-key", db_path=tmp_path / "data" / "discovery.db")
    service = DiscoveryService(settings, clock=lambda: clock[0], transport=httpx.MockTransport(provider))
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as client:
        yield client, service, provider, clock
    app.dependency_overrides.clear()
    get_service.cache_clear()


@pytest.mark.parametrize("keyword,language", [("cooking", "en"), ("한국 요리", "ko"), ("日本 料理", "ja")])
def test_search_contract_and_languages(setup, keyword, language):
    client, service, provider, _ = setup
    res = client.post("/api/discovery/search", json={"keyword": keyword, "relevance_language": language})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1 and not data["cache_hit"]
    found = data["items"][0]
    assert found["video_id"] == VIDEO
    assert found["url"] == f"https://www.youtube.com/watch?v={VIDEO}"
    assert found["description"] == "料理 tutorial"
    assert found["channel_title"] == "Kitchen" and found["license"] == "creativeCommon"
    assert found["view_count"] == 10000 and found["duration_seconds"] == 600
    assert found["thumbnail_url"].startswith("https://i.ytimg.com/")
    assert 0 <= found["recommendation_score"] <= 100
    assert "not a viral" in data["score_notice"] and "not proof" in data["rights_notice"]
    assert provider.calls[0].url.params["q"] == keyword
    assert provider.calls[0].url.params["relevanceLanguage"] == language
    assert client.get("/api/discovery/history").json()["items"][0]["search_id"] == data["search_id"]


def test_empty_results_cached_without_details_call(setup):
    client, _, provider, _ = setup
    provider.videos = []
    assert client.post("/api/discovery/search", json={"keyword": "absent"}).json()["items"] == []
    assert client.post("/api/discovery/search", json={"keyword": "absent"}).json()["cache_hit"]
    assert len(provider.calls) == 1


@pytest.mark.parametrize("field,value,count", [
    ("min_views", 10001, 0), ("min_views", 10000, 1),
    ("min_duration_seconds", 601, 0), ("min_duration_seconds", 600, 1),
    ("max_duration_seconds", 599, 0), ("max_duration_seconds", 600, 1),
    ("published_after", "2026-10-20T00:00:01Z", 0),
    ("published_after", "2026-10-20T00:00:00Z", 1),
    ("published_before", "2026-10-20T00:00:00Z", 0),
    ("published_before", "2026-10-20T09:00:01+09:00", 1),
])
def test_exact_filters(setup, field, value, count):
    client, _, provider, _ = setup
    res = client.post("/api/discovery/search", json={"keyword": "cooking", field: value})
    assert res.status_code == 200 and res.json()["total"] == count
    if field.startswith("published_"):
        assert ("publishedAfter" if field.endswith("after") else "publishedBefore") in provider.calls[0].url.params


@pytest.mark.parametrize("replacement", [
    {"status": {"license": "youtube", "privacyStatus": "public", "uploadStatus": "processed"}},
    {"status": {"privacyStatus": "public", "uploadStatus": "processed"}},
    {"status": {"license": "creativeCommon", "privacyStatus": "private", "uploadStatus": "processed"}},
    {"statistics": {}}, {"statistics": {"viewCount": "-1"}},
    {"contentDetails": {"duration": "invalid"}},
])
def test_unknown_or_non_cc_metadata_excluded(setup, replacement):
    client, _, provider, _ = setup
    provider.videos = [video(**replacement)]
    assert client.post("/api/discovery/search", json={"keyword": "cooking"}).json()["items"] == []


@pytest.mark.parametrize("change", ["live", "upcoming", "future", "no_timezone", "unsafe_thumbnail"])
def test_metadata_edge_cases(setup, change):
    client, _, provider, _ = setup
    item = video()
    if change in {"live", "upcoming"}:
        item["snippet"]["liveBroadcastContent"] = change
    elif change == "future":
        item["snippet"]["publishedAt"] = "2027-01-01T00:00:00Z"
    elif change == "no_timezone":
        item["snippet"]["publishedAt"] = "2026-10-20T00:00:00"
    else:
        item["snippet"]["thumbnails"] = {"high": {"url": "http://127.0.0.1/private"}}
    provider.videos = [item]
    result = client.post("/api/discovery/search", json={"keyword": "cooking"}).json()
    assert (result["items"][0]["thumbnail_url"] is None) if change == "unsafe_thumbnail" else result["total"] == 0


def test_duplicate_ids_and_details_deduplicated(setup):
    client, _, provider, _ = setup
    provider.videos = [video(), video()]
    result = client.post("/api/discovery/search", json={"keyword": "cooking"}).json()
    assert result["total"] == 1 and result["scanned_count"] == 1
    assert provider.calls[1].url.params["id"] == VIDEO


def test_cache_reuse_expiry_and_metadata_reuse_across_queries(setup):
    client, _, provider, clock = setup
    first = client.post("/api/discovery/search", json={"keyword": "cooking"}).json()
    second = client.post("/api/discovery/search", json={"keyword": "  cooking  "}).json()
    assert second["cache_hit"] and second["items"] == first["items"]
    assert second["search_id"] != first["search_id"] and len(provider.calls) == 2
    clock[0] += 3500
    third = client.post("/api/discovery/search", json={"keyword": "料理"}).json()
    assert not third["cache_hit"] and len(provider.calls) == 3  # search only; reuse video metadata
    assert third["expires_at"] == first["expires_at"]  # no extension of old metadata
    clock[0] += 101
    fourth = client.post("/api/discovery/search", json={"keyword": "料理"}).json()
    assert not fourth["cache_hit"] and len(provider.calls) == 5


def test_cache_and_history_survive_new_service(setup):
    client, old, provider, clock = setup
    client.post("/api/discovery/search", json={"keyword": "cooking"})
    new = DiscoveryService(old.settings, clock=lambda: clock[0], transport=httpx.MockTransport(provider))
    assert new.search(SearchRequest(keyword="cooking")).cache_hit
    assert len(new.history()["items"]) == 2 and len(provider.calls) == 2


def test_bounded_pagination_and_cross_page_duplicates(setup):
    client, _, provider, _ = setup
    provider.videos = [video(views=1), video(OTHER, views=20000)]
    provider.search_pages = {
        "first": {"items": [{"id": {"videoId": VIDEO}}], "nextPageToken": "second"},
        "second": {"items": [{"id": {"videoId": VIDEO}}, {"id": {"videoId": OTHER}}]},
    }
    result = client.post("/api/discovery/search", json={"keyword": "cooking", "min_views": 10000}).json()
    assert result["total"] == 1 and result["items"][0]["video_id"] == OTHER
    assert result["scanned_count"] == 2 and result["pages_fetched"] == 2
    assert len(provider.calls) == 4


def test_page_limit_and_no_details_for_empty_pages(setup):
    client, _, provider, _ = setup
    provider.search_pages = {"first": {"items": [], "nextPageToken": "a"},
                             "a": {"items": [], "nextPageToken": "b"},
                             "b": {"items": [], "nextPageToken": "c"}}
    result = client.post("/api/discovery/search", json={"keyword": "nothing"}).json()
    assert result["limited"] and result["pages_fetched"] == 3 and result["total"] == 0
    assert len(provider.calls) == 3


def test_max_50_and_deterministic_sort(setup):
    client, _, provider, _ = setup
    provider.videos = [video(f"{i:011d}", views=10000 + i) for i in range(50)]
    data = client.post("/api/discovery/search", json={"keyword": "cooking"}).json()
    assert len(data["items"]) == 50
    assert [v["recommendation_score"] for v in data["items"]] == sorted([v["recommendation_score"] for v in data["items"]], reverse=True)


@pytest.mark.parametrize("payload", [
    {"keyword": " "}, {"keyword": "x" * 201}, {"keyword": "a", "max_results": 51},
    {"keyword": "a", "min_views": -1}, {"keyword": "a", "min_duration_seconds": 10, "max_duration_seconds": 5},
    {"keyword": "a", "published_after": "2026-01-01T00:00:00"},
    {"keyword": "a", "published_after": "2026-10-23T00:00:00Z", "published_before": "2026-10-20T00:00:00Z"},
    {"keyword": "a", "relevance_language": "unknown"}, {"keyword": "a", "api_key": "not-allowed"},
])
def test_invalid_input_never_calls_provider(setup, payload):
    client, _, provider, _ = setup
    assert client.post("/api/discovery/search", json=payload).status_code == 422
    assert not provider.calls


@pytest.mark.parametrize("status,reason,code", [
    (403, "quotaExceeded", "youtube_quota_exceeded"),
    (403, "dailyLimitExceeded", "youtube_quota_exceeded"),
    (429, "rateLimitExceeded", "provider_rate_limited"),
    (403, "keyInvalid", "provider_access_denied"), (500, "backendError", "provider_unavailable"),
])
def test_upstream_errors_are_sanitized_and_recorded(setup, status, reason, code, caplog):
    client, service, provider, _ = setup
    provider.error = lambda req: httpx.Response(status, json={"error": {"message": "fixture-key", "errors": [{"reason": reason}]}})
    with caplog.at_level(logging.INFO):
        response = client.post("/api/discovery/search", json={"keyword": "cooking"})
    assert response.json()["detail"]["code"] == code
    assert response.status_code == (429 if "quota" in code or "rate" in code else 502)
    assert "fixture-key" not in response.text and "fixture-key" not in caplog.text
    assert service.history()["items"][0]["error_code"] == code
    assert "fixture-key" not in service.settings.db_path.read_bytes().decode(errors="ignore")
    if code == "youtube_quota_exceeded":
        assert client.post("/api/discovery/search", json={"keyword": "different"}).json()["detail"]["code"] == "local_quota_exceeded"
        assert len(provider.calls) == 1


def test_timeout_no_retry(setup):
    client, _, provider, _ = setup
    def timeout(request):
        raise httpx.ReadTimeout("fixture-key", request=request)
    provider.error = timeout
    response = client.post("/api/discovery/search", json={"keyword": "cooking"})
    assert response.status_code == 504 and "fixture-key" not in response.text
    assert len(provider.calls) == 1


@pytest.mark.parametrize("body", [[], {}, {"items": "bad"}, {"items": [None]}])
def test_invalid_upstream_response(setup, body):
    client, _, provider, _ = setup
    provider.error = lambda request: httpx.Response(200, json=body)
    assert client.post("/api/discovery/search", json={"keyword": "cooking"}).json()["detail"]["code"] == "invalid_provider_response"


def test_missing_key_is_clear_and_no_outbound(setup):
    client, service, provider, _ = setup
    service.settings = replace(service.settings, api_key="")
    response = client.post("/api/discovery/search", json={"keyword": "cooking"})
    assert response.status_code == 503 and response.json()["detail"]["code"] == "provider_not_configured"
    assert not provider.calls


def test_feature_disabled_without_creating_storage(tmp_path, monkeypatch):
    app.dependency_overrides.clear()
    get_service.cache_clear()
    monkeypatch.setenv("DISCOVERY_ENABLED", "0")
    monkeypatch.setenv("DISCOVERY_DB_PATH", str(tmp_path / "unused.db"))
    with TestClient(app) as client:
        assert client.get("/api/discovery/history").json()["detail"]["code"] == "discovery_disabled"
    assert not (tmp_path / "unused.db").exists()
    get_service.cache_clear()


def test_request_rate_limit_includes_cached_searches_and_persists(setup):
    _, service, provider, clock = setup
    service.repository.settings = replace(service.settings, requests_per_minute=1)
    service.search(SearchRequest(keyword="cooking"))
    with pytest.raises(DiscoveryError, match="request limit"):
        service.search(SearchRequest(keyword="cooking"))
    assert len(provider.calls) == 2
    clock[0] += 61
    assert service.search(SearchRequest(keyword="cooking")).cache_hit


def test_atomic_persistent_api_budget_and_utc_reset(setup):
    _, service, _, clock = setup
    repo = service.repository
    repo.settings = replace(service.settings, api_calls_per_day=5)
    def reserve(_):
        try:
            repo.reserve_api_call(1, clock[0])
            return True
        except DiscoveryError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(12))) == 5
    clock[0] += 86400
    assert reserve(0)


def test_unit_budget_blocks_before_network(setup):
    client, service, provider, _ = setup
    service.repository.settings = replace(service.settings, quota_units_per_day=99)
    response = client.post("/api/discovery/search", json={"keyword": "cooking"})
    assert response.status_code == 429 and not provider.calls


def test_history_pagination_and_validation(setup):
    client, _, _, _ = setup
    for _ in range(3):
        client.post("/api/discovery/search", json={"keyword": "cooking"})
    first = client.get("/api/discovery/history?limit=2").json()
    second = client.get(f"/api/discovery/history?limit=2&before_id={first['next_before_id']}").json()
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    assert second["next_before_id"] is None
    assert client.get("/api/discovery/history?limit=101").status_code == 422
    assert client.get("/api/discovery/history?before_id=999999999999999999999999").status_code == 422


@pytest.mark.parametrize("status,code", [(200, "invalid_provider_response"), (429, "provider_rate_limited"), (503, "provider_unavailable")])
def test_html_or_invalid_json_provider_response(setup, status, code):
    client, _, provider, _ = setup
    provider.error = lambda request: httpx.Response(status, text="not JSON; fixture-key")
    response = client.post("/api/discovery/search", json={"keyword": "cooking"})
    assert response.json()["detail"]["code"] == code
    assert "fixture-key" not in response.text


def test_ranking_uses_all_signals_and_is_bounded():
    def score(views=10000, age=3, title="cooking"):
        return score_video("cooking", title, "", views, NOW - timedelta(days=age), NOW)[0]
    assert score(views=100000) > score(views=10)
    assert score(age=1) > score(age=100)
    assert score(title="cooking tutorial") > score(title="unrelated")
    assert 0 <= score(views=0) <= 100 and 0 <= score(views=10**15) <= 100
    assert relevance("한국 요리", "한국 요리 수업", "") == 1
    assert relevance("料理", "日本料理", "") == 1
    assert relevance("COOKING", "cooking", "") == 1
    assert relevance("!!!", "cooking", "") == 0


@pytest.mark.parametrize("duration,expected", [("PT1H2M3S", 3723), ("P1D", 86400), ("PT1.5S", 1)])
def test_iso_duration(duration, expected):
    assert duration_seconds(duration) == expected


def test_main_app_keeps_existing_and_new_routes():
    import app as existing
    # Newer FastAPI keeps include_router entries lazy; inspect its supported API.
    paths = existing.app.openapi()["paths"]
    assert "post" in paths["/api/discovery/search"]
    assert "get" in paths["/api/discovery/history"]
    assert "post" in paths["/api/process"] and "get" in paths["/api/status/{job_id}"]
