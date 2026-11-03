"""Approved-source composition. Paid APIs mocked, local FFmpeg rendering is real."""
import asyncio
import io
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace as NS

import httpx
import pytest
from PIL import Image
import app as engine
from studio.product_video import api as product_api, storage, scripts
from studio.product_video.providers import PROVIDERS, VideoProvider, provider_catalog
from studio.product_video.render import render_product


def ident(): return str(uuid.uuid4())


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setenv('GEMINI_API_KEY', 'mock-key')
    monkeypatch.setattr(engine, 'BILLING_ENABLED', False)
    return tmp_path


async def req(method, path, **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=engine.app), base_url='http://test') as client:
        return await client.request(method, '/api/saasshorts/product' + path, **kwargs)


def photo():
    output = io.BytesIO(); Image.new('RGB', (120, 160), '#aadeff').save(output, format='PNG'); return output.getvalue()


async def upload_photo():
    response = await req('POST', '/assets', data={'kind': 'image', 'rights_confirmed': 'true'}, files={'file': ('owned.png', photo(), 'image/png')})
    assert response.status_code == 200, response.text
    return response.json()


def body(asset_id, **kwargs):
    return {'request_id': ident(), 'scenes': [{'asset_id': asset_id}], 'description': '확인된 상품',
            'rights_confirmed': True, 'paid_confirmed': True, 'content_confirmed': True, **kwargs}


async def wait(ident):
    for _ in range(100):
        response = await req('GET', f'/requests/{ident}')
        data = response.json()
        if data['state'] in ('completed', 'failed', 'interrupted'): return data
        await asyncio.sleep(.01)
    pytest.fail('Mock background worker did not finish')


def test_capabilities_and_unimplemented_providers():
    catalog = {p['id']: p for p in provider_catalog()}
    assert isinstance(PROVIDERS['ffmpeg-product'], VideoProvider)
    assert catalog['ffmpeg-product']['capabilities']['approved_media_composition']
    assert not catalog['ffmpeg-product']['capabilities']['lipsync']
    assert catalog['fal-actor']['capabilities']['lipsync']
    assert not catalog['kling-official']['available'] and catalog['ltx-official']['capabilities'] is None


def test_upload_requires_rights_and_decodes_real_image(setup):
    async def run():
        rejected = await req('POST', '/assets', data={'kind': 'image'}, files={'file': ('a.png', photo(), 'image/png')})
        assert rejected.status_code == 400
        item = await upload_photo()
        assert 'user_id' not in item and 'path' not in item
        preview = await req('GET', '/assets/' + item['id']); assert preview.content == photo()
        bad = await req('POST', '/assets', data={'kind': 'image', 'rights_confirmed': 'true'}, files={'file': ('a.png', b'not-image', 'image/png')})
        assert bad.status_code == 422
    asyncio.run(run())


def test_owner_and_expiration_guards(setup, monkeypatch):
    async def run():
        item = await upload_photo()
        async def reject(request, record): raise engine.HTTPException(404, 'Not found')
        with monkeypatch.context() as m:
            m.setattr(engine, '_assert_job_owner', reject)
            assert (await req('GET', '/assets/' + item['id'])).status_code == 404
        path = storage.root(engine) / item['id'] / 'meta.json'
        data = json.loads(path.read_text()); data['created_at'] = 0; path.write_text(json.dumps(data))
        assert (await req('GET', '/assets/' + item['id'])).status_code == 410
        assert (await req('GET', '/assets/../../secret')).status_code != 200
    asyncio.run(run())


def test_analysis_idempotency_paid_confirmation_and_uploaded_scene_prompt(setup, monkeypatch):
    calls = []
    def generate(description, scenes, language, key):
        calls.append(scenes)
        return {'language': 'ko', 'production_mode': 'product', 'full_narration': '상품 정보',
                'segments': [{'asset_id': scenes[0]['asset_id'], 'narration': '상품 정보'}]}
    monkeypatch.setattr(product_api, 'generate_product_script', generate)
    async def run():
        item = await upload_photo(); request = body(item['id'])
        assert (await req('POST', '/analyze', json={**request, 'paid_confirmed': False})).status_code == 400
        results = await asyncio.gather(req('POST', '/analyze', json=request), req('POST', '/analyze', json=request))
        assert all(r.status_code == 200 for r in results)
        result = await wait(request['request_id']); assert result['state'] == 'completed'
        assert len(calls) == 1 and calls[0][0]['kind'] == 'image'
        assert (await req('POST', '/analyze', json={**request, 'description': 'changed'})).status_code == 409
        assert len(calls) == 1
    asyncio.run(run())


