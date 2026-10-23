import { useCallback, useEffect, useRef, useState } from 'react';
import { getSearchHistory } from './api';
import { errorMessage, text } from './strings';
import { formatDate, formatDuration, formatNumber } from './utils';

export default function SearchHistory({ onReplay, searchLoading }) {
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef(null);
  const sequence = useRef(0);

  const load = useCallback(async (beforeId = null) => {
    const current = ++sequence.current;
    controller.current?.abort();
    const pending = new AbortController();
    controller.current = pending;
    setLoading(true); setError('');
    try {
      const response = await getSearchHistory(beforeId, pending.signal);
      if (sequence.current !== current) return;
      setItems((previous) => {
        const combined = beforeId == null ? response.items : [...previous, ...response.items];
        return [...new Map(combined.map((entry) => [entry.search_id, entry])).values()];
      });
      setCursor(response.next_before_id);
    } catch (failure) {
      if (sequence.current === current && failure.code !== 'cancelled') setError(failure.message);
    } finally {
      if (sequence.current === current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    return () => { sequence.current += 1; controller.current?.abort(); };
  }, [load]);

  return (
    <section aria-label="검색 이력" className="rounded-card border border-rule bg-paper2 p-4 sm:p-5 space-y-3">
      <div className="flex items-center justify-between gap-3"><h2 className="text-base font-medium text-ink">최근 검색 이력</h2><button type="button" disabled={loading} onClick={() => load()} className="btn-ghost text-xs px-3 py-2 disabled:opacity-50">이력 새로고침</button></div>
      <p className="text-xs text-muted leading-relaxed">{text.historyNotice}</p>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {!loading && !error && !items.length && <p className="text-sm text-muted">저장된 검색 이력이 없습니다.</p>}
      <ul className="divide-y divide-rule">
        {items.map((entry) => <li key={entry.search_id} className="py-3 space-y-2">
          <div className="flex flex-wrap justify-between gap-2 text-sm"><span className="font-medium text-ink break-all">{entry.request.keyword}</span><span className={entry.status === 'error' ? 'text-danger' : 'text-muted'}>{entry.status === 'success' ? '성공' : entry.status === 'error' ? '실패' : '미완료'} · {entry.result_count == null ? '결과 미확인' : `${entry.result_count}개`}{entry.cache_hit && ' · 캐시'}</span></div>
          <p className="text-xs text-muted">{formatDate(entry.requested_at, true)} · 언어 {({ ko: '한국어', en: '영어', ja: '일본어' })[entry.request.relevance_language] || '힌트 없음'} · 최소 조회 {formatNumber(entry.request.min_views)}회 · 길이 {formatDuration(entry.request.min_duration_seconds)}~{formatDuration(entry.request.max_duration_seconds)}</p>
          <p className="text-xs text-muted">게시 범위: {entry.request.published_after ? formatDate(entry.request.published_after, true) : '시작 제한 없음'} ~ {entry.request.published_before ? `${formatDate(entry.request.published_before, true)} 미만` : '종료 제한 없음'} · 최대 {entry.request.max_results}개</p>
          {entry.error_code && <p className="text-xs text-danger">{errorMessage(entry.error_code)}</p>}
          <button type="button" disabled={searchLoading} onClick={() => onReplay(entry.request)} className="btn-ghost px-3 py-2 text-xs disabled:opacity-50">이 조건으로 다시 검색</button>
        </li>)}
      </ul>
      {loading && <p role="status" className="text-sm text-muted">검색 이력을 불러오는 중…</p>}
      {cursor != null && <button type="button" disabled={loading} onClick={() => load(cursor)} className="btn-ghost px-4 py-2 text-xs disabled:opacity-50">이전 이력 더 보기</button>}
    </section>
  );
}
