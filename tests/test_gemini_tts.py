"""No external calls: real GenAI serialization over HTTP MockTransport + synthetic PCM."""
import asyncio
import base64
import json
import shutil
import wave
from pathlib import Path
from types import SimpleNamespace as NS

import httpx
import pytest
from google import genai
from google.genai import types
import app as api
import saasshorts as saas
from studio import gemini_tts as tts


@pytest.fixture
def sdk(monkeypatch):
    state = {'model_status': 200, 'generate_status': 200, 'mime': 'audio/L16;codec=pcm;rate=24000',
             'data': bytes(2400 * 2), 'calls': []}
    def handler(req):
        state['calls'].append((req.method, str(req.url), json.loads(req.content) if req.content else None))
        if req.method == 'GET':
            if state['model_status'] != 200: return httpx.Response(state['model_status'], json={'error': {'message': 'mock unavailable'}})
            return httpx.Response(200, json={'name': 'models/' + tts.DEFAULT_MODEL, 'supportedGenerationMethods': ['generateContent']})
        if state['generate_status'] != 200: return httpx.Response(state['generate_status'], json={'error': {'message': 'mock synthesis failed'}})
        return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'inlineData': {
            'mimeType': state['mime'], 'data': base64.b64encode(state['data']).decode()}}]}}]})
    def client(key):
        return genai.Client(api_key=key, vertexai=False, http_options=types.HttpOptions(
            httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
            retry_options=types.HttpRetryOptions(attempts=1)))
    monkeypatch.setattr(tts, 'client_for', client)
    return state


def test_model_catalog_confirmation_does_not_claim_synthesis_or_free_price(sdk):
    result = tts.verify_model('mock')
    assert result['model'] == 'gemini-3.8-flash-lite-tts'
    assert result['catalog_confirmed'] and not result['audio_synthesis_verified']
    assert result['estimated_tts_usd'] is None
    assert len(sdk['calls']) == 1 and sdk['calls'][0][0] == 'GET'


@pytest.mark.parametrize('status', [403, 404, 429])
def test_unavailable_model_never_synthesizes_or_falls_back(sdk, tmp_path, status):
    sdk['model_status'] = status
    with pytest.raises(tts.GeminiTTSError, match='이용 가능 여부'):
        tts.generate_voiceover('상품', 'mock', str(tmp_path / 'voice.mp3'))
    assert all(call[0] == 'GET' for call in sdk['calls'])
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required for real local PCM→WAV→MP3 conversion')
def test_real_sdk_pcm_to_wav_mp3_without_external_synthesis(sdk, tmp_path):
    output = tmp_path / 'voice.mp3'
    assert tts.generate_voiceover('한국어 상품 정보를 확인해요', 'mock', str(output)) == str(output)
    with wave.open(str(output.with_suffix('.wav'))) as audio:
        assert audio.getnchannels() == 1 and audio.getsampwidth() == 2
        assert audio.getframerate() == 24000 and audio.getnframes() == 2400
    assert output.stat().st_size > 0
    body = next(call[2] for call in sdk['calls'] if call[0] == 'POST')
    assert body['generationConfig']['responseModalities'] == ['AUDIO']
    assert body['generationConfig']['speechConfig']['voice_config']['prebuilt_voice_config']['voice_name'] == 'Kore'
    assert '한국어 상품 정보' in json.dumps(body, ensure_ascii=False)


def test_synthesis_failure_is_single_attempt_and_no_partial_mp3(sdk, tmp_path):
    sdk['generate_status'] = 503
    output = tmp_path / 'voice.mp3'; output.write_bytes(b'partial')
    with pytest.raises(tts.GeminiTTSError, match='자동 재시도하지 않습니다'):
        tts.generate_voiceover('상품', 'mock', str(output))
    assert sum(call[0] == 'POST' for call in sdk['calls']) == 1
    assert not output.exists()


@pytest.mark.parametrize('mime,data', [('audio/mpeg', b'invalid'), ('audio/pcm', b'no-rate'), ('audio/L16;rate=24000', b'odd')])
def test_invalid_audio_metadata_is_rejected_without_conversion(sdk, monkeypatch, tmp_path, mime, data):
    sdk.update(mime=mime, data=data)
    monkeypatch.setattr(tts.subprocess, 'run', lambda *a, **k: pytest.fail('Must not convert invalid audio'))
    with pytest.raises(tts.GeminiTTSError): tts.generate_voiceover('상품', 'mock', str(tmp_path / 'voice.mp3'))


async def request(path, method='POST', **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url='http://test') as client:
        return await client.request(method, path, **kwargs)


