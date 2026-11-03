"""Korean shopping scripts/voice boundaries. All external/paid calls are mocked."""
import asyncio
import json
from types import SimpleNamespace as NS

import httpx
import pytest
import saasshorts as saas
import app as api


@pytest.mark.parametrize('language,expected', [('ko', 'ko'), ('ko-KR', 'ko'), ('en', 'en'), ('es', 'es')])
def test_script_locale_and_prompt(monkeypatch, language, expected):
    from google import genai
    prompts = []
    def generate(**kwargs):
        prompts.append(kwargs['contents'][0])
        return NS(text=json.dumps([{'title': '상품 정보', 'language': 'wrong'}]))
    monkeypatch.setattr(genai, 'Client', lambda **kwargs: NS(models=NS(generate_content=generate)))
    result = saas.generate_scripts({'description': '텀블러, 12000원'}, 'mock', language=language)
    assert result[0]['language'] == expected
    prompt = prompts[0]
    if expected == 'ko':
        assert 'ko-KR' in prompt and '12000원' in prompt
        assert '할인율' in prompt and '임의 환산' in prompt and '제휴 관계를 가정하지' in prompt
        assert 'European' not in prompt and '#saas' not in prompt and 'link in bio' not in prompt
        assert '한국어 자막' in prompt and '실물 상품' in prompt
    else:
        assert ('SPANISH' if expected == 'es' else 'ENGLISH') in prompt
        assert 'European' in prompt  # Keep legacy en/es instructions.


@pytest.mark.parametrize('voice,expected,preview', [
    ({'labels': {'language': 'ko'}, 'preview_url': 'https://sample/ko'}, True, 'https://sample/ko'),
    ({'labels': {'accent': 'korean'}, 'preview_url': 'https://sample/ko'}, True, 'https://sample/ko'),
    ({'verified_languages': [{'language': 'ko', 'preview_url': 'https://sample/verified'}]}, True, 'https://sample/verified'),
    ({'verified_languages': [{'language': 'ko'}], 'preview_url': 'https://sample/en'}, True, ''),
    ({'labels': {'language': 'en'}, 'preview_url': 'https://sample/en'}, False, ''),
])
def test_korean_voice_evidence_and_preview(voice, expected, preview):
    assert saas.korean_voice_metadata(voice) == {'supports_korean': expected, 'korean_preview_url': preview}


def test_provider_voice_list_uses_account_metadata(monkeypatch):
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, headers):
            assert url.endswith('/voices') and headers['xi-api-key'] == 'mock'
            return httpx.Response(200, json={'voices': [{'voice_id': 'korean', 'name': '한국어', 'labels': {'language': 'ko'}}]})
    monkeypatch.setattr(saas.httpx, 'Client', Client)
    assert saas.get_elevenlabs_voices('mock')[0]['supports_korean']


def test_korean_whisper_uses_word_times_and_releases_model(monkeypatch):
    import transcribe_backends as backend
    calls = []
    monkeypatch.setattr(backend, 'run_whisper_transcription', lambda path, **kwargs: (
        calls.append(kwargs) or iter([NS(words=[NS(word='안녕하세요', start=.25, end=1.2)])]), NS(language='ko')))
    monkeypatch.setattr(backend, 'transcribe_media', lambda path: pytest.fail('Korean must use Whisper, not a European ASR backend'))
    monkeypatch.setattr(backend, 'release_models', lambda: calls.append('released'))
    assert saas.transcribe_audio_for_subs('mock.mp3', 'ko') == [{'word': '안녕하세요', 'start': .25, 'end': 1.2}]
    assert calls[0]['language'] == 'ko' and calls[0]['word_timestamps'] is True
    assert calls[-1] == 'released'


@pytest.mark.parametrize('language', ['ko', 'en', 'es'])
def test_subtitles_preserve_language_and_audio_timing(monkeypatch, tmp_path, language):
    def transcribe(path, **kwargs):
        assert kwargs['language'] == language
        return [{'word': '아주긴한국어상품설명문구가여기에있습니다' if language == 'ko' else 'hello', 'start': .25, 'end': 1.5}]
    monkeypatch.setattr(saas, 'transcribe_audio_for_subs', transcribe)
    path = tmp_path / 'captions.ass'
    saas.generate_tiktok_subs('mock.mp3', str(path), language=language)
    text = path.read_text(encoding='utf-8')
    assert '0:00:00.25,0:00:01.50' in text
    if language == 'ko':
        assert 'Noto Sans CJK KR' in text and '\\N' in text and '아주긴한국어' in text
    else:
        assert 'Arial Black' in text and 'HELLO' in text


