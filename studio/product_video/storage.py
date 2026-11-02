"""Private approved assets and a small durable paid-request ledger (not a project library)."""
import hashlib
import json
import math
import shutil
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

from fastapi import HTTPException

MAX_BYTES = 100 * 1024 * 1024
TTL = 24 * 3600


def valid_id(value):
    try:
        if str(uuid.UUID(str(value))) != value: raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Invalid asset/request ID') from None
    return value


def root(engine):
    path = Path(engine.UPLOAD_DIR) / 'product_studio'
    path.mkdir(parents=True, exist_ok=True)
    return path


def probe(path):
    try:
        data = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,matroska,webm,mp3,wav,ogg,aac,flac', '-show_streams', '-show_format', '-of', 'json', str(path)],
            check=True, capture_output=True, timeout=30).stdout)
        streams = data.get('streams', [])
        duration = float(data.get('format', {}).get('duration') or 0)
        if not math.isfinite(duration): raise ValueError()
        return streams, duration
    except (ValueError, OSError, subprocess.SubprocessError):
        raise HTTPException(422, '파일을 해석할 수 없습니다. 지원되는 영상·사진·음원 파일을 사용하세요.') from None


async def upload(engine, file, kind, owner, approved):
    if not approved: raise HTTPException(400, '원본·음원 이용 권리를 먼저 확인하세요.')
    clean_expired(engine)
    if sum(p.stat().st_size for p in root(engine).rglob('*') if p.is_file()) > 2 * 1024**3:
        raise HTTPException(413, '제품 작업 파일이 2 GB를 초과했습니다. 만료 파일 정리 또는 관리자 확인이 필요합니다.')
    ident = str(uuid.uuid4()); directory = root(engine) / ident; directory.mkdir()
    path = directory / 'source'
    try:
        count = 0
        with path.open('wb') as target:
            while chunk := await file.read(1024 * 1024):
                count += len(chunk)
                if count > MAX_BYTES: raise HTTPException(413, '파일당 최대 100 MB입니다.')
                target.write(chunk)
        if not count: raise HTTPException(422, '빈 파일입니다.')
        if kind == 'image':
            from PIL import Image
            try:
                with Image.open(path) as image:
                    if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width * image.height > 24_000_000:
                        raise ValueError()
                    image.verify()
            except Exception:
                raise HTTPException(422, '24 MP 이하 PNG/JPEG/WebP 사진을 사용하세요.') from None
            duration = 0
        else:
            streams, duration = await __import__('asyncio').to_thread(probe, path)
            expected = 'audio' if kind == 'music' else 'video'
            if not any(s.get('codec_type') == expected for s in streams) or not 0 < duration <= 600:
                raise HTTPException(422, '10분 이하의 올바른 영상·음원을 사용하세요.')
            if kind == 'video' and any(int(s.get('width', 0)) * int(s.get('height', 0)) > 8_500_000 for s in streams):
                raise HTTPException(422, '4K 이하 영상을 사용하세요.')
        info = {'id': ident, 'kind': kind, 'duration': duration, 'approved': True,
                'user_id': str(owner) if owner else None, 'media_type': file.content_type if file.content_type and file.content_type.startswith(('image/', 'video/', 'audio/')) else 'application/octet-stream', 'created_at': time.time()}
        (directory / 'meta.json').write_text(json.dumps(info), encoding='utf-8')
        return {k: v for k, v in info.items() if k != 'user_id'}
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise


async def asset(engine, request, ident):
    directory = root(engine) / valid_id(ident)
    try: info = json.loads((directory / 'meta.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): raise HTTPException(404, '원본 파일을 찾을 수 없습니다.') from None
    await engine._assert_job_owner(request, info)
    if time.time() - info['created_at'] > TTL or not (directory / 'source').is_file():
        raise HTTPException(410, '원본 보관 기간이 만료됐습니다. 다시 업로드하세요.')
    return {**info, 'path': str(directory / 'source')}


def connection(engine):
    db = sqlite3.connect(root(engine) / '.requests.sqlite3', timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, owner TEXT, fingerprint TEXT, state TEXT, response TEXT, created REAL)')
    return db


def claim(engine, ident, owner, body):
    valid_id(ident)
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with connection(engine) as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT * FROM requests WHERE id=?', (ident,)).fetchone()
        if existing:
            if existing['owner'] != (str(owner) if owner else ''): raise HTTPException(404, 'Not found')
            if existing['fingerprint'] != fingerprint: raise HTTPException(409, '요청 ID를 다른 내용으로 재사용할 수 없습니다.')
            return False
        db.execute('INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?)', (ident, str(owner) if owner else '', fingerprint, 'queued', '{}', time.time()))
    return True


def update(engine, ident, state, response):
    with connection(engine) as db:
        db.execute('UPDATE requests SET state=?, response=? WHERE id=?', (state, json.dumps(response, ensure_ascii=False), ident))


async def read(engine, request, ident):
    with connection(engine) as db:
        row = db.execute('SELECT * FROM requests WHERE id=?', (valid_id(ident),)).fetchone()
    if not row: raise HTTPException(404, 'Not found')
    await engine._assert_job_owner(request, {'user_id': row['owner'] or None})
    if time.time() - row['created'] > TTL:
        update(engine, ident, 'expired', {})
        return {'request_id': ident, 'state': 'expired', 'error': '작업 보관 기간이 만료됐습니다. 기존 요청 ID로 유료 작업을 다시 실행하지 않습니다.'}
    return {'request_id': ident, 'state': row['state'], **json.loads(row['response'])}


def clean_expired(engine):
    # Opportunistic 24-hour working-file cleanup, never a paid-request replay.
    with connection(engine) as db:
        db.execute("UPDATE requests SET state='expired', response='{}' WHERE created<?", (time.time() - TTL,))
    for directory in root(engine).iterdir():
        if not directory.is_dir(): continue
        name = directory.name.removeprefix('job_')
        try: valid_id(name)
        except HTTPException: continue
        if time.time() - directory.stat().st_mtime > TTL:
            shutil.rmtree(directory, ignore_errors=True)


def purge_user(engine, user_id):
    """Reuse the existing account-erasure hook without changing cloud/ code."""
    base = Path(engine.UPLOAD_DIR) / 'product_studio'
    if not base.is_dir(): return 0
    removed = 0
    with connection(engine) as db:
        rows = db.execute('SELECT id FROM requests WHERE owner=?', (str(user_id),)).fetchall()
        for row in rows:
            shutil.rmtree(base / ('job_' + row['id']), ignore_errors=True); removed += 1
        db.execute("UPDATE requests SET owner='deleted', state='expired', response='{}' WHERE owner=?", (str(user_id),))
    for directory in base.iterdir():
        if not directory.is_dir(): continue
        try: info = json.loads((directory / 'meta.json').read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        if str(info.get('user_id')) == str(user_id):
            shutil.rmtree(directory, ignore_errors=True); removed += 1
    return removed
