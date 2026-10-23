import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { mockApi, videos } from './fixtures';

const media = Buffer.from(readFileSync(new URL('./media/owned-preview.base64', import.meta.url), 'utf8').trim(), 'base64');
const clip = { video_url: '/videos/discovery-job/clip.mp4', video_title_for_youtube_short: '완성된 테스트 쇼츠', start: 1, end: 3, predicted_score: 85, why: 'Synthetic owned test fixture' };

async function setup(page, options = {}) {
  await page.addInitScript((keys) => {
    localStorage.setItem('os_social_nudge_dismissed', '1');
    if (keys) { localStorage.setItem('gemini_key', 'fixture-key'); localStorage.setItem('uploadPostKey_v3', 'fixture-post'); }
  }, !!options.keys);
  await mockApi(page);
  await page.route('**/embed/**', (route) => route.fulfill({ body: '<p>Source preview mock</p>', contentType: 'text/html' }));
  const submitted = [], polled = [];
  await page.route('**/api/process', async (route) => {
    const req = route.request();
    const body = req.headers()['content-type']?.includes('application/json') ? req.postDataJSON() : req.postData();
    submitted.push(body);
    if (options.process) return options.process(route, body, submitted.length);
    return route.fulfill({ json: { job_id: 'discovery-job', status: 'queued' } });
  });
  await page.route('**/api/status/*', (route) => {
    polled.push(route.request().url());
    if (options.status) return options.status(route, polled.length);
    return route.fulfill({ json: { status: 'processing', logs: ['AI analysis'], result: null } });
  });
  await page.route('**/videos/discovery-job/clip.mp4*', (route) => route.fulfill({ status: 200, body: media, contentType: 'video/mp4', headers: { 'Content-Length': String(media.length) } }));
  return { submitted, polled };
}

async function selectVideo(page) {
  await page.goto('/#app?tab=discovery');
  await page.getByLabel('검색어', { exact: true }).fill('한국 요리');
  await page.getByRole('button', { name: '영상 검색', exact: true }).click();
  await page.getByRole('button', { name: `${videos[0].title} 영상 선택`, exact: true }).click();
  return page.getByRole('region', { name: '선택한 영상 상세' });
}

async function confirm(detail) {
  await detail.getByRole('checkbox', { name: /원본과 이용 조건/ }).check();
  await detail.getByRole('checkbox', { name: /다운로드가 허용됨/ }).check();
}

test('rights and download permission are independent; exact source/options reach the existing engine', async ({ page }) => {
  const { submitted } = await setup(page);
  const detail = await selectVideo(page);
  const button = detail.getByRole('button', { name: '쇼츠 제작하기', exact: true });
  await expect(button).toBeDisabled();
  await detail.getByRole('checkbox', { name: /원본과 이용 조건/ }).check();
  await expect(button).toBeDisabled();
  expect(submitted).toHaveLength(0);
  await detail.getByRole('checkbox', { name: /다운로드가 허용됨/ }).check();
  await detail.getByLabel('목표 쇼츠 수').selectOption('3');
  await detail.getByLabel('클립 길이').selectOption('30');
  await detail.getByLabel('AI 후킹 문구').selectOption('1');
  await button.click();
  await expect(page.getByRole('region', { name: '탐색 영상 제작 정보' })).toBeVisible();
  expect(submitted).toHaveLength(1);
  expect(submitted[0]).toMatchObject({ url: videos[0].url, acknowledged: true, output_format: 'vertical', target_clips: 3,
    clip_min_seconds: 15, clip_max_seconds: 30, auto_hook: '1', layouts: ['auto'], force_low_quality: false,
    discovery_source: { video_id: videos[0].video_id, url: videos[0].url, title: videos[0].title, channel_title: videos[0].channel_title, license: 'creativeCommon', metadata_fetched_at: videos[0].metadata_fetched_at, download_authorized: true } });
});

test('unset generation controls preserve defaults, and a rapid double activation sends one request', async ({ page }) => {
  let release;
  const blocked = new Promise((resolve) => { release = resolve; });
  const { submitted } = await setup(page, { process: async (route) => { await blocked; return route.fulfill({ json: { job_id: 'discovery-job' } }); } });
  const detail = await selectVideo(page); await confirm(detail);
  await detail.getByRole('button', { name: '쇼츠 제작하기', exact: true }).evaluate((button) => { button.click(); button.click(); });
  await expect(page.getByText('요청 접수 중 · 작업 ID 응답 대기')).toBeVisible();
  expect(submitted).toHaveLength(1);
  expect(submitted[0]).not.toHaveProperty('target_clips');
  expect(submitted[0]).not.toHaveProperty('clip_min_seconds');
  expect(submitted[0]).not.toHaveProperty('auto_hook');
  release();
  await expect(page.getByText(/작업 discovery-job/)).toBeVisible();
});