async def request(method, path, **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url='http://test') as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.parametrize('language,expected', [('ko', 'ko'), ('ko-KR', 'ko'), ('en', 'en'), ('es', 'es')])
def test_analyze_endpoint_keeps_language(monkeypatch, language, expected):
    from google import genai
    async def key(request): return 'mock'
    async def reserve(*args): return None
    monkeypatch.setattr(api, 'resolve_gemini', key)
    monkeypatch.setattr(api, 'reserve_managed_action', reserve)
    monkeypatch.setattr(genai, 'Client', lambda **kwargs: NS(models=NS(generate_content=lambda **kwargs: NS(text='[{"title":"상품"}]'))))
    response = asyncio.run(request('POST', '/api/saasshorts/analyze', json={'description': '텀블러 12000원', 'language': language}))
    assert response.status_code == 200, response.text
    assert response.json()['scripts'][0]['language'] == expected


def test_korean_url_analysis_does_not_use_saas_research(monkeypatch):
    async def key(request): return 'mock'
    async def reserve(*args): return None
    monkeypatch.setattr(api, 'resolve_gemini', key)
    monkeypatch.setattr(api, 'reserve_managed_action', reserve)
    monkeypatch.setattr(api, 'scrape_website', lambda url: {'title': '텀블러', 'main_content': '가격 미확인'})
    monkeypatch.setattr(api, 'research_saas_online', lambda *args: pytest.fail('Overseas SaaS research is not a shopping source'))
    def scripts(analysis, key, count, style, language, gender):
        assert analysis['source_content']['main_content'] == '가격 미확인'
        return [{'language': 'ko'}]
    monkeypatch.setattr(api, 'generate_scripts', scripts)
    response = asyncio.run(request('POST', '/api/saasshorts/analyze', json={'url': 'https://example.com', 'language': 'ko'}))
    assert response.status_code == 200 and response.json()['web_research'] is None


@pytest.mark.parametrize('voice_id,voices', [(None, []), ('rachel', []), ('rachel', [{'voice_id': 'rachel', 'supports_korean': False}])])
def test_korean_generate_fails_before_paid_work_without_verified_voice(monkeypatch, voice_id, voices):
    monkeypatch.setattr(api, 'get_elevenlabs_voices', lambda key: voices)
    body = {'tts_provider': 'elevenlabs', 'script': {'language': 'ko'}, 'voice_id': voice_id}
    response = asyncio.run(request('POST', '/api/saasshorts/generate', json=body,
                                  headers={'X-Fal-Key': 'mock', 'X-ElevenLabs-Key': 'mock'}))
    assert response.status_code == 400 and '한국어' in response.json()['detail']


def test_generate_retains_key_checks():
    response = asyncio.run(request('POST', '/api/saasshorts/generate', json={'tts_provider': 'elevenlabs', 'script': {'language': 'ko'}}))
    assert response.status_code == 400 and 'X-Fal-Key' in response.json()['detail']


@pytest.mark.parametrize('language,voice_id', [('ko', 'korean'), ('en', None), ('es', None)])
def test_generate_passes_locale_and_voice_to_existing_pipeline(monkeypatch, tmp_path, language, voice_id):
    captured = []
    monkeypatch.setattr(api, 'OUTPUT_DIR', str(tmp_path))
    monkeypatch.setattr(api, 'saas_jobs', {})
    monkeypatch.setattr(api, 'get_elevenlabs_voices', lambda key: [{'voice_id': 'korean', 'supports_korean': True}])
    def pipeline(script, config, output, log):
        captured.append((script, config))
        return {'video_filename': 'mock.mp4'}
    monkeypatch.setattr(api, 'generate_full_video', pipeline)
    async def run():
        monkeypatch.setattr(api, 'concurrency_semaphore', asyncio.Semaphore(1))
        response = await request('POST', '/api/saasshorts/generate', json={'tts_provider': 'elevenlabs', 'script': {'language': language}, 'voice_id': voice_id},
                                 headers={'X-Fal-Key': 'mock', 'X-ElevenLabs-Key': 'mock'})
        assert response.status_code == 200, response.text
        # Await the actual existing background task; do not call external engines.
        tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task() and 'run_generation' in task.get_coro().__qualname__]
        await asyncio.gather(*tasks)
    asyncio.run(run())
    assert captured[0][0]['language'] == language
    assert captured[0][1]['voice_id'] == (voice_id or '21m00Tcm4TlvDq8ikWAM')


