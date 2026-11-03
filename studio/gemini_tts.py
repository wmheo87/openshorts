"""Optional Gemini TTS adapter. No paid-provider fallback or automatic synthesis retry."""
import os
import re
import subprocess
import wave
from pathlib import Path

DEFAULT_MODEL = 'gemini-3.8-flash-lite-tts'
VOICES = ('Kore', 'Puck', 'Zephyr', 'Charon', 'Leda', 'Aoede', 'Achird', 'Sulafat', 'Laomedeia', 'Schedar', 'Iapetus', 'Callirrhoe', 'Vindemiatrix', 'Autonoe', 'Orus', 'Fenrir', 'Enceladus', 'Umbriel', 'Algieba', 'Despina', 'Erinome', 'Algenib', 'Rasalgethi', 'Achernar', 'Alnilam', 'Gacrux', 'Pulcherrima', 'Zubenelgenubi', 'Sadachbia', 'Sadaltager')
COST_NOTICE = ('Gemini TTS 요금/무료 할당량은 미확인입니다(0원 보장 아님). '
               'fal.ai 영상·립싱크 요금은 별도이며, 실패한 요청도 과금될 수 있습니다. '
               '다른 유료 공급자로 자동 전환하지 않습니다.')


class GeminiTTSError(RuntimeError):
    pass


def model_name():
    return os.environ.get('GEMINI_TTS_MODEL', DEFAULT_MODEL)


def client_for(key):
    from google import genai
    from google.genai import types
    # One attempt: a timeout must not silently duplicate a potentially billed call.
    return genai.Client(api_key=key, vertexai=False, http_options=types.HttpOptions(
        timeout=120000, retry_options=types.HttpRetryOptions(attempts=1)))


def verify_model(key, model=None):
    model = model or model_name()
    if not key:
        raise GeminiTTSError('Gemini TTS용 사용자 API 키가 필요합니다. ' + COST_NOTICE)
    try:
        with client_for(key) as client:
            info = client.models.get(model=model)
        if 'generateContent' not in (info.supported_actions or []):
            raise ValueError('generateContent not supported')
    except Exception:
        # Provider messages can contain URLs/credentials; never echo them to the UI.
        raise GeminiTTSError(f'Gemini TTS 모델 {model}의 계정 이용 가능 여부를 확인하지 못했습니다. 모델명·권한·할당량을 확인하세요. ' + COST_NOTICE) from None
    return {'model': model, 'catalog_confirmed': True, 'audio_synthesis_verified': False,
            'estimated_tts_usd': None, 'cost_notice': COST_NOTICE, 'voices': list(VOICES)}


def generate_voiceover(text, key, output_path, voice='Kore', model=None):
    """Gemini inline PCM → WAV → MP3 for the unchanged fal.ai audio path."""
    from google.genai import types
    model = model or model_name()
    if voice not in VOICES:
        raise GeminiTTSError('지원하는 Gemini 음성을 선택하세요. ' + COST_NOTICE)
    verify_model(key, model)
    output = Path(output_path)
    wav_path = output.with_suffix('.wav')
    try:
        with client_for(key) as client:
            response = client.models.generate_content(
                model=model, contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=['AUDIO'],
                    speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
        candidates = response.candidates or []
        parts = candidates[0].content.parts if candidates and candidates[0].content else []
        audio = [part.inline_data for part in (parts or []) if part.inline_data and part.inline_data.data]
        if not audio or any(blob.mime_type != audio[0].mime_type for blob in audio):
            raise ValueError('No consistent inline audio')
        mime = audio[0].mime_type or ''
        data = b''.join(blob.data for blob in audio)
        if not data or len(data) > 32 * 1024 * 1024:
            raise ValueError('Empty or oversized audio')
        if mime.split(';')[0].lower() in ('audio/wav', 'audio/x-wav'):
            wav_path.write_bytes(data)
            with wave.open(str(wav_path), 'rb') as wav:
                if wav.getnframes() < 1:
                    raise ValueError('Empty WAV')
        else:
            rate = re.search(r'(?:^|;)\s*rate=(\d+)', mime)
            if mime.split(';')[0].lower() not in ('audio/l16', 'audio/pcm') or not rate or len(data) % 2:
                raise ValueError('Unsupported PCM metadata')
            sample_rate = int(rate.group(1))
            if not 8000 <= sample_rate <= 48000:
                raise ValueError('Unsupported sample rate')
            with wave.open(str(wav_path), 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate)
                wav.writeframes(data)
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                        '-i', str(wav_path), '-ac', '1', '-ar', '24000', '-codec:a', 'libmp3lame', str(output)],
                       check=True, capture_output=True, timeout=180)
        if not output.is_file() or not output.stat().st_size:
            raise ValueError('Empty MP3')
    except Exception:
        output.unlink(missing_ok=True)  # Never reuse an incomplete paid synthesis asset.
        raise GeminiTTSError('Gemini TTS 음성 생성 또는 WAV/MP3 변환에 실패했습니다. 자동 재시도하지 않습니다. ' + COST_NOTICE) from None
    return str(output)
