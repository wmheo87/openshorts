import { test, expect } from '@playwright/test';
import { mockApi, historyEntry, historyRequest, searchResponse, videos } from './fixtures';

async function open(page, options) {
  const calls = await mockApi(page, options);
  await page.goto('/#app?tab=discovery');
  await expect(page.getByRole('heading', { name: 'Video Discovery', exact: true })).toBeVisible();
  return calls;
}
async function search(page, keyword = '한국 요리') {
  await page.getByLabel('검색어', { exact: true }).fill(keyword);
  await page.getByRole('button', { name: '영상 검색', exact: true }).click();
  await expect(page.getByRole('heading', { name: '검색 결과 3개' })).toBeVisible();
}
const cardTitles = (page) => page.getByLabel('영상 후보 목록').locator('article').evaluateAll((cards) => cards.map((card) => card.getAttribute('aria-label')));

test('search renders, sends exact P1 filters, and preserves all existing menus', async ({ page, isMobile }) => {
  const calls = await open(page);
  await expect(page.getByText('Required API keys missing.')).toHaveCount(0);
  await page.getByLabel('최소 조회수', { exact: true }).fill('10000');
  await page.getByLabel('최소 길이 (초)', { exact: true }).fill('120');
  await page.getByLabel('최대 길이 (초)', { exact: true }).fill('1200');
  await page.getByLabel('업로드 시작일', { exact: true }).fill('2026-10-01');
  await page.getByLabel('업로드 종료일 (포함)', { exact: true }).fill('2026-10-23');
  await page.locator('select[name="max_results"]').selectOption('50');
  await search(page);
  const request = calls.find((call) => call.path === '/api/discovery/search');
  expect(request.body).toEqual({ keyword: '한국 요리', relevance_language: 'ko', min_views: 10000, min_duration_seconds: 120, max_duration_seconds: 1200, max_results: 50, published_after: '2026-09-30T15:00:00.000Z', published_before: '2026-10-23T15:00:00.000Z' });
  await expect(page.getByText(/캐시 결과/)).toBeVisible();
  await expect(page.getByText(/조회 범위 또는 결과 상한/)).toBeVisible();
  await expect(page.getByText(/바이럴 성공 확률이나/).first()).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('discovery.png') });
  if (isMobile) await page.getByRole('button', { name: 'open navigation' }).click();
  for (const label of ['Clip Generator', 'AI Shorts', 'AI Agent', 'UGC Gallery', 'YouTube Studio', 'Settings', 'Video Discovery']) await expect(page.getByRole('button', { name: new RegExp(label) }).first()).toBeVisible();
  expect(calls.some((call) => /process|render|social|translate/.test(call.path))).toBe(false);
});

test('English and Japanese searches use the chosen language', async ({ page }) => {
  const calls = await open(page);
  for (const [keyword, language] of [['cooking', 'en'], ['日本料理', 'ja']]) {
    await page.locator('select[name="relevance_language"]').selectOption(language);
    await search(page, keyword);
  }
  expect(calls.filter((call) => call.path.endsWith('/search')).map((call) => [call.body.keyword, call.body.relevance_language])).toEqual([['cooking', 'en'], ['日本料理', 'ja']]);
});

test('client validation rejects empty keywords and inverted lengths without a search call', async ({ page }) => {
  const calls = await open(page);
  await page.getByRole('button', { name: '영상 검색', exact: true }).click();
  await expect(page.getByText('검색어를 1~200자로 입력하세요.')).toBeVisible();
  await page.getByLabel('검색어', { exact: true }).fill('한국 요리');
  await page.getByLabel('최소 길이 (초)', { exact: true }).fill('100');
  await page.getByLabel('최대 길이 (초)', { exact: true }).fill('50');
  await page.getByRole('button', { name: '영상 검색', exact: true }).click();
  await expect(page.getByText('최대 길이는 최소 길이 이상이어야 합니다.')).toBeVisible();
  expect(calls.filter((call) => call.path.endsWith('/search'))).toHaveLength(0);
});

test('sorts by score, views and date without calling the server again', async ({ page }) => {
  const calls = await open(page);
  await search(page);
  expect(await cardTitles(page)).toEqual(videos.map((v) => v.title));
  await page.getByLabel('정렬', { exact: true }).selectOption('views');
  expect(await cardTitles(page)).toEqual([videos[1].title, videos[2].title, videos[0].title]);
  await page.getByLabel('정렬', { exact: true }).selectOption('newest');
  expect(await cardTitles(page)).toEqual([videos[2].title, videos[0].title, videos[1].title]);
  expect(calls.filter((call) => call.path.endsWith('/search'))).toHaveLength(1);
});

