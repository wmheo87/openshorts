import { test, expect } from '@playwright/test';
import { mockApi } from './fixtures';

async function setup(page, { voices = true, source = 'elevenlabs' } = {}) {
  await page.addInitScript(() => {
    for (const key of ['gemini_key', 'elevenLabsKey_v1', 'falKey_v1']) localStorage.setItem(key, 'mock-key');
    localStorage.setItem('os_social_nudge_dismissed', '1');
  });
  await mockApi(page);
  const requests = [];
  await page.route('**/api/saasshorts/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/voices')) return route.fulfill({ json: { source, voices: voices ? [
      { voice_id: 'ko-account-voice', name: '한국어 계정 음성', labels: { gender: 'female', language: 'ko' }, supports_korean: true, korean_preview_url: '/mock-korean-preview.mp3' },
      { voice_id: 'english-voice', name: 'English voice', labels: { gender: 'female', language: 'en' }, supports_korean: false },
    ] : [] } });
    if (path.endsWith('/actor-gallery')) return route.fulfill({ json: { images: [{ url: '/mock-actor.png' }] } });
    if (path.endsWith('/analyze')) {
      const body = route.request().postDataJSON(); requests.push({ path, body });
      return route.fulfill({ json: { analysis: { product_name: '텀블러', key_features: [], pain_points: [] }, scripts: [
        { title: '상품 확인', language: body.language, full_narration: '상품 정보를 확인해 주세요', actor_description: 'An adult Korean woman',
          duration_seconds: 23, style: body.style, segments: [], hashtags: ['#쇼핑'] },
      ] } });
    }
    if (path.endsWith('/generate')) {
      requests.push({ path, body: route.request().postDataJSON() });
      return route.fulfill({ json: { job_id: 'mock-korean-job' } });
    }
    return route.fulfill({ json: { status: 'processing', logs: [] } });
  });
  await page.goto('/#app');
  if (page.viewportSize().width < 768) await page.getByRole('button', { name: 'open navigation' }).click();
  await page.getByRole('button', { name: /^AI Shorts/ }).click();
  return requests;
}

async function configure(page, language = 'ko') {
  if (language !== 'ko') await page.getByRole('radio', { name: language === 'en' ? /English/ : /Español/ }).click();
  await page.getByPlaceholder('e.g. artisan pizzeria in Madrid, productivity coach, sportswear store, meditation app...').fill('텀블러, 확인된 판매 가격 12000원');
  await page.getByRole('button', { name: 'generate scripts', exact: true }).click();
  await page.getByRole('button', { name: /Configure video/ }).click();
  await page.getByRole('button').filter({ has: page.getByAltText('Actor 1', { exact: true }) }).click();
}

for (const language of ['ko', 'en', 'es']) test(`AI Shorts ${language} preserves language and voice in API requests`, async ({ page }) => {
  const requests = await setup(page);
  await expect(page.getByRole('radio', { name: /한국어/ })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByRole('button', { name: /Low Cost/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Premium/ })).toBeVisible();
  await expect(page.getByRole('radio', { name: /Before\/After/ })).toBeVisible();
  await configure(page, language);
  const generate = page.getByRole('button', { name: /Generate video \(/ });
  if (language === 'ko') {
    await expect(generate).toBeDisabled();
    await page.getByRole('combobox', { name: '한국어 음성', exact: true }).selectOption('ko-account-voice');
    await expect(page.getByRole('combobox', { name: '한국어 음성', exact: true }).getByRole('option', { name: 'English voice' })).toHaveCount(0);
    const preview = page.getByLabel('한국어 음성 미리듣기');
    await expect(preview).toHaveAttribute('src', '/mock-korean-preview.mp3');
    await expect(preview).toHaveAttribute('controls', '');
    await preview.dispatchEvent('error');
    await expect(page.getByText(/미리듣기를 불러오지 못했습니다/)).toBeVisible();
  }
  await expect(generate).toBeEnabled();
  await generate.click();
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[0].body.language).toBe(language);
  expect(requests[1].body.script.language).toBe(language);
  if (language === 'ko') expect(requests[1].body.voice_id).toBe('ko-account-voice');
});

for (const source of ['elevenlabs', 'defaults']) test(`unconfirmed Korean voice (${source}) never falls back to English`, async ({ page }) => {
  const requests = await setup(page, { voices: source === 'defaults', source });
  await configure(page);
  await expect(page.getByText(/현재 ElevenLabs 계정에서 한국어 음성을 확인하지 못했습니다/)).toBeVisible();
  await expect(page.getByRole('button', { name: /Generate video \(/ })).toBeDisabled();
  expect(requests).toHaveLength(1);
});