def test_product_generate_no_fal_no_actor_no_elevenlabs_and_missing_file(setup, monkeypatch):
    calls = []
    monkeypatch.setattr(product_api.gemini_tts, 'verify_model', lambda *args: {'model': 'mock-model'})
    def render(script, config, output, log):
        assert 'fal_key' not in config and 'elevenlabs_key' not in config
        path = Path(output); path.mkdir(parents=True); (path / 'product.mp4').write_bytes(b'mock-mp4')
        calls.append(config); return {'filename': 'product.mp4', 'duration': 2}
    monkeypatch.setattr(PROVIDERS['ffmpeg-product'], 'render', render)
    async def run():
        item = await upload_photo(); request = body(item['id'], script={'production_mode': 'product', 'language': 'ko', 'full_narration': '상품', 'segments': [{'asset_id': item['id']}]})
        assert (await req('POST', '/generate', json={**request, 'content_confirmed': False})).status_code == 400
        assert (await req('POST', '/generate', json=request)).status_code == 200
        result = await wait(request['request_id']); assert result['state'] == 'completed', result
        assert (await req('GET', '/download/' + request['request_id'])).content == b'mock-mp4'
        assert len(calls) == 1
        output = storage.root(engine) / ('job_' + request['request_id']) / 'product.mp4'
        output.write_bytes(b'')
        assert (await req('GET', '/requests/' + request['request_id'])).json()['state'] == 'failed'
        assert (await req('GET', '/download/' + request['request_id'])).status_code == 404
        output.write_bytes(b'mock-mp4')
        assert (await req('POST', '/generate', json=request)).status_code == 200
        assert len(calls) == 1
        (storage.root(engine) / ('job_' + request['request_id']) / 'product.mp4').unlink()
        assert (await req('GET', '/requests/' + request['request_id'])).json()['state'] == 'failed'
        assert (await req('GET', '/download/' + request['request_id'])).status_code == 404
    asyncio.run(run())


def test_paid_failure_no_auto_retry(setup, monkeypatch):
    calls = []
    def fail(*args): calls.append(True); raise RuntimeError('mock API failure with secret body')
    monkeypatch.setattr(product_api, 'generate_product_script', fail)
    async def run():
        item = await upload_photo(); request = body(item['id'])
        await req('POST', '/analyze', json=request)
        result = await wait(request['request_id']); assert result['state'] == 'failed'
        assert 'secret body' not in str(result)
        await req('POST', '/analyze', json=request)
        assert len(calls) == 1
    asyncio.run(run())


def test_missing_key_and_out_of_bounds_scene_reject_before_paid(setup, monkeypatch):
    async def run():
        item = await upload_photo()
        monkeypatch.delenv('GEMINI_API_KEY')
        assert (await req('POST', '/analyze', json=body(item['id']))).status_code == 400
        monkeypatch.setenv('GEMINI_API_KEY', 'mock')
        metadata = storage.root(engine) / item['id'] / 'meta.json'
        data = json.loads(metadata.read_text()); data.update(kind='video', duration=2); metadata.write_text(json.dumps(data))
        request = body(item['id']); request['scenes'][0]['end'] = 3
        assert (await req('POST', '/analyze', json=request)).status_code == 422
        request['scenes'][0]['end'] = -1
        assert (await req('POST', '/analyze', json=request)).status_code == 422
    asyncio.run(run())


def test_restart_never_replays_paid_request(setup):
    async def run():
        request_id = ident()
        assert storage.claim(engine, request_id, None, {'action': 'analyze'})
        data = (await req('GET', '/requests/' + request_id)).json()
        assert data['state'] == 'interrupted'
        assert not storage.claim(engine, request_id, None, {'action': 'analyze'})
    asyncio.run(run())


