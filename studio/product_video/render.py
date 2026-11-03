"""Local FFmpeg-only composition of approved footage; no generated product scenes."""
import json
import math
import shutil
from importlib.util import find_spec
import subprocess
from pathlib import Path
from studio.gemini_tts import generate_voiceover
from saasshorts import generate_tiktok_subs
from .storage import probe
from .captions import style_product_captions


def run(args, cwd=None):
    try:
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-protocol_whitelist', 'file,pipe', *args],
                       check=True, capture_output=True, timeout=600, cwd=cwd)
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError('FFmpeg 합성에 실패했습니다. 원본 형식·디스크·폰트를 확인하세요. 유료 API를 다시 호출하지 않습니다.') from None


class LocalRuntimeError(RuntimeError):
    pass


def ensure_runtime():
    # Avoid buying TTS before discovering a missing local renderer/ASR install.
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise LocalRuntimeError('FFmpeg/ffprobe가 설치되지 않았습니다. 유료 음성을 생성하지 않았습니다.')
    if find_spec('faster_whisper') is None:
        raise LocalRuntimeError('한국어 Whisper 의존성 faster-whisper를 설치하세요. 유료 음성을 생성하지 않았습니다.')


def render_product(script, config, output_dir, log):
    ensure_runtime()
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    scenes = config['scenes']
    log('한국어 Gemini TTS 생성 중 · fal.ai 호출 없음')
    audio = generate_voiceover(script['full_narration'], config['gemini_key'], str(out / 'voice.mp3'),
                               config.get('voice', 'Kore'), config['model'])
    _, duration = probe(audio)
    if not math.isfinite(duration) or not 0 < duration <= 120:
        raise ValueError('음성이 120초를 초과하거나 비어 있습니다. 짧은 대본으로 새 요청을 준비하세요.')
    log('실제 음성에서 Whisper 타임스탬프·ASS 자막 생성 중')
    generate_tiktok_subs(audio, str(out / 'captions.ass'), max_words=2, language='ko')
    if not (out / 'captions.ass').stat().st_size: raise ValueError('음성 인식 자막이 비어 있습니다. 완료로 처리하지 않습니다.')
    style_product_captions(out / 'captions.ass', config.get('subtitle_position', 'bottom'),
                           config.get('subtitle_style', 'outline'))
    width, height = 720, 1280
    # Approximate scene timing from each scene's own spoken text, not arbitrary photo duration.
    # This does not provide word-exact alignment; future work can derive cuts from ASR timings.
    segment_scripts = script.get('segments') or []
    if len(segment_scripts) != len(scenes) or any(s.get('asset_id') != scene['asset_id'] or not isinstance(s.get('narration'), str) or not s['narration'].strip() for s, scene in zip(segment_scripts, scenes)):
        raise ValueError('장면별 대본이 원본 장면과 일치하지 않습니다.')
    weights = [max(1, len(s['narration'].strip())) for s in segment_scripts]
    total = sum(weights)
    for i, (scene, weight) in enumerate(zip(scenes, weights)):
        seconds = duration * weight / total
        log(f'승인 원본 장면 {i + 1}/{len(scenes)} · 크롭/사진 움직임/전환 합성')
        crop_x = {'center': '(in_w-out_w)/2', 'left': '0', 'right': 'in_w-out_w'}[scene['crop']]
        if scene.get('fit', 'contain') == 'contain':
            vf = f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30'
        else:
            vf = f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}:{crop_x}:(in_h-out_h)/2,setsar=1,fps=30'
        if scene['kind'] == 'image':
            frames = max(1, math.ceil(seconds * 30))
            if scene['motion'] == 'zoom':
                vf += f",zoompan=z='min(1+on*0.0005,1.08)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s={width}x{height}:fps=30"
            elif scene['motion'] == 'pan':
                vf += f",zoompan=z=1.08:x='(iw-iw/zoom)*on/{frames}':y='ih/2-ih/zoom/2':d={frames}:s={width}x{height}:fps=30"
            inputs = ['-loop', '1', '-i', scene['path']]
        else:
            inputs = ['-ss', str(scene['start']), '-t', str(scene['end'] - scene['start']), '-i', scene['path']]
            # Hold the final authorized frame if narration is longer; no fabricated action.
            vf += f',tpad=stop_mode=clone:stop_duration={seconds}'
        if config['transition'] == 'fade':
            fade = min(.15, seconds / 3)
            vf += f',fade=t=in:d={fade},fade=t=out:st={max(0, seconds-fade)}:d={fade}'
        run([*inputs, '-vf', vf, '-an', '-t', str(seconds), '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-threads', '2', str(out / f'scene{i}.mp4')])
    (out / 'concat.txt').write_text(''.join(f"file 'scene{i}.mp4'\n" for i in range(len(scenes))), encoding='utf-8')
    run(['-f', 'concat', '-safe', '1', '-i', 'concat.txt', '-c', 'copy', 'joined.mp4'], cwd=out)
    inputs = ['-i', 'joined.mp4', '-i', 'voice.mp3']
    if config.get('music'):
        inputs += ['-stream_loop', '-1', '-i', config['music']['path']]
        audio_filter = f"[2:a]volume={config['music_volume']}[bg];[1:a][bg]amix=inputs=2:duration=first:normalize=0[a]"
        mapping = ['-filter_complex', audio_filter, '-map', '0:v', '-map', '[a]']
    else:
        mapping = ['-map', '0:v', '-map', '1:a']
    log('9:16 MP4·한국어 ASS·선택한 배경음 최종 합성')
    # Relative controlled names avoid Windows drive/filter quoting issues.
    run([*inputs, *mapping, '-vf', 'ass=captions.ass', '-t', str(duration), '-c:v', 'libx264', '-preset', 'veryfast',
         '-threads', '2', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', 'product.mp4'], cwd=out)
    streams, actual = probe(out / 'product.mp4')
    if not any(s.get('width') == width and s.get('height') == height for s in streams) or actual <= 0:
        raise ValueError('출력 영상 검증 실패')
    return {'filename': 'product.mp4', 'duration': actual, 'cost': {'fal_usd': 0, 'gemini_tts_usd': None,
            'note': 'fal.ai 호출 없음. Gemini 및 로컬 컴퓨팅 비용은 별도이며 실제 요금 미확인.'}}