test('selection shows details, temporary rights confirmation, safe original link and broken thumbnail fallback', async ({ page }) => {
  const calls = await open(page);
  await search(page);
  const card = page.getByRole('article', { name: videos[0].title, exact: true });
  await expect(card.getByText('썸네일 없음')).toBeVisible();
  await card.getByRole('button').click();
  const detail = page.getByRole('region', { name: '선택한 영상 상세' });
  await expect(detail).toBeVisible();
  await expect(detail.getByText(/모든 이용 권리가 보장되지는/)).toBeVisible();
  await expect(detail.getByText(/선택과 체크만으로 제작하지 않습니다/)).toBeVisible();
  await detail.getByRole('checkbox', { name: /원본과 이용 조건/ }).check();
  await expect(detail.getByRole('checkbox', { name: /원본과 이용 조건/ })).toBeChecked();
  const link = detail.getByRole('link');
  await expect(link).toHaveAttribute('href', videos[0].url);
  await expect(link).toHaveAttribute('target', '_blank');
  await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  await page.context().route('https://www.youtube.com/**', (route) => route.fulfill({ body: '<h1>Original source mock</h1>', contentType: 'text/html' }));
  const popupPromise = page.waitForEvent('popup');
  await link.click();
  const popup = await popupPromise;
  await popup.waitForLoadState();
  expect(popup.url()).toBe(videos[0].url);
  await popup.close();
  await page.getByRole('button', { name: `${videos[1].title} 영상 선택` }).click();
  await expect(detail.getByRole('checkbox', { name: /원본과 이용 조건/ })).not.toBeChecked();
  expect(calls.filter((call) => call.method !== 'GET').map((call) => call.path)).toEqual(['/api/discovery/search']);
});

test('history displays outcomes and replays exact original timestamps', async ({ page }) => {
  const calls = await open(page);
  const history = page.getByRole('region', { name: '검색 이력', exact: true });
  await expect(history.getByText('이전 검색', { exact: true })).toBeVisible();
  await expect(history.getByText('성공 · 3개 · 캐시')).toBeVisible();
  await history.getByRole('button', { name: '이 조건으로 다시 검색' }).click();
  await expect(page.getByRole('heading', { name: '검색 결과 3개' })).toBeVisible();
  expect(calls.find((call) => call.path.endsWith('/search')).body).toEqual(historyRequest);
  await expect(page.getByLabel('검색어', { exact: true })).toHaveValue(historyRequest.keyword);
});

test('empty results and empty history are honest empty states', async ({ page }) => {
  await open(page, { response: searchResponse([]), history: [] });
  await expect(page.getByText('저장된 검색 이력이 없습니다.')).toBeVisible();
  await page.getByLabel('검색어', { exact: true }).fill('없는 영상');
  await page.getByRole('button', { name: '영상 검색', exact: true }).click();
  await expect(page.getByRole('heading', { name: '검색 결과 0개' })).toBeVisible();
  await expect(page.getByText(/조건에 맞는 영상이 없습니다/)).toBeVisible();
});

for (const [status, code, message] of [
  [503, 'provider_not_configured', '서버에 YouTube API 키가 설정되지 않았습니다'],
  [503, 'discovery_disabled', '탐색 기능이 꺼져 있습니다'],
  [429, 'youtube_quota_exceeded', 'YouTube API 할당량을 모두 사용했습니다'],
  [429, 'rate_limited', '검색 요청 제한에 도달했습니다'],
  [422, null, '검색 조건이 올바르지 않습니다'],
  [502, 'provider_access_denied', 'YouTube API 접근이 거부됐습니다'],
  [504, 'provider_timeout', 'YouTube API 응답이 지연'],
]) test(`maps ${status}/${code} to Korean with no automatic retries`, async ({ page }) => {
  const calls = await open(page, { searchError: { status, code } });
  await page.getByLabel('검색어', { exact: true }).fill('한국 요리');
  await page.getByRole('button', { name: '영상 검색', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: message })).toBeVisible();
  expect(calls.filter((call) => call.path.endsWith('/search'))).toHaveLength(1);
});

test('network failure and history failure remain separate, with manual retry only', async ({ page }) => {
  const calls = await open(page, { historyError: true, onSearch: (route) => route.abort('failed') });
  await expect(page.getByRole('alert').filter({ hasText: '검색 이력 저장소' })).toBeVisible();
  await page.getByLabel('검색어', { exact: true }).fill('한국 요리');
  await page.getByRole('button', { name: '영상 검색', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: '서버에 연결할 수 없습니다' })).toBeVisible();
  expect(calls.filter((call) => call.path.endsWith('/search'))).toHaveLength(1);
});