def test_product_script_is_not_actor_five_segment_template(monkeypatch):
    prompts = []
    scene = {'asset_id': ident(), 'kind': 'image', 'note': '승인된 상품 정면'}
    class Client:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        @property
        def models(self): return self
        def generate_content(self, **kwargs):
            prompts.append(kwargs['contents'])
            return NS(text=json.dumps({'full_narration': '상품 안내', 'segments': [{'asset_id': scene['asset_id']}]}))
    monkeypatch.setattr(scripts, 'client_for', lambda key: Client())
    result = scripts.generate_product_script('판매가 미확인', [scene], 'ko', 'mock')
    assert result['production_mode'] == 'product' and result['language'] == 'ko'
    assert 'Do not require an actor' in prompts[0] and '승인된 상품 정면' in prompts[0]


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required for real product composition')
@pytest.mark.parametrize('motion,transition', [('zoom', 'fade'), ('pan', 'cut')])
def test_real_ffmpeg_photo_video_crop_music_korean_ass_and_download(tmp_path, monkeypatch, motion, transition):
    from studio.product_video import render
    monkeypatch.setattr(render, 'ensure_runtime', lambda: None)  # ASR intentionally mocked; actual FFmpeg is exercised.
    image = tmp_path / 'owned.png'; image.write_bytes(photo())
    video = tmp_path / 'owned.mp4'; voice = tmp_path / 'voice.wav'; music = tmp_path / 'music.wav'
    def ff(*args): subprocess.run(['ffmpeg', '-v', 'error', '-y', *args], check=True, capture_output=True)
    ff('-f', 'lavfi', '-i', 'color=c=navy:s=160x120:d=2:r=30', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video))
    ff('-f', 'lavfi', '-i', 'sine=frequency=440:duration=2.4', '-ar', '24000', str(voice))
    ff('-f', 'lavfi', '-i', 'sine=frequency=220:duration=1', str(music))
    def tts(text, key, output, *args): ff('-i', str(voice), str(output)); return output
    monkeypatch.setattr(render, 'generate_voiceover', tts)
    # Only ASR is mocked; actual existing ASS writer and every FFmpeg stage runs.
    import saasshorts
    monkeypatch.setattr(saasshorts, 'transcribe_audio_for_subs', lambda *a, **kw: [{'word': '한국어상품안내를확인해요', 'start': 0, 'end': 2.3}])
    output = tmp_path / 'result'
    result = render_product({'full_narration': '상품 정보'}, {'gemini_key': 'mock', 'model': 'mock', 'voice': 'Kore',
        'scenes': [{'path': str(image), 'kind': 'image', 'duration': 2, 'motion': motion, 'crop': 'left'},
                   {'path': str(video), 'kind': 'video', 'start': .2, 'end': 1.2, 'crop': 'right', 'motion': 'none'}],
        'transition': transition, 'music': {'path': str(music)}, 'music_volume': .1}, str(output), log=lambda message: None)
    streams, duration = storage.probe(output / 'product.mp4')
    assert any(s.get('width') == 720 and s.get('height') == 1280 for s in streams)
    assert any(s.get('codec_type') == 'audio' for s in streams)
    assert 2.3 < duration < 2.8 and result['cost']['fal_usd'] == 0
    assert 'Noto Sans CJK KR' in (output / 'captions.ass').read_text()
    ff('-i', str(output / 'product.mp4'), '-f', 'null', '-')  # Decode the complete delivered file.


@pytest.mark.parametrize('action', ['analyze', 'actor-options', 'generate'])
def test_preserved_actor_paid_requests_are_idempotent(setup, monkeypatch, action):
    calls = []
    monkeypatch.setattr(engine, 'OUTPUT_DIR', str(setup / 'actor-output'))
    monkeypatch.setattr(engine, 'saas_jobs', {})
    monkeypatch.setattr(engine, 'generate_scripts', lambda *a: calls.append('analyze') or [{'title': 'legacy', 'language': 'en'}])
    monkeypatch.setattr(engine, 'generate_actor_images', lambda *a, **kw: calls.append('actor-options') or [])
    monkeypatch.setattr(engine, 'generate_full_video', lambda *a: calls.append('generate') or {'video_filename': 'mock.mp4'})
    async def run():
        monkeypatch.setattr(engine, 'concurrency_semaphore', asyncio.Semaphore(1))
        payload = {'request_id': ident(), 'paid_confirmed': True}
        payload.update({'description': 'actual facts', 'language': 'en'} if action == 'analyze' else
                       {'actor_description': 'adult person'} if action == 'actor-options' else
                       {'script': {'language': 'en'}, 'tts_provider': 'elevenlabs'})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=engine.app), base_url='http://test') as client:
            first = await client.post('/api/saasshorts/' + action, json=payload, headers={'X-Fal-Key': 'mock', 'X-ElevenLabs-Key': 'mock'})
            assert first.status_code == 200, first.text
            second = await client.post('/api/saasshorts/' + action, json=payload, headers={'X-Fal-Key': 'mock', 'X-ElevenLabs-Key': 'mock'})
            assert second.status_code == 200 and first.json() == second.json()
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and 'run_generation' in t.get_coro().__qualname__]
            await asyncio.gather(*tasks)
        assert calls == [action]
    asyncio.run(run())