for (const [status, detail, message] of [
  [400, 'Missing X-Gemini-Key header', '제작용 Gemini 키 또는 로컬 LLM'],
  [403, 'YouTube URL ingest is disabled on this deployment.', 'YouTube URL 처리를 허용하지 않습니다'],
  [400, 'This video is only 20s long', '원본 영상 길이'],
  [409, { code: 'source_license_changed' }, '원본 라이선스가 변경'],
  [409, { code: 'source_unavailable' }, '원본이 삭제·비공개'],
  [503, { code: 'provider_not_configured' }, 'YouTube API 키가 설정되지 않았습니다'],
  [429, { code: 'local_quota_exceeded' }, '일별 API 호출 예산'],
]) test(`rejects ${status}/${JSON.stringify(detail)} without automatic resubmission`, async ({ page }) => {
  const { submitted } = await setup(page, { process: (route) => route.fulfill({ status, json: { detail } }) });
  const panel = await selectVideo(page); await confirm(panel);
  await panel.getByRole('button', { name: '쇼츠 제작하기', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: message }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: '명시적으로 다시 시도' })).toBeVisible();
  expect(submitted).toHaveLength(1);
});

test('quality gate only forces low resolution after explicit confirmation', async ({ page }) => {
  const { submitted } = await setup(page, { process: (route, body) => route.fulfill({ json: body.force_low_quality
    ? { job_id: 'discovery-job' } : { needs_confirmation: true, quality_check: { max_height: 360, min_height: 720 } } }) });
  const panel = await selectVideo(page); await confirm(panel);
  await panel.getByRole('button', { name: '쇼츠 제작하기', exact: true }).click();
  await expect(page.getByText(/YouTube only offers/)).toBeVisible();
  expect(submitted).toHaveLength(1); expect(submitted[0].force_low_quality).toBe(false);
  await page.getByRole('button', { name: 'process anyway', exact: true }).click();
  await expect(page.getByText(/작업 discovery-job/)).toBeVisible();
  expect(submitted).toHaveLength(2); expect(submitted[1].force_low_quality).toBe(true);
});

test('a rejected request is only retried by an explicit user action', async ({ page }) => {
  const { submitted } = await setup(page, { process: (route, body, count) => route.fulfill(count === 1
    ? { status: 400, json: { detail: 'Missing X-Gemini-Key header' } } : { json: { job_id: 'discovery-job' } }) });
  const panel = await selectVideo(page); await confirm(panel);
  await panel.getByRole('button', { name: '쇼츠 제작하기', exact: true }).click();
  await expect(page.getByRole('button', { name: '명시적으로 다시 시도' })).toBeVisible();
  expect(submitted).toHaveLength(1);
  await page.getByRole('button', { name: '명시적으로 다시 시도' }).click();
  await expect(page.getByText(/작업 discovery-job/)).toBeVisible();
  expect(submitted).toHaveLength(2);
});

test('submission timeout locks an unknown outcome instead of automatically retrying', async ({ page }) => {
  let release;
  const blocked = new Promise((resolve) => { release = resolve; });
  const { submitted } = await setup(page, { process: async (route) => { await blocked; return route.fulfill({ json: { job_id: 'unknown-job' } }).catch(() => {}); } });
  const panel = await selectVideo(page); await confirm(panel);
  await page.clock.install();
  await panel.getByRole('button', { name: '쇼츠 제작하기', exact: true }).click();
  await expect(page.getByText('요청 접수 중 · 작업 ID 응답 대기')).toBeVisible();
  await page.clock.fastForward(180001);
  await expect(page.getByText(/응답 유실 · 중복 제작 방지/)).toBeVisible();
  expect(submitted).toHaveLength(1);
  release();
});

test('queued, partial and completed results use the original player and MP4 download', async ({ page }) => {
  const { polled } = await setup(page, { status: (route, count) => route.fulfill({ json: count === 1
    ? { status: 'queued', logs: ['Queued'], queue: { position: 2, ahead: 1, eta_seconds: 60 }, result: null }
    : { status: count === 2 ? 'processing' : 'completed', logs: ['AI analysis', 'FFmpeg rendered'], result: { clips: [clip] } } }) });
  const panel = await selectVideo(page); await confirm(panel);
  await panel.getByRole('button', { name: '쇼츠 제작하기', exact: true }).click();
  await expect(page.getByText(/in line · about/)).toBeVisible({ timeout: 10000 });
  const video = page.locator('video[src*="/videos/discovery-job/clip.mp4"]').first();
  await expect(video).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('COMPLETE', { exact: true })).toBeVisible({ timeout: 15000 });
  await expect.poll(() => video.evaluate((element) => element.videoWidth)).toBe(90);
  expect(await video.evaluate((element) => element.videoHeight)).toBe(160);
  await video.evaluate(async (element) => { element.muted = true; await element.play(); });
  await expect.poll(() => video.evaluate((element) => element.currentTime)).toBeGreaterThan(0);
  const downloadEvent = page.waitForEvent('download');
  await page.getByRole('button', { name: 'download', exact: true }).first().click();
  const download = await downloadEvent;
  expect(await download.failure()).toBeNull();
  expect(readFileSync(await download.path())).toEqual(media);
  expect(polled.length).toBeGreaterThanOrEqual(3);
});

