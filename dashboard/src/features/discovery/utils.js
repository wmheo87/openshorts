export const defaultFilters = {
  keyword: '', relevance_language: 'ko', min_views: '0',
  min_duration_seconds: '1', max_duration_seconds: '86400',
  published_after: '', published_before: '', max_results: '20',
};

export class FilterError extends Error {
  constructor(fields) {
    super('검색 조건을 확인해 주세요.');
    this.fields = fields;
  }
}

export function localDate(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return `${date.getFullYear().toString().padStart(4, '0')}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function dateBoundary(value, nextDay = false) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error('Invalid date');
  const date = new Date(`${value}T00:00:00`);
  if (localDate(date) !== value) throw new Error('Invalid date');
  if (nextDay) date.setDate(date.getDate() + 1); // Calendar day, including DST; not +24 hours.
  if (date.getFullYear() > 9999) throw new Error('Invalid date');
  return date.toISOString();
}

export function buildSearchRequest(filters) {
  const errors = {};
  const keyword = filters.keyword.normalize('NFC').trim().replace(/\s+/g, ' ');
  if (!keyword || [...keyword].length > 200 || [...keyword].some((char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127)) errors.keyword = '검색어를 1~200자로 입력하세요.';
  const request = { keyword, relevance_language: filters.relevance_language || null };
  if (request.relevance_language && !['ko', 'en', 'ja'].includes(request.relevance_language)) errors.relevance_language = '지원되는 언어를 선택하세요.';
  for (const [name, low, high] of [
    ['min_views', 0, 10 ** 15], ['min_duration_seconds', 1, 86400],
    ['max_duration_seconds', 1, 86400], ['max_results', 1, 50],
  ]) {
    const raw = String(filters[name]);
    const value = Number(raw);
    if (!/^\d+$/.test(raw) || !Number.isSafeInteger(value) || value < low || value > high) errors[name] = `${low.toLocaleString('ko-KR')}~${high.toLocaleString('ko-KR')} 범위의 정수를 입력하세요.`;
    request[name] = value;
  }
  if (request.min_duration_seconds > request.max_duration_seconds) errors.max_duration_seconds = '최대 길이는 최소 길이 이상이어야 합니다.';
  for (const name of ['published_after', 'published_before']) {
    request[name] = null;
    if (!filters[name]) continue;
    try { request[name] = dateBoundary(filters[name], name === 'published_before'); }
    catch { errors[name] = '올바른 날짜를 입력하세요.'; }
  }
  if (filters.published_after && filters.published_before && filters.published_after > filters.published_before) errors.published_before = '종료일은 시작일보다 빠를 수 없습니다.';
  if (Object.keys(errors).length) throw new FilterError(errors);
  return request;
}

export function filtersFromRequest(request) {
  return {
    ...defaultFilters, ...Object.fromEntries(Object.entries(request).map(([key, value]) => [key, value == null ? '' : String(value)])),
    published_after: request.published_after ? localDate(request.published_after) : '',
    published_before: request.published_before ? localDate(new Date(new Date(request.published_before).getTime() - 1)) : '',
  };
}

export function sortVideos(items, order) {
  const field = order === 'views' ? 'view_count' : 'recommendation_score';
  return [...items].sort((a, b) => {
    const difference = order === 'newest' ? new Date(b.published_at) - new Date(a.published_at) : b[field] - a[field];
    return difference || a.video_id.localeCompare(b.video_id);
  });
}

export const formatNumber = (value) => Number.isFinite(value) ? value.toLocaleString('ko-KR') : '정보 없음';
export function formatDuration(value) {
  if (!Number.isFinite(value)) return '정보 없음';
  const hours = Math.floor(value / 3600), minutes = Math.floor((value % 3600) / 60), seconds = Math.floor(value % 60);
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}` : `${minutes}:${String(seconds).padStart(2, '0')}`;
}
export function formatDate(value, withTime = false) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '정보 없음';
  return date.toLocaleString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit', ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}) });
}

export function safeVideoUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && ['www.youtube.com', 'youtube.com', 'youtu.be'].includes(url.hostname) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}