def test_size_limit_and_nonfinite_input_are_rejected(setup, monkeypatch):
    async def run():
        with monkeypatch.context() as m:
            m.setattr(storage, 'MAX_BYTES', 8)
            assert (await req('POST', '/assets', data={'kind': 'image', 'rights_confirmed': 'true'}, files={'file': ('a.png', photo(), 'image/png')})).status_code == 413
        item = await upload_photo()
        request = body(item['id']); request['scenes'][0]['crop'] = '../../'
        assert (await req('POST', '/analyze', json=request)).status_code == 422
        request = body(item['id']); request['tts_provider'] = 'fal'
        assert (await req('POST', '/analyze', json=request)).status_code == 422
    asyncio.run(run())


def test_ledger_expiration_keeps_paid_request_tombstone(setup):
    async def run():
        request_id = ident(); payload = {'action': 'analyze'}
        storage.claim(engine, request_id, None, payload)
        with storage.connection(engine) as db: db.execute('UPDATE requests SET created=0 WHERE id=?', (request_id,))
        assert (await req('GET', '/requests/' + request_id)).json()['state'] == 'expired'
        assert not storage.claim(engine, request_id, None, payload)
    asyncio.run(run())


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required for actual video/audio upload verification')
def test_real_video_music_upload_and_unsafe_playlist_rejection(setup):
    movie = setup / 'owned.mp4'; music = setup / 'owned.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:d=1', '-c:v', 'libx264', str(movie)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=1', str(music)], check=True)
    async def run():
        video = await req('POST', '/assets', data={'kind': 'video', 'rights_confirmed': 'true'}, files={'file': ('owned.mp4', movie.read_bytes(), 'video/mp4')})
        audio = await req('POST', '/assets', data={'kind': 'music', 'rights_confirmed': 'true'}, files={'file': ('owned.wav', music.read_bytes(), 'audio/wav')})
        assert video.status_code == audio.status_code == 200
        assert video.json()['duration'] == audio.json()['duration'] == 1
        playlist = b'#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nhttp://127.0.0.1:9/secret.ts\n#EXT-X-ENDLIST\n'
        rejected = await req('POST', '/assets', data={'kind': 'video', 'rights_confirmed': 'true'}, files={'file': ('bad.mp4', playlist, 'video/mp4')})
        assert rejected.status_code == 422
    asyncio.run(run())


def test_account_erasure_removes_owned_sources_and_private_outputs(setup):
    base = storage.root(engine); asset_id = ident(); request_id = ident()
    directory = base / asset_id; directory.mkdir(); (directory / 'source').write_bytes(b'owned')
    (directory / 'meta.json').write_text(json.dumps({'user_id': 'owned-user'}))
    job = base / ('job_' + request_id); job.mkdir(); (job / 'product.mp4').write_bytes(b'owned')
    storage.claim(engine, request_id, 'owned-user', {'test': True})
    storage.update(engine, request_id, 'completed', {'script': 'private product facts'})
    assert storage.purge_user(engine, 'owned-user') == 2
    assert not directory.exists() and not job.exists()
    with storage.connection(engine) as db:
        row = db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
    assert row['owner'] == 'deleted' and row['response'] == '{}' and row['state'] == 'expired'


def test_missing_local_asr_fails_before_paid_tts(tmp_path, monkeypatch):
    from studio.product_video import render
    monkeypatch.setattr(render, 'find_spec', lambda name: None)
    monkeypatch.setattr(render, 'generate_voiceover', lambda *a: pytest.fail('Do not pay TTS before local prerequisites'))
    with pytest.raises(RuntimeError, match='유료 음성을 생성하지 않았습니다'):
        render.render_product({'full_narration': '상품'}, {}, str(tmp_path), log=lambda message: None)