for (const error of ['yt-dlp download failed', 'AI analysis failed', 'ffmpeg encoder error']) test(`worker failure: ${error}`, async ({ page }) => {
  await setup(page, { status: (route) => route.fulfill({ json: { status: 'failed', logs: [error], error, result: null } }) });
  const panel = await selectVideo(page); await confirm(panel);
  await panel.getByRole('button', { name: '쇼츠 제작하기', exact: true }).click();
  await expect(page.getByRole('region', { name: '탐색 영상 제작 정보' }).getByRole('alert')).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('COMPLETE', { exact: true })).toHaveCount(0);
});

test('lost submission response stays locked after reload and is never replayed', async ({ page }) => {
  const { submitted } = await setup(page, { process: (route) => route.abort('failed') });
  const panel = await selectVideo(page); await confirm(panel);
  await panel.getByRole('button', { name: '쇼츠 제작하기', exact: true }).click();
  await expect(page.getByText(/응답 유실 · 중복 제작 방지/)).toBeVisible();
  expect(submitted).toHaveLength(1);
  await page.reload();
  await expect(page.getByText(/응답 유실 · 중복 제작 방지/)).toBeVisible();
  expect(submitted).toHaveLength(1);
});

test('reloaded accepted job resumes status reads; missing job becomes an error without another POST', async ({ page }) => {
  let missing = false;
  const { submitted } = await setup(page, { status: (route) => missing
    ? route.fulfill({ status: 404, json: { detail: 'Job not found' } }) : route.fulfill({ json: { status: 'processing', logs: [], result: null } }) });
  const panel = await selectVideo(page); await confirm(panel);
  await panel.getByRole('button', { name: '쇼츠 제작하기', exact: true }).click();
  await expect(page.getByText(/작업 discovery-job/)).toBeVisible();
  await page.reload();
  missing = true;
  await expect(page.getByText(/작업 또는 결과 파일을 찾을 수 없습니다/)).toBeVisible({ timeout: 10000 });
  expect(submitted).toHaveLength(1);
});

test('existing direct URL and file upload still use the same processing API', async ({ page }) => {
  const { submitted } = await setup(page, { keys: true });
  await page.goto('/#app');
  await page.getByRole('button', { name: 'Video URL', exact: true }).click();
  await page.getByPlaceholder('https://... paste a video link').fill(videos[1].url);
  await page.getByRole('checkbox', { name: /I confirm I own/ }).check();
  await page.getByRole('button', { name: 'Generate Clips', exact: true }).click();
  await expect.poll(() => submitted.length).toBe(1);
  expect(submitted[0].url).toBe(videos[1].url); expect(submitted[0]).not.toHaveProperty('discovery_source');
  await page.getByRole('button', { name: 'New Project', exact: true }).click();
  // Unknown-duration upload exercises multipart wiring; the real server length gate
  // is exercised separately in ASGI tests. No duration or security checks are disabled.
  await page.locator('input[type="file"]').setInputFiles({ name: 'owned.mp4', mimeType: 'video/mp4', buffer: Buffer.from('fixture-with-unknown-browser-duration') });
  await page.getByRole('checkbox', { name: /I confirm I own/ }).check();
  await page.getByRole('button', { name: 'Generate Clips', exact: true }).click();
  await expect.poll(() => submitted.length, { timeout: 12000 }).toBe(2);
  expect(submitted[1]).toContain('filename="owned.mp4"'); expect(submitted[1]).toContain('name="acknowledged"');
});


test('reloaded cached Discovery completion rechecks files before showing success', async ({ page }) => {
  const { submitted, polled } = await setup(page, { status: (route) => route.fulfill({ status: 404, json: { detail: 'Expired job' } }) });
  await page.goto('/#app');
  await page.evaluate(({ source, savedClip }) => {
    localStorage.setItem('openshorts_session', JSON.stringify({ jobId: 'discovery-job', status: 'complete',
      results: { clips: [savedClip] }, discoveryOrigin: source, activeTab: 'dashboard', timestamp: Date.now() }));
  }, { source: videos[0], savedClip: clip });
  await page.reload();
  await expect(page.getByText('COMPLETE', { exact: true })).toHaveCount(0);
  await expect(page.getByText(/작업 또는 결과 파일을 찾을 수 없습니다/)).toBeVisible({ timeout: 10000 });
  expect(polled.length).toBeGreaterThan(0);
  expect(submitted).toHaveLength(0);
});
