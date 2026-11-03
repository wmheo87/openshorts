import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { mockApi } from './fixtures';
const media = Buffer.from(readFileSync(new URL('./media/owned-preview.base64', import.meta.url), 'utf8').trim(), 'base64');
const photo = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jr1sAAAAASUVORK5CYII=', 'base64');
const sourceId = '11111111-1111-4111-8111-111111111111';
const musicId = '22222222-2222-4222-8222-222222222222';
async function setup(page, lost = false) {
  await page.addInitScript(() => { localStorage.setItem('gemini_key', 'mock-key'); localStorage.setItem('os_social_nudge_dismissed', '1'); });
  await mockApi(page);
  const posts = [], states = new Map();
  let finish = !lost;
  await page.route('**/api/saasshorts/product/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    if (path.endsWith('/providers')) return route.fulfill({ json: { providers: [
      { id: 'ffmpeg-product', available: true, capabilities: { approved_media_composition: true } },
      { id: 'kling-official', available: false, capabilities: null },
    ] } });
    if (path.endsWith('/assets')) {
      const music = request.postData().includes('\r\n\r\nmusic\r\n');
      return route.fulfill({ json: { id: music ? musicId : sourceId, kind: music ? 'music' : 'image', duration: music ? 4 : 0 } });
    }
    if (path.endsWith('/analyze') || path.endsWith('/generate')) {
      const body = request.postDataJSON(); posts.push({ path, body, headers: request.headers() });
      states.set(body.request_id, { action: path.endsWith('/analyze') ? 'analyze' : 'generate', body });
      if (lost) return route.abort('failed');
      return route.fulfill({ json: { request_id: body.request_id, state: 'queued' } });
    }
    if (path.includes('/requests/')) {
      const id = path.split('/').pop(), entry = states.get(id);
      if (!entry) return route.fulfill({ status: 404, json: { detail: 'not accepted yet' } });
      if (!finish) return route.fulfill({ json: { state: 'processing', logs: ['mock processing'] } });
      return route.fulfill({ json: { state: 'completed', ...(entry.action === 'analyze' ? { script: {
        language: 'ko', production_mode: 'product', title: '제품 정보', full_narration: '상품 정보와 가격을 확인해요', segments: entry.body.scenes.map(s => ({ asset_id: s.asset_id, narration: '상품 정보' })),
      } } : { result: { filename: 'product.mp4', duration: 2 } }), logs: ['mock complete'] } });
    }
    if (path.includes('/download/')) return route.fulfill({ body: media, contentType: 'video/mp4' });
    return route.fulfill({ status: 404, json: { detail: 'unknown route' } });
  });
  await page.goto('/#app');
  if (page.viewportSize().width < 768) await page.getByRole('button', { name: '메뉴 열기' }).click();
  await page.getByRole('button', { name: /^AI 쇼츠 제작/ }).first().click();
  return { posts, finish: () => { finish = true; } };
}
async function select(page) {
  await expect(page.getByLabel('제품 영상·사진 업로드', { exact: true })).toBeDisabled();
  await page.getByRole('checkbox', { name: /원본 영상·사진·음원의 사용/ }).check();
  await page.getByLabel('제품 영상·사진 업로드', { exact: true }).setInputFiles({ name: 'owned.png', mimeType: 'image/png', buffer: photo });
  await expect(page.getByLabel('장면 1 내용', { exact: true })).toBeVisible();
  await page.getByLabel('장면 1 내용', { exact: true }).fill('승인된 상품 정면');
  await page.getByLabel('확인된 상품 정보', { exact: true }).fill('판매 페이지에 명시된 정보만 사용');
}
const paid = page => page.getByRole('checkbox', { name: /이번 Gemini 유료 요청의 비용/ }).check();

test('default product mode needs no fal key and produces a preview/download from approved selections', async ({ page }) => {
  const { posts } = await setup(page);
  await expect(page.getByRole('button', { name: '제품 영상형 (기본·fal.ai 불필요)', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('필수 API 키가 없습니다.')).toHaveCount(0);
  await select(page);
  await page.getByLabel('장면 1 움직임', { exact: true }).selectOption('pan');
  await page.getByLabel('장면 1 크롭', { exact: true }).selectOption('right');
  await page.getByLabel('배경음 업로드', { exact: true }).setInputFiles({ name: 'owned.wav', mimeType: 'audio/wav', buffer: Buffer.from('mock-only-music') });
  await expect(page.getByText('배경음 선택됨', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '제품 대본 생성', exact: true })).toBeDisabled();
  await paid(page);
  await page.getByRole('button', { name: '제품 대본 생성', exact: true }).click();
  await expect(page.getByLabel('한국어 내레이션', { exact: true })).toBeVisible();
  expect(posts[0].body.scenes[0]).toMatchObject({ asset_id: sourceId, motion: 'pan', crop: 'right' });
  expect(posts[0].headers).not.toHaveProperty('x-fal-key');
  expect(posts[0].headers).not.toHaveProperty('x-elevenlabs-key');
  expect(posts[0].body.music_id).toBe(musicId);
  await page.getByLabel('장면 1 움직임', { exact: true }).selectOption('zoom');
  await expect(page.getByLabel('한국어 내레이션', { exact: true })).toBeVisible(); // Visual framing needs no extra paid script request.
  await expect(page.getByRole('button', { name: '제품 MP4 제작', exact: true })).toBeDisabled();
  await paid(page);
  await page.getByRole('checkbox', { name: /원본과 대본을 검토했으며/ }).check();
  await page.getByRole('button', { name: '제품 MP4 제작', exact: true }).evaluate(button => { button.click(); button.click(); });
  const player = page.getByLabel('제품 쇼츠 미리보기', { exact: true });
  await expect(player).toBeVisible();
  await expect.poll(() => player.evaluate(v => v.videoWidth)).toBe(90);
  const downloaded = page.waitForEvent('download');
  await page.getByRole('link', { name: 'MP4 다운로드', exact: true }).click();
  const download = await downloaded;
  expect(readFileSync(await download.path())).toEqual(media);
  expect(posts).toHaveLength(2);
  expect(posts[1].body.content_confirmed).toBe(true);
});

test('lost paid response survives reload with status GET only and no duplicate POST', async ({ page }) => {
  const state = await setup(page, true);
  await select(page); await paid(page);
  await page.getByRole('button', { name: '제품 대본 생성', exact: true }).click();
  await expect.poll(() => state.posts.length).toBe(1);
  await expect(page.getByRole('status')).toContainText(state.posts[0].body.request_id);
  await page.reload();
  if (page.viewportSize().width < 768) await page.getByRole('button', { name: '메뉴 열기' }).click();
  await page.getByRole('button', { name: /^AI 쇼츠 제작/ }).first().click();
  state.finish();
  await expect(page.getByLabel('한국어 내레이션', { exact: true })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(state.posts).toHaveLength(1);
});
