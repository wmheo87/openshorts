"""Private, bounded product URL analysis and explicitly approved media import."""
import asyncio
import hashlib
import io
import json
import time
import uuid
from collections import defaultdict, deque
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from PIL import Image
from starlette.datastructures import Headers

from . import product_page, public_fetch, storage


class AnalyzeURL(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(min_length=1, max_length=4096)


class ImportURL(BaseModel):
    model_config = ConfigDict(extra='forbid')
    analysis_id: str
    candidate_ids: list[Annotated[str, Field(pattern=r'^\d{1,2}$')]] = Field(min_length=1, max_length=10)
    rights_confirmed: StrictBool = False


def load_analysis(engine, ident):
    directory = storage.root(engine) / storage.valid_id(ident)
    try:
        record = json.loads((directory / 'meta.json').read_text(encoding='utf-8'))
        if record.get('record_type') != 'product-url':
            raise ValueError()
    except (OSError, ValueError):
        raise HTTPException(404, '상품 분석 결과를 찾을 수 없습니다.') from None
    return record


def media_kind(response):
    data, mime = response.data, response.mime
    images = {'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WEBP'}
    if mime in images:
        try:
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
                if image.format != images[mime] or min(width, height) < 300 or width * height > 24_000_000 or max(width/height, height/width) > 4:
                    raise ValueError()
                image.verify()
            return 'image', {'width': width, 'height': height}
        except Exception:
            raise public_fetch.CollectionError('300px 이상·24 MP 이하의 PNG/JPEG/WebP 제품 이미지만 가져올 수 있습니다.') from None
    if mime in ('video/mp4', 'video/quicktime') and len(data) >= 12 and data[4:8] == b'ftyp':
        return 'video', {}
    if mime == 'video/webm' and data.startswith(b'\x1a\x45\xdf\xa3'):
        return 'video', {}
    raise public_fetch.CollectionError('MIME과 실제 파일 형식이 일치하지 않거나 지원하지 않는 자료입니다.')


def import_table(engine):
    db = storage.connection(engine)
    db.execute('CREATE TABLE IF NOT EXISTS product_url_imports (analysis TEXT, candidate TEXT, state TEXT, asset TEXT, created REAL, PRIMARY KEY (analysis, candidate))')
    db.execute('DELETE FROM product_url_imports WHERE created<?', (time.time() - storage.TTL,))
    db.commit()
    return db


async def import_candidate(engine, request, record, candidate, owner):
    analysis = record['analysis_id']
    with import_table(engine) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM product_url_imports WHERE analysis=? AND candidate=?', (analysis, candidate['id'])).fetchone()
        if row and row['state'] == 'completed':
            asset = await storage.asset(engine, request, row['asset'])
            return {k: v for k, v in asset.items() if k not in ('path', 'user_id')}
        if row and row['state'] == 'processing':
            raise HTTPException(409, '이미 가져오는 중이거나 결과가 불명확합니다. 자동 중복 다운로드하지 않습니다.')
        db.execute('INSERT OR REPLACE INTO product_url_imports VALUES (?, ?, ?, NULL, ?)', (analysis, candidate['id'], 'processing', time.time()))
    try:
        response = await asyncio.to_thread(public_fetch.fetch, candidate['url'], max_bytes=storage.MAX_BYTES,
            allowed=('image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'video/webm', 'video/quicktime'),
            seconds=60, policy=public_fetch.check_robots)
        kind, dimensions = await asyncio.to_thread(media_kind, response)
        if kind != candidate['kind']:
            raise public_fetch.CollectionError('분석한 자료 타입과 실제 파일 타입이 다릅니다.')
        digest = hashlib.sha256(response.data).hexdigest()
        # Reuse a content-identical already imported asset from this analysis only.
        with import_table(engine) as db:
            previous = db.execute("SELECT asset FROM product_url_imports WHERE analysis=? AND state='completed'", (analysis,)).fetchall()
        for row in previous:
            prior = await storage.asset(engine, request, row['asset'])
            if prior.get('sha256') == digest:
                asset = {k: v for k, v in prior.items() if k not in ('path', 'user_id')}
                break
        else:
            file = UploadFile(file=io.BytesIO(response.data), filename='public-source', headers=Headers({'content-type': response.mime}))
            try:
                asset = await storage.upload(engine, file, kind, owner, True)
            finally:
                await file.close()
            provenance = {'source_url': response.url, 'product_url': record['source_url'], 'source_site': urlsplit(response.url).hostname,
                          'sha256': digest, 'rights_confirmed_at': time.time(), **dimensions}
            meta = storage.root(engine) / asset['id'] / 'meta.json'
            info = json.loads(meta.read_text(encoding='utf-8'))
            meta.write_text(json.dumps({**info, **provenance}, ensure_ascii=False), encoding='utf-8')
            asset.update(provenance)
        with import_table(engine) as db:
            db.execute("UPDATE product_url_imports SET state='completed', asset=? WHERE analysis=? AND candidate=?", (asset['id'], analysis, candidate['id']))
        return asset
    except BaseException:
        with import_table(engine) as db:
            db.execute("UPDATE product_url_imports SET state='failed' WHERE analysis=? AND candidate=?", (analysis, candidate['id']))
        raise


def create_router(engine):
    router = APIRouter(prefix='/url', tags=['product-url'])
    semaphore = asyncio.Semaphore(2)
    calls = defaultdict(deque)

    async def guard(request):
        await engine.require_managed_entitlement(request)
        owner = await engine._owner_id(request)
        key = str(owner) if owner else (request.client.host if request.client else 'local')
        now = time.monotonic()
        # Per-process admission budget, bounded independently from paid requests.
        for stale in list(calls):
            if not calls[stale] or now - calls[stale][-1] > 60:
                del calls[stale]
        if len(calls) >= 1000 and key not in calls:
            raise HTTPException(429, '상품 수집 요청이 많습니다. 잠시 후 직접 다시 시도하세요.')
        queue = calls[key]
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= 10:
            raise HTTPException(429, '상품 URL 요청은 분당 10회로 제한됩니다. 자동 재시도하지 않습니다.')
        queue.append(now)
        return owner

    @router.post('/analyze')
    async def analyze(body: AnalyzeURL, request: Request):
        owner = await guard(request)
        try:
            async with semaphore:
                data = await asyncio.to_thread(product_page.analyze, body.url)
            storage.clean_expired(engine)
            ident = str(uuid.uuid4())
            directory = storage.root(engine) / ident
            directory.mkdir()
            (directory / 'meta.json').write_text(json.dumps({**data, 'analysis_id': ident, 'record_type': 'product-url',
                'created_at': time.time(), 'user_id': str(owner) if owner else None}, ensure_ascii=False), encoding='utf-8')
            return {**data, 'analysis_id': ident}
        except public_fetch.CollectionError as exc:
            raise HTTPException(422, str(exc)) from None
        except (OSError, ValueError):
            raise HTTPException(503, '상품 분석 결과를 저장하거나 해석할 수 없습니다. 직접 업로드를 사용하세요.') from None

    @router.post('/import')
    async def import_media(body: ImportURL, request: Request):
        owner = await guard(request)
        if not body.rights_confirmed:
            raise HTTPException(400, '선택한 각 자료의 사용·편집 권리를 확인한 후 가져오세요.')
        record = load_analysis(engine, body.analysis_id)
        await engine._assert_job_owner(request, record)
        if time.time() - record['created_at'] > storage.TTL:
            raise HTTPException(410, '상품 분석이 만료됐습니다. 다시 분석하세요.')
        candidates = {item['id']: item for item in record['candidates']}
        ids = list(dict.fromkeys(body.candidate_ids))
        if any(ident not in candidates for ident in ids):
            raise HTTPException(422, '분석 결과에 없는 자료입니다. 다시 분석하세요.')
        assets, errors, seen, imported = [], [], set(), []
        async with semaphore:
            for ident in ids:
                try:
                    asset = await import_candidate(engine, request, record, candidates[ident], owner)
                    imported.append(ident)
                    if asset['id'] not in seen:
                        assets.append({**asset, 'candidate_id': ident})
                        seen.add(asset['id'])
                except (public_fetch.CollectionError, HTTPException) as exc:
                    errors.append({'candidate_id': ident, 'message': str(exc.detail) if isinstance(exc, HTTPException) else str(exc)})
        return {'assets': assets, 'errors': errors, 'imported_candidate_ids': imported}

    return router
