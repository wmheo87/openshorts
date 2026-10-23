import VideoCard from './VideoCard';

export default function VideoGrid({ videos, selectedId, onSelect }) {
  if (!videos.length) return <div role="status" className="rounded-card border border-dashed border-rule2 p-8 text-center text-muted text-sm">조건에 맞는 영상이 없습니다. 검색어나 필터를 바꿔 보세요.</div>;
  return <div aria-label="영상 후보 목록" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">{videos.map((video) => <VideoCard key={video.video_id} video={video} selected={video.video_id === selectedId} onSelect={onSelect} />)}</div>;
}