def test_default_korean_gemini_api_needs_no_elevenlabs_key(monkeypatch, tmp_path):
    captured = []
    monkeypatch.setattr(api, 'OUTPUT_DIR', str(tmp_path)); monkeypatch.setattr(api, 'saas_jobs', {})
    monkeypatch.setattr(tts, 'verify_model', lambda key: captured.append(key) or {'model': tts.DEFAULT_MODEL})
    monkeypatch.setattr(api, 'get_elevenlabs_voices', lambda *a: pytest.fail('No ElevenLabs call for Gemini'))
    monkeypatch.setattr(api, 'generate_full_video', lambda script, config, *a: captured.append(config) or {'video_filename': 'mock.mp4'})
    async def run():
        monkeypatch.setattr(api, 'concurrency_semaphore', asyncio.Semaphore(1))
        response = await request('/api/saasshorts/generate', json={'script': {'language': 'ko'}}, headers={'X-Fal-Key': 'mock', 'X-Gemini-Key': 'mock'})
        assert response.status_code == 200, response.text
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and 'run_generation' in t.get_coro().__qualname__]
        await asyncio.gather(*tasks)
    asyncio.run(run())
    assert captured[0] == 'mock' and captured[1]['tts_provider'] == 'gemini'
    assert captured[1]['elevenlabs_key'] is None and captured[1]['gemini_key'] == 'mock'


def test_model_endpoint_missing_key_fails_without_synthesis(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    response = asyncio.run(request('/api/saasshorts/tts-model', method='GET'))
    assert response.status_code == 503 and 'API 키' in response.json()['detail']


def test_managed_tts_key_does_not_use_managed_billing_key(monkeypatch):
    monkeypatch.setattr(api, 'BILLING_ENABLED', True)
    monkeypatch.setenv('GEMINI_API_KEY', 'operator-key-not-for-new-tts')
    from starlette.requests import Request
    assert api.saas_gemini_tts_key(Request({'type': 'http', 'headers': []})) is None
    assert api.saas_gemini_tts_key(Request({'type': 'http', 'headers': [(b'x-gemini-key', b'user-key')]})) == 'user-key'


@pytest.mark.parametrize('mode', ['lowcost', 'premium'])
def test_gemini_audio_existing_lipsync_korean_subtitles_and_unknown_cost(monkeypatch, tmp_path, mode):
    seen = []
    def voice(text, key, output, voice, model):
        assert key == 'mock' and voice == 'Kore'; Path(output).write_bytes(b'gemini-mp3'); return output
    def asset(*args): Path(args[-1]).write_bytes(b'asset'); return args[-1]
    def head(image, audio, key, output):
        assert Path(audio).read_bytes() == b'gemini-mp3'; seen.append(mode); return asset(image, audio, key, output)
    monkeypatch.setattr(tts, 'generate_voiceover', voice)
    monkeypatch.setattr(saas, 'generate_voiceover', lambda *a: pytest.fail('No ElevenLabs fallback'))
    monkeypatch.setattr(saas, 'generate_actor_image', asset)
    monkeypatch.setattr(saas, 'generate_talking_head_lowcost', head); monkeypatch.setattr(saas, 'generate_talking_head', head)
    monkeypatch.setattr(saas, 'transcribe_audio_for_subs', lambda path, **kw: seen.append(kw['language']) or [{'word': '상품', 'start': 0, 'end': 1}])
    monkeypatch.setattr(saas, 'composite_video', lambda *args: Path(args[-1]).write_bytes(b'mock-mp4'))
    monkeypatch.setattr(saas, 'mark_ai_generated', lambda *a: None); monkeypatch.setattr(saas, '_get_media_duration', lambda *a: 1)
    result = saas.generate_full_video({'language': 'ko', 'title': '상품', 'full_narration': '상품 안내'},
        {'tts_provider': 'gemini', 'gemini_key': 'mock', 'gemini_voice': 'Kore', 'gemini_tts_model': tts.DEFAULT_MODEL, 'fal_key': 'mock', 'video_mode': mode}, str(tmp_path), log=lambda *a: None)
    assert seen == [mode, 'ko'] and '_gemini_' in result['video_filename']
    assert result['cost_estimate']['voiceover_gemini'] is None and result['cost_estimate']['total'] is None
    assert 'voiceover_elevenlabs' not in result['cost_estimate']


def test_failed_gemini_tts_never_starts_fal_or_elevenlabs(monkeypatch, tmp_path):
    def fail(*a): raise tts.GeminiTTSError('mock failed; unknown cost')
    monkeypatch.setattr(tts, 'generate_voiceover', fail)
    monkeypatch.setattr(saas, 'generate_actor_image', lambda *a: pytest.fail('No fal.ai spend after TTS failure'))
    monkeypatch.setattr(saas, 'generate_voiceover', lambda *a: pytest.fail('No paid fallback'))
    with pytest.raises(tts.GeminiTTSError):
        saas.generate_full_video({'language': 'ko', 'full_narration': '상품'}, {'tts_provider': 'gemini', 'fal_key': 'mock'}, str(tmp_path), log=lambda *a: None)