def test_korean_tts_keeps_multilingual_model(monkeypatch, tmp_path):
    captured = []
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            captured.append((url, kwargs['json']))
            return httpx.Response(200, content=b'mock-mp3')
    monkeypatch.setattr(saas.httpx, 'Client', Client)
    saas.generate_voiceover('상품 정보를 확인해 주세요', 'mock', str(tmp_path / 'voice.mp3'), 'korean')
    assert captured[0][0].endswith('/korean')
    assert captured[0][1]['model_id'] == 'eleven_multilingual_v2'
    assert captured[0][1]['text'] == '상품 정보를 확인해 주세요'


@pytest.mark.parametrize('mode', ['lowcost', 'premium'])
def test_korean_existing_pipeline_carries_audio_to_lipsync_and_subtitles(monkeypatch, tmp_path, mode):
    from pathlib import Path
    calls = []
    def asset(*args):
        path = args[-1]; Path(path).write_bytes(b'mock-asset'); return path
    def voice(text, key, output, voice_id):
        assert text == '확인된 상품 정보입니다' and voice_id == 'korean'
        Path(output).write_bytes(b'mock-audio'); return output
    def head(image, audio, key, output):
        assert Path(audio).read_bytes() == b'mock-audio'
        calls.append(mode)
        return asset(image, audio, key, output)
    def composite(head, broll, subs, hook, output):
        captions = Path(subs).read_text(encoding='utf-8')
        assert 'Noto Sans CJK KR' in captions and '상품' in captions
        Path(output).write_bytes(b'mock-video'); return output
    monkeypatch.setattr(saas, 'generate_actor_image', asset)
    monkeypatch.setattr(saas, 'generate_voiceover', voice)
    monkeypatch.setattr(saas, 'generate_talking_head_lowcost', head)
    monkeypatch.setattr(saas, 'generate_talking_head', head)
    monkeypatch.setattr(saas, 'transcribe_audio_for_subs', lambda path, **kwargs: (
        calls.append(kwargs['language']) or [{'word': '상품', 'start': .1, 'end': .8}]))
    monkeypatch.setattr(saas, 'composite_video', composite)
    monkeypatch.setattr(saas, 'mark_ai_generated', lambda *args: None)
    monkeypatch.setattr(saas, '_get_media_duration', lambda path: 1.)
    result = saas.generate_full_video({'language': 'ko', 'title': '상품', 'full_narration': '확인된 상품 정보입니다'},
                                    {'fal_key': 'mock', 'elevenlabs_key': 'mock', 'voice_id': 'korean', 'video_mode': mode},
                                    str(tmp_path), log=lambda text: None)
    assert Path(result['video_path']).read_bytes() == b'mock-video'
    assert calls == [mode, 'ko']


def test_korean_whisper_failure_releases_model(monkeypatch):
    import transcribe_backends as backend
    released = []
    def fail(*args, **kwargs): raise RuntimeError('mock ASR failure')
    monkeypatch.setattr(backend, 'run_whisper_transcription', fail)
    monkeypatch.setattr(backend, 'release_models', lambda: released.append(True))
    with pytest.raises(RuntimeError, match='mock ASR failure'):
        saas.transcribe_audio_for_subs('mock.mp3', 'ko')
    assert released == [True]


def test_korean_voice_service_error_is_explicit(monkeypatch):
    def fail(key): raise httpx.ConnectError('mock unavailable')
    monkeypatch.setattr(api, 'get_elevenlabs_voices', fail)
    response = asyncio.run(request('POST', '/api/saasshorts/generate', json={'tts_provider': 'elevenlabs', 'script': {'language': 'ko'}, 'voice_id': 'korean'},
                                  headers={'X-Fal-Key': 'mock', 'X-ElevenLabs-Key': 'mock'}))
    assert response.status_code == 503 and '확인하지 못했습니다' in response.json()['detail']
