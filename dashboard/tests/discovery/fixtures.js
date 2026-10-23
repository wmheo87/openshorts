export const videos = [
  { video_id: 'aaaaaaaaaaa', title: '한국 요리 수업', recommendation_score: 95, view_count: 12000, published_at: '2026-09-01T00:00:00Z' },
  { video_id: 'bbbbbbbbbbb', title: 'Cooking at home', recommendation_score: 70, view_count: 200000, published_at: '2026-08-01T00:00:00Z' },
  { video_id: 'ccccccccccc', title: '日本料理の基本', recommendation_score: 50, view_count: 30000, published_at: '2026-10-20T00:00:00Z' },
].map((video) => ({
  ...video, url: `https://www.youtube.com/watch?v=${video.video_id}`, description: '설명은 일반 텍스트입니다.',
  channel_id: 'test-channel', channel_title: '테스트 채널', thumbnail_url: `https://i.ytimg.com/vi/${video.video_id}/hqdefault.jpg`,
  duration_seconds: 600, license: 'creativeCommon', metadata_fetched_at: '2026-10-23T00:00:00Z',
  score_components: { age_days: 10, average_daily_views: 1200, keyword_relevance: 1 },
}));

export const historyRequest = {
  keyword: '이전 검색', relevance_language: 'ja', min_views: 3000, min_duration_seconds: 120,
  max_duration_seconds: 1200, max_results: 30, published_after: '2026-09-01T03:45:00Z', published_before: '2026-09-20T16:30:00Z',
};
export const historyEntry = { search_id: 'history-1', requested_at: '2026-10-22T00:00:00Z', request: historyRequest, result_count: 3, cache_hit: true, status: 'success', error_code: null };

export function searchResponse(items = videos) {
  return {
    search_id: 'mock-search', items, total: items.length, cache_hit: true,
    fetched_at: '2026-10-23T00:00:00Z', expires_at: '2026-10-23T01:00:00Z',
    scanned_count: 50, pages_fetched: 1, limited: true, score_version: 'heuristic-v1',
    score_notice: 'Independent heuristic, not a viral success probability.',
    rights_notice: 'Creative Commons metadata is not proof of all usage rights.',
  };
}

export async function mockApi(page, options = {}) {
  const calls = [];
  await page.route('https://i.ytimg.com/**', (route) => route.abort());
  await page.route('**/api/**', async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    calls.push({ path: url.pathname, method: req.method(), body: req.postDataJSON() });
    if (url.pathname === '/api/config') return route.fulfill({ json: { billingEnabled: false, googleAuthEnabled: false, youtubeUrlEnabled: true, jobRetentionSeconds: 86400, localLlm: null } });
    if (url.pathname === '/api/discovery/history') {
      if (options.historyError) return route.fulfill({ status: 503, json: { detail: { code: 'discovery_storage_unavailable' } } });
      return route.fulfill({ json: { items: options.history === undefined ? [historyEntry] : options.history, next_before_id: null } });
    }
    if (url.pathname === '/api/discovery/search') {
      if (options.onSearch) return options.onSearch(route);
      if (options.searchError) return route.fulfill({ status: options.searchError.status, json: { detail: { code: options.searchError.code, message: 'Server original', retryable: false } } });
      return route.fulfill({ json: options.response || searchResponse() });
    }
    return route.fulfill({ status: 404, json: { detail: 'Not part of discovery' } });
  });
  return calls;
}
