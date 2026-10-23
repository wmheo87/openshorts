"""Real ASGI handover/queue contract, with metadata HTTP mocked and no worker lifespan."""
import asyncio
import json
from dataclasses import replace
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import HTTPException

import app as engine
from studio.discovery import router
from studio.discovery.config import Settings
from studio.discovery.errors import DiscoveryError
from studio.discovery.production import read_source, verify_source
from studio.discovery.service import DiscoveryService

VIDEO_ID = "abcdefghijk"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
SOURCE = {"video_id": VIDEO_ID, "url": URL, "title": "Selected title", "channel_title": "Selected channel",
          "license": "creativeCommon", "metadata_fetched_at": "2026-10-20T00:00:00Z", "download_authorized": True}


def metadata():
    return {"id": VIDEO_ID, "snippet": {"title": "Fresh title", "description": "Source description", "channelId": "channel",
            "channelTitle": "Fresh channel", "publishedAt": "2026-10-19T00:00:00Z", "liveBroadcastContent": "none"},
            "statistics": {"viewCount": "10000"}, "contentDetails": {"duration": "PT10M"},
            "status": {"license": "creativeCommon", "privacyStatus": "public", "uploadStatus": "processed"}}


def request(method, path, **kwargs):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=engine.app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(run())


@pytest.fixture
def setup(tmp_path, monkeypatch):
    output = tmp_path / "output"; output.mkdir()
    uploads = tmp_path / "uploads"; uploads.mkdir()
    monkeypatch.setattr(engine, "OUTPUT_DIR", str(output)); monkeypatch.setattr(engine, "UPLOAD_DIR", str(uploads))
    monkeypatch.setattr(engine, "jobs", {}); monkeypatch.setattr(engine, "job_queue", asyncio.PriorityQueue())
    monkeypatch.setattr(engine, "QUALITY_GATE_MIN_HEIGHT", 0); monkeypatch.setattr(engine, "MIN_SOURCE_SECONDS", 0)
    monkeypatch.setattr(engine, "DISABLE_YOUTUBE_URL", False); monkeypatch.setattr(engine, "_draining", False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(engine.llm_backend, "active", lambda: False)
    checked = []
    async def validate(url):
        checked.append(url)
        if url != URL: raise HTTPException(400, "Unsafe or mismatched URL")
    monkeypatch.setattr(engine, "_validate_source_url", validate)
    calls, state = [], {"items": [metadata()]}
    def provider(req):
        calls.append(req)
        assert req.url.path.endswith('/videos')  # Fresh check never performs a search or download.
        return httpx.Response(200, json=state)
    service = DiscoveryService(Settings(enabled=True, api_key="fixture-key", db_path=tmp_path / "discovery.db"),
                               clock=lambda: datetime(2026, 10, 23, tzinfo=timezone.utc).timestamp(),
                               transport=httpx.MockTransport(provider))
    monkeypatch.setattr(router, "get_service", lambda: service)
    return output, service, calls, state, checked


def post(body=None, key=True):
    return request("POST", "/api/process", json={"url": URL, "acknowledged": True, "discovery_source": SOURCE, **(body or {})},
                   headers={"X-Gemini-Key": "fixture-gemini"} if key else {})


def test_discovery_reuses_existing_queue_options_security_and_records_source(setup):
    output, service, calls, _, checked = setup
    response = post({"output_format": "vertical", "layouts": ["auto"], "target_clips": 3,
                     "clip_min_seconds": 15, "clip_max_seconds": 30, "auto_hook": "1"})
    assert response.status_code == 200, response.text
    job_id = response.json()['job_id']; job = engine.jobs[job_id]
    assert job['status'] == 'queued' and engine.job_queue.qsize() == 1
    assert checked == [URL] and len(calls) == 1
    assert job['cmd'][:3] == [engine.sys.executable, '-u', 'main.py']
    assert job['cmd'][job['cmd'].index('-u', 3) + 1] == URL
    assert job['cmd'][job['cmd'].index('--format') + 1] == 'vertical'
    assert job['env']['CLIP_TARGET_MIN'] == job['env']['CLIP_TARGET_MAX'] == '3'
    assert job['env']['CLIP_MIN_SECONDS'] == '15.0' and job['env']['CLIP_MAX_SECONDS'] == '30.0'
    assert job['env']['AUTO_HOOK'] == '1' and job['env']['AUTO_LAYOUT'] == '1'
    source = job['discovery_source']
    assert source['title'] == 'Fresh title' and source['selected_metadata']['title'] == 'Selected title'
    assert source['metadata_fetched_at'] == '2026-10-23T00:00:00+00:00'
    assert json.loads((output / job_id / '.discovery-source.json').read_text()) == source
    job.pop('discovery_source')  # Simulate runtime record rebuilt after a restart.
    assert read_source(job) == source
    status = request('GET', f'/api/status/{job_id}').json()
    assert status['status'] == 'queued' and status['discovery_source'] == source
    with service.repository.connection() as db:
        assert tuple(db.execute('SELECT calls,units FROM discovery_api_budget').fetchone()) == (1, 1)


@pytest.mark.parametrize('patch,code', [
    ({'acknowledged': False}, None), ({'acknowledged': 'false'}, None),
    ({'discovery_source': {**SOURCE, 'download_authorized': False}}, 'download_not_confirmed'),
    ({'discovery_source': {**SOURCE, 'download_authorized': 'true'}}, 'invalid_discovery_source'),
    ({'discovery_source': {**SOURCE, 'video_id': 'bad'}}, 'invalid_discovery_source'),
    ({'discovery_source': {**SOURCE, 'url': 'https://www.youtube.com/watch?v=lmnopqrstuv'}}, 'invalid_discovery_source'),
])
def test_rights_and_source_validation_fail_before_queue_or_external_call(setup, patch, code):
    _, _, calls, _, _ = setup
    response = post(patch)
    assert response.status_code in (400, 422)
    if code: assert response.json()['detail']['code'] == code
    assert not engine.jobs and not calls and engine.job_queue.empty()


@pytest.mark.parametrize('change,code', [('deleted', 'source_unavailable'), ('private', 'source_unavailable'), ('license', 'source_license_changed'), ('live', 'source_unavailable')])
def test_fresh_check_rejects_changed_source_and_does_not_use_cache(setup, change, code):
    _, service, calls, state, _ = setup
    service.repository.cache_videos([{'video_id': VIDEO_ID, 'fake': 'stale metadata'}], service.clock() + 3600)
    if change == 'deleted': state['items'] = []
    elif change == 'private': state['items'][0]['status']['privacyStatus'] = 'private'
    elif change == 'license': state['items'][0]['status']['license'] = 'youtube'
    else: state['items'][0]['snippet']['liveBroadcastContent'] = 'live'
    response = post()
    assert response.status_code == 409 and response.json()['detail']['code'] == code
    assert len(calls) == 1 and not engine.jobs


def test_metadata_budget_exhaustion_fails_closed_without_external_call(setup, monkeypatch):
    _, service, calls, _, _ = setup
    def exhausted(*args): raise DiscoveryError('local_quota_exceeded', 'Budget exhausted', 429)
    monkeypatch.setattr(service.repository, 'reserve_api_call', exhausted)
    assert post().status_code == 429
    assert not calls and not engine.jobs


def test_engine_key_and_url_policy_still_apply(setup, monkeypatch):
    _, _, calls, _, _ = setup
    assert post(key=False).status_code == 400
    monkeypatch.setattr(engine, 'DISABLE_YOUTUBE_URL', True)
    assert post().status_code == 403
    assert not calls and not engine.jobs


def test_quality_gate_requires_explicit_confirmation_and_rechecks_metadata(setup, monkeypatch):
    _, _, calls, _, _ = setup
    monkeypatch.setattr(engine, 'QUALITY_GATE_MIN_HEIGHT', 720)
    async def probe(url): return {'max_height': 360, 'duration': 600}
    monkeypatch.setattr(engine, '_probe_youtube_quality', probe)
    response = post()
    assert response.json()['needs_confirmation'] and not engine.jobs
    assert post({'force_low_quality': True}).status_code == 200
    assert len(engine.jobs) == 1 and len(calls) == 2


def test_short_source_gate_remains_active_even_if_low_quality_forced(setup, monkeypatch):
    monkeypatch.setattr(engine, 'MIN_SOURCE_SECONDS', 45)
    async def probe(url): return {'max_height': 1080, 'duration': 20}
    monkeypatch.setattr(engine, '_probe_youtube_quality', probe)
    response = post({'force_low_quality': True})
    assert response.status_code == 400 and '20s' in response.text and not engine.jobs


def test_missing_results_are_not_reported_complete_and_preserve_clip_indices(setup):
    output, _, _, _, _ = setup
    job_id = post().json()['job_id']; job = engine.jobs[job_id]
    (output / job_id / 'second.mp4').write_bytes(b'finished-fixture')
    job.update(status='completed', result={'clips': [{'video_url': f'/videos/{job_id}/missing.mp4'}, {'video_url': f'/videos/{job_id}/second.mp4'}]})
    data = request('GET', f'/api/status/{job_id}').json()
    assert data['status'] == 'failed' and 'missing' in data['error']
    assert len(data['result']['clips']) == 2
    assert data['result']['clips'][0]['unavailable'] is True and data['result']['clips'][1]['unavailable'] is False
    (output / job_id / 'second.mp4').unlink()
    assert all(clip['unavailable'] for clip in request('GET', f'/api/status/{job_id}').json()['result']['clips'])


def test_completed_available_results_and_owner_guard_remain(setup, monkeypatch):
    output, _, _, _, _ = setup
    job_id = post().json()['job_id']; job = engine.jobs[job_id]
    (output / job_id / 'clip.mp4').write_bytes(b'finished-fixture')
    job.update(status='completed', result={'clips': [{'video_url': f'/videos/{job_id}/clip.mp4'}]})
    assert request('GET', f'/api/status/{job_id}').json()['status'] == 'completed'
    async def forbidden(*args): raise HTTPException(403, 'Forbidden')
    monkeypatch.setattr(engine, '_assert_job_owner', forbidden)
    assert request('GET', f'/api/status/{job_id}').status_code == 403


def test_regular_url_and_file_upload_do_not_require_discovery_service(setup, monkeypatch):
    def unavailable(): raise AssertionError('Non-discovery flow must not initialize discovery')
    monkeypatch.setattr(router, 'get_service', unavailable)
    assert post({'discovery_source': None}).status_code == 200
    response = request('POST', '/api/process', data={'acknowledged': 'true', 'output_format': 'vertical'},
                       files={'file': ('owned.mp4', b'fixture-upload', 'video/mp4')}, headers={'X-Gemini-Key': 'fixture-key'})
    assert response.status_code == 200 and len(engine.jobs) == 2


def test_revalidation_needs_its_own_server_key_without_falling_back_to_cache(setup):
    _, service, calls, _, _ = setup
    service.settings = replace(service.settings, api_key='')
    response = post()
    assert response.status_code == 503 and response.json()['detail']['code'] == 'provider_not_configured'
    assert not calls and not engine.jobs


def test_existing_source_security_rejection_precedes_external_revalidation(setup, monkeypatch):
    _, _, calls, _, _ = setup
    async def reject(url): raise HTTPException(400, 'Source security rejected')
    monkeypatch.setattr(engine, '_validate_source_url', reject)
    assert post().status_code == 400
    assert not calls and not engine.jobs


def test_result_path_traversal_is_not_exposed_as_an_available_clip(setup):
    output, _, _, _, _ = setup
    job_id = post().json()['job_id']; job = engine.jobs[job_id]
    (output / 'outside.mp4').write_bytes(b'outside-job')
    job.update(status='completed', result={'clips': [{'video_url': f'/videos/{job_id}/../outside.mp4'}]})
    response = request('GET', f'/api/status/{job_id}').json()
    assert response['status'] == 'failed' and response['result']['clips'][0]['unavailable'] is True
