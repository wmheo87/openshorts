import { t as uiT, useUiLocale } from "../../i18n/runtime.js";
import { useState } from 'react';
import { Check, ExternalLink, ImageOff } from 'lucide-react';
import { formatDate, formatDuration, formatNumber, safeVideoUrl } from './utils';

function Thumbnail({ video }) {
  useUiLocale();
  const [failed, setFailed] = useState(false);
  return (
    <span className="relative block aspect-video bg-paper3 overflow-hidden">
      {video.thumbnail_url && !failed
        ? <img src={video.thumbnail_url} alt={`${video.title} ${uiT('썸네일')}`} loading="lazy" onError={() => setFailed(true)} className="w-full h-full object-cover" />
        : <span className="flex h-full items-center justify-center gap-2 text-muted text-xs"><ImageOff size={20} />{uiT("썸네일 없음")}</span>}
      <span className="absolute bottom-2 right-2 rounded bg-paper/90 text-ink px-2 py-1 text-xs font-mono">{uiT(formatDuration(video.duration_seconds))}</span>
    </span>
  );
}

export default function VideoCard({ video, selected, onSelect }) {
  useUiLocale();
  const original = safeVideoUrl(video.url);
  return (
    <article aria-label={video.title} className={`min-w-0 rounded-card border overflow-hidden bg-paper2 ${selected ? 'border-brass ring-1 ring-brass' : 'border-rule hover:border-rule2'}`}>
      <button type="button" aria-label={`${video.title} ${uiT('영상 선택')}`} aria-pressed={selected} onClick={() => onSelect(video)} className="block w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brass">
        <Thumbnail key={video.thumbnail_url || 'missing'} video={video} />
        <span className="block p-4 space-y-2">
          <span className="flex items-center justify-between gap-2"><span className="text-ok text-xs">{uiT("CC BY 후보")}</span><span className="text-brass text-xs font-mono">{uiT("추천 ")}{uiT(video.recommendation_score.toFixed(1))} / 100</span></span>
          <span className="block text-sm font-medium text-ink line-clamp-2 break-words">{video.title}</span>
          <span className="block text-xs text-muted truncate">{video.channel_title}</span>
          <span className="flex flex-wrap justify-between gap-2 text-xs text-muted"><span>{uiT("조회 ")}{uiT(formatNumber(video.view_count))}{uiT("회")}</span><span>{uiT(formatDate(video.published_at))}</span></span>
          <span className="inline-flex items-center gap-1 text-xs text-brass pt-2">{selected && <Check size={14} />}{uiT(selected ? '선택됨' : '영상 선택')}</span>
        </span>
      </button>
      {original && <a href={original} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center gap-2 border-t border-rule px-4 py-3 text-xs text-ink2 hover:bg-paper3">{uiT("원본 영상 열기")}<ExternalLink size={13} /></a>}
    </article>
  );
}
