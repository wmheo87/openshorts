import { useEffect, useMemo, useRef, useState } from 'react';
import { Search, ShieldCheck } from 'lucide-react';
import { searchVideos } from './api';
import SearchFilters from './SearchFilters';
import VideoGrid from './VideoGrid';
import VideoDetail from './VideoDetail';
import SearchHistory from './SearchHistory';
import { buildSearchRequest, defaultFilters, filtersFromRequest, formatDate, sortVideos } from './utils';
import { text } from './strings';
import { buildProductionData } from './production';

export default function DiscoveryPage({ onProduce }) {
  const [filters, setFilters] = useState({ ...defaultFilters });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [slow, setSlow] = useState(false);
  const [result, setResult] = useState(null);
  const [resultKeyword, setResultKeyword] = useState('');
  const [order, setOrder] = useState('score');
  const [selected, setSelected] = useState(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [downloadConfirmed, setDownloadConfirmed] = useState(false);
  const [productionOptions, setProductionOptions] = useState({ targetClips: '', maxSeconds: '', autoHook: '' });
  const [productionError, setProductionError] = useState('');
  const [producing, setProducing] = useState(false);
  const productionLock = useRef(false);
  const [historyVersion, setHistoryVersion] = useState(0);
  const pending = useRef(null);
  const sequence = useRef(0);
  const detail = useRef(null);
  const alert = useRef(null);
  const videos = useMemo(() => sortVideos(result?.items || [], order), [result, order]);

  useEffect(() => () => { sequence.current += 1; pending.current?.abort(); }, []);
  useEffect(() => {
    if (selected) { detail.current?.focus({ preventScroll: true }); detail.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
  }, [selected]);
  useEffect(() => { if (error) alert.current?.focus(); }, [error]);

  const execute = async (payload) => {
    const current = ++sequence.current;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setLoading(true); setSlow(false); setError(''); setErrors({});
    setResult(null); setSelected(null); setAcknowledged(false); setDownloadConfirmed(false); setProductionError(''); setResultKeyword(payload.keyword);
    const timer = setTimeout(() => { if (sequence.current === current) setSlow(true); }, 10000);
    try {
      const response = await searchVideos(payload, controller.signal);
      if (sequence.current === current) setResult(response);
    } catch (failure) {
      if (sequence.current === current) setError(failure.message);
    } finally {
      clearTimeout(timer);
      if (sequence.current === current) { setLoading(false); setHistoryVersion((version) => version + 1); }
    }
  };

  const submit = (event) => {
    event.preventDefault();
    if (loading) return;
    try { execute(buildSearchRequest(filters)); }
    catch (failure) { setErrors(failure.fields || {}); setError(failure.message); }
  };

  const replay = (request) => {
    if (loading) return;
    setFilters(filtersFromRequest(request));
    execute(request); // Preserve the exact historic ISO boundaries, including non-midnight timestamps.
  };

  const produce = async () => {
    if (productionLock.current || !selected) return;
    productionLock.current = true;
    setProducing(true); setProductionError('');
    try {
      const data = buildProductionData(selected, productionOptions, acknowledged, downloadConfirmed);
      if (!onProduce) throw new Error('제작 연결을 사용할 수 없습니다. 전체 OpenShorts 백엔드에서 실행해 주세요.');
      const result = await onProduce(data);
      if (result?.message) setProductionError(result.message);
    } catch (failure) { setProductionError(failure.message); }
    finally { productionLock.current = false; setProducing(false); }
  };

  return (
    <div className="h-full min-w-0 overflow-y-auto custom-scrollbar" data-testid="discovery-page">
      <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
        <header><p className="eyebrow text-brass mb-2">AI Shorts Studio · 영상 탐색</p><h1 className="font-display text-2xl sm:text-3xl text-ink">{text.title}</h1><p className="text-sm text-muted mt-2">{text.intro}</p></header>
        <SearchFilters filters={filters} errors={errors} loading={loading} onSubmit={submit} onCancel={() => pending.current?.abort()}
          onChange={(name, value) => { setFilters((previous) => ({ ...previous, [name]: value })); setErrors((previous) => ({ ...previous, [name]: undefined })); }} />
        {error && <p ref={alert} tabIndex={-1} role="alert" className="rounded-input border border-danger/40 bg-danger/10 p-4 text-sm text-danger focus:outline-none">{error}</p>}
        {loading && <div role="status" aria-live="polite" className="flex items-center gap-3 p-4 rounded-card border border-rule bg-paper2 text-sm text-muted"><Search className="animate-pulse shrink-0" size={20} /><span>{slow ? '검색이 지연되고 있습니다. 자동 재시도는 하지 않습니다. 대기를 중단해도 서버 작업은 계속될 수 있습니다.' : 'YouTube 영상 정보를 검색하고 있습니다…'}</span></div>}
        {selected && <div ref={detail} tabIndex={-1} className="focus:outline-none"><VideoDetail video={selected} acknowledged={acknowledged} onAcknowledge={setAcknowledged} onClose={() => { setSelected(null); setAcknowledged(false); setDownloadConfirmed(false); }} downloadConfirmed={downloadConfirmed} onDownloadConfirm={setDownloadConfirmed} options={productionOptions} onOptions={setProductionOptions} onProduce={produce} producing={producing} productionError={productionError} /></div>}
        {result && <section aria-label="영상 검색 결과" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg text-ink font-medium">검색 결과 {result.total}개</h2><p className="text-xs text-muted mt-1">“{resultKeyword}” · {result.cache_hit ? '캐시 결과' : '새 조회 결과'} · 조회 시각 {formatDate(result.fetched_at, true)}</p></div><label className="text-xs text-muted flex items-center gap-2">정렬<select aria-label="정렬" value={order} onChange={(event) => setOrder(event.target.value)} className="bg-paper2 border border-rule2 rounded-input p-2 text-ink2"><option value="score">추천 점수순</option><option value="views">조회수순</option><option value="newest">최신순</option></select></label></div>
          {result.limited && <p className="text-xs text-warn">조회 범위 또는 결과 상한에 도달했습니다. 전체 YouTube 영상의 순위가 아니며 다른 후보가 더 있을 수 있습니다.</p>}
          <VideoGrid videos={videos} selectedId={selected?.video_id} onSelect={(video) => { if (productionLock.current) return; setSelected(video); setAcknowledged(false); setDownloadConfirmed(false); setProductionError(''); }} />
          <div className="text-xs text-muted space-y-2 leading-relaxed"><p>{text.scoreNotice}</p><p>{text.rightsNotice}</p><details><summary className="cursor-pointer">서버 제공 안내 원문</summary><p className="mt-2 break-words">{result.score_notice}</p><p className="mt-2 break-words">{result.rights_notice}</p></details></div>
        </section>}
        {!result && !loading && !error && <div className="border border-dashed border-rule2 rounded-card p-8 text-center text-sm text-muted"><ShieldCheck size={24} className="mx-auto mb-3 text-brass" /><p>검색어와 조건을 입력해 CC BY 영상 후보를 찾아보세요.</p><p className="mt-2 text-xs">검색은 영상 정보만 조회하며 원본을 자동 다운로드하지 않습니다.</p></div>}
        <SearchHistory key={historyVersion} onReplay={replay} searchLoading={loading} />
      </div>
    </div>
  );
}
