"""Independent private product endpoints; reuse app auth and worker concurrency."""
import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from studio import gemini_tts
from . import storage
from .providers import PROVIDERS, provider_catalog
from .scripts import generate_product_script
from .render import LocalRuntimeError


class Scene(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    asset_id: str
    start: float = Field(default=0, ge=0, le=600)
    end: float = Field(default=1, gt=0, le=600)
    duration: float = Field(default=3, ge=1, le=15)
    crop: Literal['center', 'left', 'right'] = 'center'
    fit: Literal['contain', 'cover'] = 'contain'
    motion: Literal['none', 'zoom', 'pan'] = 'zoom'
    note: str = Field(default='', max_length=400)


class ProductRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    request_id: str
    scenes: list[Scene] = Field(min_length=1, max_length=10)
    description: str = Field(default='', max_length=4000)
    rights_confirmed: StrictBool = False
    paid_confirmed: StrictBool = False
    content_confirmed: StrictBool = False
    script: dict | None = None
    voice: Literal['Kore', 'Puck', 'Zephyr', 'Charon', 'Leda', 'Aoede', 'Achird', 'Sulafat', 'Laomedeia', 'Schedar', 'Iapetus', 'Callirrhoe', 'Vindemiatrix', 'Autonoe', 'Orus', 'Fenrir', 'Enceladus', 'Umbriel', 'Algieba', 'Despina', 'Erinome', 'Algenib', 'Rasalgethi', 'Achernar', 'Alnilam', 'Gacrux', 'Pulcherrima', 'Zubenelgenubi', 'Sadachbia', 'Sadaltager'] = 'Kore'
    music_id: str | None = None
    music_volume: float = Field(default=.12, ge=0, le=.4)
    transition: Literal['cut', 'fade'] = 'fade'
    subtitle_position: Literal['top', 'center', 'bottom'] = 'bottom'
    subtitle_style: Literal['outline', 'highlight', 'box'] = 'outline'


def create_router(engine):
    router = APIRouter(prefix='/api/saasshorts/product', tags=['product-video'])
    tasks = set()
    active = set()  # Only this process's tasks; after restart never replay paid work.

    async def prepare(request, body, generating):
        await engine.require_managed_entitlement(request)
        if not body.rights_confirmed or not body.paid_confirmed or (generating and not body.content_confirmed):
            raise HTTPException(400, '원본 권리·유료 요청 비용·게시 내용 확인이 필요합니다.')
        scenes = []
        for selection in body.scenes:
            info = await storage.asset(engine, request, selection.asset_id)
            if info['kind'] == 'music': raise HTTPException(422, '음원을 영상 장면으로 사용할 수 없습니다.')
            if info['kind'] == 'video' and not 0 <= selection.start < selection.end <= info['duration']:
                raise HTTPException(422, '선택 영상 구간이 원본 길이를 벗어났습니다.')
            scenes.append({**selection.model_dump(), 'kind': info['kind'], 'path': info['path']})
        music = await storage.asset(engine, request, body.music_id) if body.music_id else None
        if music and music['kind'] != 'music': raise HTTPException(422, '배경음에는 승인된 음원만 선택하세요.')
        key = engine.saas_gemini_tts_key(request)
        if not key: raise HTTPException(400, 'Gemini 사용자 API 키가 필요합니다. fal.ai/ElevenLabs 키는 필요하지 않습니다.')
        if generating:
            if not body.script or body.script.get('production_mode') != 'product' or body.script.get('language') != 'ko':
                raise HTTPException(422, '제품 영상형 한국어 대본을 확인하세요.')
            narration = body.script.get('full_narration')
            if not isinstance(narration, str) or not 1 <= len(narration) <= 1200:
                raise HTTPException(422, '내레이션은 1~1200자로 제한됩니다.')
            if not isinstance(body.script.get('segments'), list) or any(not isinstance(s, dict) or not isinstance(s.get('narration'), str) or not s['narration'].strip() for s in body.script['segments']) or [s.get('asset_id') for s in body.script['segments']] != [s['asset_id'] for s in scenes]:
                raise HTTPException(422, '대본과 선택 장면이 다릅니다. 새 대본 요청을 준비하세요.')
        return scenes, music, key

    def output_available(ident):
        path = storage.root(engine) / ('job_' + ident) / 'product.mp4'
        try: return path.is_file() and path.stat().st_size > 0
        except OSError: return False

    @router.get('/providers')
    async def providers():
        return {'providers': provider_catalog(), 'default': 'ffmpeg-product', 'tts_model': gemini_tts.model_name(), 'cost_notice': 'Gemini 대본/TTS 요금 미확인(0원 보장 아님). 제품형 fal.ai 비용 0, 로컬 컴퓨팅 비용 별도.'}

    @router.post('/assets')
    async def upload(request: Request, file: UploadFile = File(...), kind: Literal['video', 'image', 'music'] = Form(...), rights_confirmed: bool = Form(False)):
        await engine.require_managed_entitlement(request)
        owner = await engine._owner_id(request)
        return await storage.upload(engine, file, kind, owner, rights_confirmed)

    @router.get('/assets/{ident}')
    async def preview(ident: str, request: Request):
        info = await storage.asset(engine, request, ident)
        mime = info.get('media_type', 'application/octet-stream')
        # A private authenticated blob fetch; no source is published under /videos.
        return FileResponse(info['path'], media_type=mime)

    @router.post('/{action}')
    async def submit(action: Literal['analyze', 'generate'], body: ProductRequest, request: Request):
        scenes, music, key = await prepare(request, body, action == 'generate')
        owner = await engine._owner_id(request)
        fresh = storage.claim(engine, body.request_id, owner, {'action': action, **body.model_dump()})
        if not fresh: return await storage.read(engine, request, body.request_id)
        active.add(body.request_id)
        config = {'gemini_key': key, 'scenes': scenes, 'music': music, 'music_volume': body.music_volume,
                  'transition': body.transition, 'voice': body.voice, 'model': gemini_tts.model_name(),
                  'subtitle_position': body.subtitle_position, 'subtitle_style': body.subtitle_style}
        async def work():
            logs = []
            def log(message):
                logs.append(message)
                storage.update(engine, body.request_id, 'processing', {'logs': list(logs)})
            try:
                async with engine.concurrency_semaphore:
                    log('요청 접수 · 승인 원본 확인 완료 · 유료 API 자동 재시도 없음')
                    if action == 'analyze':
                        script = await asyncio.to_thread(generate_product_script, body.description, scenes, 'ko', key)
                        storage.update(engine, body.request_id, 'completed', {'script': script, 'logs': logs})
                    else:
                        # Availability check is not proof of AUDIO support; fail closed if unavailable.
                        await asyncio.to_thread(gemini_tts.verify_model, key, config['model'])
                        folder = storage.root(engine) / ('job_' + body.request_id)
                        result = await asyncio.to_thread(PROVIDERS['ffmpeg-product'].render, body.script, config, str(folder), log)
                        (folder / 'source-manifest.json').write_text(json.dumps({'scenes': body.scenes and [s.model_dump() for s in body.scenes],
                            'music_id': body.music_id, 'rights_confirmed': True, 'content_confirmed': True, 'paid_confirmed': True, 'confirmed_at': time.time(), 'provider': 'ffmpeg-product', 'request_id': body.request_id}, ensure_ascii=False), encoding='utf-8')
                        storage.update(engine, body.request_id, 'completed', {'result': result, 'logs': logs})
            except Exception as exc:
                # Do not echo provider exception bodies/keys. A failed request is never replayed.
                storage.update(engine, body.request_id, 'failed', {'logs': logs, 'error': (str(exc) if isinstance(exc, (gemini_tts.GeminiTTSError, LocalRuntimeError)) else '') + ' 제작 요청에 실패했습니다. 모델/키/원본/Whisper/FFmpeg를 확인하세요. 이미 발생한 Gemini 비용은 청구될 수 있습니다. 자동 재시도·유료 공급자 전환은 하지 않습니다.'})
            finally: active.discard(body.request_id)
        task = asyncio.create_task(work()); tasks.add(task); task.add_done_callback(tasks.discard)
        return {'request_id': body.request_id, 'state': 'queued'}

    @router.get('/requests/{ident}')
    async def status(ident: str, request: Request):
        await engine.require_managed_entitlement(request)
        data = await storage.read(engine, request, ident)
        if data['state'] in ('processing', 'queued') and ident not in active:
            return {**data, 'state': 'interrupted', 'error': '작업이 중단되었거나 다른 프로세스에서 진행 중입니다. 자동 재실행하지 않습니다. 서버 상태를 확인하세요.'}
        if data.get('result') and not output_available(ident):
            return {**data, 'state': 'failed', 'result': None, 'error': '출력 파일이 만료되었거나 없습니다.'}
        return data

    @router.get('/download/{ident}')
    async def download(ident: str, request: Request):
        await engine.require_managed_entitlement(request)
        data = await storage.read(engine, request, ident)
        path = storage.root(engine) / ('job_' + ident) / 'product.mp4'
        if data['state'] != 'completed' or not data.get('result') or not output_available(ident):
            raise HTTPException(404, '완료된 MP4가 없거나 만료됐습니다.')
        return FileResponse(path, media_type='video/mp4', filename='product-short.mp4')

    return router
