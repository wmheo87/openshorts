import test from 'node:test';
import assert from 'node:assert/strict';
import { buildProductionData, clearPendingProduction, knownProductionRejection, productionError, readPendingProduction, rememberProduction } from '../src/features/discovery/production.js';

const video = { video_id: 'abcdefghijk', url: 'https://www.youtube.com/watch?v=abcdefghijk', title: 'Source', channel_title: 'Channel', license: 'creativeCommon', metadata_fetched_at: '2026-10-23T00:00:00Z' };

test('production requires separate rights and download permission, matching source ID and URL', () => {
  for (const [rights, download] of [[false, false], [true, false], [false, true]]) assert.throws(() => buildProductionData(video, {}, rights, download));
  assert.throws(() => buildProductionData({ ...video, url: 'https://evil.test/' }, {}, true, true));
  assert.throws(() => buildProductionData({ ...video, license: 'youtube' }, {}, true, true));
});

test('supported options and source snapshot map to the existing handleProcess contract', () => {
  const data = buildProductionData(video, { targetClips: '3', maxSeconds: '30', autoHook: '1' }, true, true);
  assert.equal(data.type, 'url'); assert.equal(data.payload, video.url); assert.equal(data.outputFormat, 'vertical');
  assert.equal(data.targetClips, 3); assert.equal(data.clipMinSeconds, 15); assert.equal(data.clipMaxSeconds, 30);
  assert.equal(data.autoHook, true); assert.equal(data.layout, 'auto');
  assert.deepEqual(data.discoverySource, { ...video, download_authorized: true });
});

test('unset controls preserve engine defaults and invalid options are rejected', () => {
  const data = buildProductionData(video, { targetClips: '', maxSeconds: '', autoHook: '' }, true, true);
  assert.equal(data.targetClips, null); assert.equal(data.clipMaxSeconds, null); assert.equal(data.autoHook, null);
  assert.throws(() => buildProductionData(video, { targetClips: '6' }, true, true));
  assert.throws(() => buildProductionData(video, { maxSeconds: '180' }, true, true));
});

test('uncertain submission marker survives reads without storing any API keys', () => {
  const previous = globalThis.sessionStorage;
  const storage = new Map();
  globalThis.sessionStorage = { setItem: (key, value) => storage.set(key, value), getItem: (key) => storage.get(key), removeItem: (key) => storage.delete(key) };
  try {
    rememberProduction(video);
    assert.deepEqual(readPendingProduction().source, video);
    assert.equal(JSON.stringify([...storage]).includes('api_key'), false);
    clearPendingProduction(); assert.equal(readPendingProduction(), null);
  } finally { globalThis.sessionStorage = previous; }
});

test('known pre-queue errors can be retried explicitly; unknown server outcomes stay locked', () => {
  assert.equal(knownProductionRejection('provider_timeout'), true);
  assert.equal(knownProductionRejection('unknown_error'), false);
  assert.match(productionError('{"detail":"Missing X-Gemini-Key header"}'), /로컬 LLM/);
  assert.match(productionError('{"detail":{"code":"source_license_changed"}}'), /라이선스/);
  assert.match(productionError('This video is only 20s long'), /길이/);
  assert.match(productionError('ffmpeg failed'), /FFmpeg/);
});