test('slow searches show loading, can stop waiting, and never submit production work', async ({ page }) => {
  let release;
  const blocked = new Promise((resolve) => { release = resolve; });
  const calls = await open(page, { onSearch: async (route) => { await blocked; await route.fulfill({ json: searchResponse() }).catch(() => {}); } });
  await page.clock.install();
  await page.getByLabel('검색어', { exact: true }).fill('한국 요리');
  await page.getByRole('button', { name: '영상 검색', exact: true }).click();
  await expect(page.getByRole('button', { name: '검색 중…' })).toBeDisabled();
  await page.clock.fastForward(11000);
  await expect(page.getByText(/검색이 지연되고 있습니다/)).toBeVisible();
  await page.getByRole('button', { name: '대기 중단' }).click();
  await expect(page.getByRole('alert').filter({ hasText: '응답 대기를 중단' })).toBeVisible();
  release();
  expect(calls.filter((call) => call.path.endsWith('/search'))).toHaveLength(1);
});

test('HTML metadata is rendered as text and the layout fits the viewport', async ({ page }) => {
  const title = '<img src=x onerror="window.discoveryXss=1">';
  await open(page, { response: searchResponse([{ ...videos[0], title, thumbnail_url: null, description: '<script>window.discoveryXss=1</script>' }]) });
  await page.getByLabel('검색어', { exact: true }).fill('text');
  await page.getByRole('button', { name: '영상 검색', exact: true }).click();
  await page.getByRole('button', { name: `${title} 영상 선택`, exact: true }).click();
  await expect(page.getByRole('region', { name: '선택한 영상 상세' }).getByText('<script>window.discoveryXss=1</script>', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.discoveryXss)).toBeUndefined();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.getByTestId('discovery-page').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
});

test('client timeout shows an actionable message without retrying', async ({ page }) => {
  let release;
  const blocked = new Promise((resolve) => { release = resolve; });
  const calls = await open(page, { onSearch: async (route) => { await blocked; await route.fulfill({ json: searchResponse() }).catch(() => {}); } });
  await page.clock.install();
  await page.getByLabel('검색어', { exact: true }).fill('한국 요리');
  await page.getByRole('button', { name: '영상 검색', exact: true }).click();
  await page.clock.fastForward(76000);
  await expect(page.getByRole('alert').filter({ hasText: '서버 응답 대기 시간이 초과됐습니다' })).toBeVisible();
  release();
  expect(calls.filter((call) => call.path.endsWith('/search'))).toHaveLength(1);
});

test('history pagination displays failed and unfinished searches', async ({ page }) => {
  await mockApi(page);
  await page.route('**/api/discovery/history?**', (route) => route.fulfill({ json: new URL(route.request().url()).searchParams.has('before_id')
    ? { items: [{ ...historyEntry, search_id: 'pending', status: 'pending', result_count: null }], next_before_id: null }
    : { items: [{ ...historyEntry, search_id: 'failed', status: 'error', error_code: 'youtube_quota_exceeded', result_count: null }], next_before_id: 10 } }));
  await page.goto('/#app?tab=discovery');
  const history = page.getByRole('region', { name: '검색 이력', exact: true });
  await expect(history.getByText(/실패 · 결과 미확인/)).toBeVisible();
  await expect(history.getByText(/YouTube API 할당량을 모두/)).toBeVisible();
  await history.getByRole('button', { name: '이전 이력 더 보기' }).click();
  await expect(history.getByText(/미완료 · 결과 미확인/)).toBeVisible();
  await expect(history.getByRole('button', { name: '이전 이력 더 보기' })).toHaveCount(0);
});

test('feature flag off hides discovery and keeps the original Clip Generator', async ({ page, isMobile }) => {
  const calls = await mockApi(page);
  await page.goto('http://127.0.0.1:5181/#app?tab=discovery');
  await expect(page.getByTestId('discovery-page')).toHaveCount(0);
  await expect(page.getByText('Required API keys missing.')).toBeVisible();
  if (isMobile) await page.getByRole('button', { name: 'open navigation' }).click();
  await expect(page.getByRole('button', { name: /Video Discovery/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Clip Generator/ }).first()).toBeVisible();
  expect(calls.some((call) => call.path.startsWith('/api/discovery'))).toBe(false);
});
