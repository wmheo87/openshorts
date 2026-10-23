import { ExternalLink, X } from 'lucide-react';
import { text } from './strings';
import { formatDate, formatDuration, formatNumber, safeVideoUrl } from './utils';

export default function VideoDetail({ video, acknowledged, onAcknowledge, onClose }) {
  const original = safeVideoUrl(video.url);
  return (
    <section aria-label="선택한 영상 상세" className="rounded-card border border-brass/50 bg-paper2 p-4 sm:p-5 space-y-4">
      <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="eyebrow text-brass mb-2">선택한 영상</p><h2 className="text-lg text-ink font-medium break-words">{video.title}</h2><p className="text-sm text-muted mt-1">{video.channel_title}</p></div><button type="button" onClick={onClose} aria-label="영상 선택 해제" className="btn-ghost p-2 shrink-0"><X size={18} /></button></div>
      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs"><div><dt className="text-muted">영상 길이</dt><dd className="text-ink2 mt-1">{formatDuration(video.duration_seconds)}</dd></div><div><dt className="text-muted">조회수</dt><dd className="text-ink2 mt-1">{formatNumber(video.view_count)}회</dd></div><div><dt className="text-muted">추천 점수</dt><dd className="text-brass mt-1">{video.recommendation_score.toFixed(1)} / 100</dd></div><div><dt className="text-muted">라이선스 정보</dt><dd className="text-ok mt-1">{video.license === 'creativeCommon' ? 'Creative Commons (CC BY) 표시' : '확인 필요'}</dd></div></dl>
      {video.description && <p className="whitespace-pre-wrap break-words text-sm text-ink2 max-h-48 overflow-y-auto">{video.description}</p>}
      {original && <a href={original} target="_blank" rel="noopener noreferrer" className="inline-flex max-w-full items-center gap-2 text-xs text-brass"><ExternalLink size={14} className="shrink-0" /><span className="break-all">{original}</span><span className="sr-only">원본 영상 열기</span></a>}
      <div className="rounded-input bg-paper3 p-3 text-xs text-muted space-y-2"><p>게시일 {formatDate(video.published_at)} · 정보 조회 {formatDate(video.metadata_fetched_at, true)}</p><p>게시 후 {formatNumber(video.score_components.age_days)}일 · 일평균 조회 {formatNumber(video.score_components.average_daily_views)}회 · 키워드 관련성 {(video.score_components.keyword_relevance * 100).toFixed(0)} / 100</p><p>{text.scoreNotice}</p></div>
      <div className="border-t border-rule pt-4 space-y-3"><p className="text-xs text-warn leading-relaxed">{text.rightsNotice}</p><label className="flex items-start gap-2 text-sm text-ink2"><input type="checkbox" checked={acknowledged} onChange={(event) => onAcknowledge(event.target.checked)} className="mt-1 accent-brass" />원본과 이용 조건을 직접 검토했습니다 (이 화면에서만 표시)</label><p className="text-xs text-muted">{text.selectionNotice}</p></div>
    </section>
  );
}
