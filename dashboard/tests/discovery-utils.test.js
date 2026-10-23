import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { createServer as createViteServer } from 'vite';
import { buildSearchRequest, defaultFilters, filtersFromRequest, formatDuration, safeVideoUrl, sortVideos } from '../src/features/discovery/utils.js';
import { errorMessage } from '../src/features/discovery/strings.js';

test('P1 request uses the exact schema and numeric fields', () => {
  const request = buildSearchRequest({ ...defaultFilters, keyword: '  한국   요리  ', min_views: '1000' });
  assert.deepEqual(request, { keyword: '한국 요리', relevance_language: 'ko', min_views: 1000, min_duration_seconds: 1, max_duration_seconds: 86400, max_results: 20, published_after: null, published_before: null });
});

test('Korean, English and Japanese keywords remain searchable text', () => {
  for (const keyword of ['한국 요리', 'cooking', '日本料理']) assert.equal(buildSearchRequest({ ...defaultFilters, keyword }).keyword, keyword);
});

test('invalid keyword, integer, length, date and result bounds are rejected before HTTP', () => {
  for (const patch of [
    { keyword: '' }, { keyword: '\u0000' }, { keyword: 'x'.repeat(201) }, { min_views: '-1' }, { min_views: '1e3' },
    { min_views: '' }, { min_duration_seconds: '0' }, { max_duration_seconds: '86401' },
    { min_duration_seconds: '30', max_duration_seconds: '10' }, { max_results: '51' },
    { published_after: '2026-02-30' }, { published_after: '2026-10-24', published_before: '2026-10-23' },
  ]) assert.throws(() => buildSearchRequest({ ...defaultFilters, keyword: 'valid', ...patch }));
});

test('inclusive calendar dates use timezone-aware exclusive upper bounds (Seoul and DST)', () => {
  const script = `import {buildSearchRequest,defaultFilters} from './src/features/discovery/utils.js'; console.log(JSON.stringify(buildSearchRequest({...defaultFilters,keyword:'a',published_after:'2026-03-08',published_before:'2026-03-08'})))`;
  for (const [timezone, after, before] of [
    ['Asia/Seoul', '2026-03-07T15:00:00.000Z', '2026-03-08T15:00:00.000Z'],
    ['America/New_York', '2026-03-08T05:00:00.000Z', '2026-03-09T04:00:00.000Z'],
  ]) {
    const data = JSON.parse(execFileSync(process.execPath, ['--input-type=module', '-e', script], { env: { ...process.env, TZ: timezone }, encoding: 'utf8' }));
    assert.equal(data.published_after, after); assert.equal(data.published_before, before);
  }
});

test('sorting uses independent metrics, deterministic ties, and does not mutate results', () => {
  const videos = [
    { video_id: 'b', recommendation_score: 90, view_count: 10, published_at: '2026-01-01Z' },
    { video_id: 'a', recommendation_score: 40, view_count: 100, published_at: '2026-02-01Z' },
    { video_id: 'c', recommendation_score: 30, view_count: 20, published_at: '2026-03-01Z' },
  ];
  assert.deepEqual(sortVideos(videos, 'score').map((v) => v.video_id), ['b', 'a', 'c']);
  assert.deepEqual(sortVideos(videos, 'views').map((v) => v.video_id), ['a', 'c', 'b']);
  assert.deepEqual(sortVideos(videos, 'newest').map((v) => v.video_id), ['c', 'a', 'b']);
  assert.deepEqual(videos.map((v) => v.video_id), ['b', 'a', 'c']);
});

test('history filters, original links and duration formatting handle edge cases', () => {
  assert.equal(filtersFromRequest({ keyword: 'a', relevance_language: null }).relevance_language, '');
  assert.equal(formatDuration(3723), '1:02:03');
  for (const value of ['javascript:alert(1)', 'https://evil.test/', 'https://u:p@www.youtube.com/']) assert.equal(safeVideoUrl(value), null);
  assert.equal(safeVideoUrl('https://www.youtube.com/watch?v=abcdefghijk'), 'https://www.youtube.com/watch?v=abcdefghijk');
  assert.match(errorMessage('provider_not_configured', 503), /API 키/);
  assert.match(errorMessage(null, 422), /조건/);
});

test('Vite routes only /api/discovery to the optional standalone service', async () => {
  const seen = [];
  const mock = (name) => createServer((req, res) => { seen.push([name, req.url]); res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({ source: name })); });
  const backend = mock('backend'), discovery = mock('discovery');
  await Promise.all([new Promise((resolve) => backend.listen(0, '127.0.0.1', resolve)), new Promise((resolve) => discovery.listen(0, '127.0.0.1', resolve))]);
  const previous = { VITE_PROXY_TARGET: process.env.VITE_PROXY_TARGET, VITE_DISCOVERY_PROXY_TARGET: process.env.VITE_DISCOVERY_PROXY_TARGET };
  process.env.VITE_PROXY_TARGET = `http://127.0.0.1:${backend.address().port}`;
  process.env.VITE_DISCOVERY_PROXY_TARGET = `http://127.0.0.1:${discovery.address().port}`;
  let vite;
  try {
    vite = await createViteServer({ server: { host: '127.0.0.1', port: 0 }, mode: 'test' });
    await vite.listen();
    const base = `http://127.0.0.1:${vite.httpServer.address().port}`;
    assert.equal((await (await fetch(`${base}/api/discovery/history?limit=10`)).json()).source, 'discovery');
    assert.equal((await (await fetch(`${base}/api/config`)).json()).source, 'backend');
    assert.equal((await (await fetch(`${base}/api/status/test`)).json()).source, 'backend');
    assert.deepEqual(seen.map(([name]) => name), ['discovery', 'backend', 'backend']);
  } finally {
    await vite?.close();
    for (const server of [backend, discovery]) { server.closeAllConnections(); await new Promise((resolve) => server.close(resolve)); }
    for (const [key, value] of Object.entries(previous)) { if (value == null) delete process.env[key]; else process.env[key] = value; }
  }
});
