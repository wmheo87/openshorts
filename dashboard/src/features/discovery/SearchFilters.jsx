const inputClass = 'w-full min-w-0 rounded-input border border-rule2 bg-paper px-3 py-2.5 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brass';

export default function SearchFilters({ filters, onChange, onSubmit, errors, loading, onCancel }) {
  const field = (name, label, type = 'number', extra = {}) => (
    <label className="block min-w-0 text-xs text-ink2" key={name}>
      <span className="block mb-1.5">{label}</span>
      <input name={name} type={type} aria-label={label} value={filters[name]} onChange={(event) => onChange(name, event.target.value)}
        className={inputClass} aria-invalid={!!errors[name]} aria-describedby={errors[name] ? `discovery-${name}-error` : undefined} {...extra} />
      {errors[name] && <span id={`discovery-${name}-error`} className="block mt-1 text-danger">{errors[name]}</span>}
    </label>
  );
  return (
    <form aria-label="영상 검색 조건" onSubmit={onSubmit} noValidate className="rounded-card border border-rule bg-paper2 p-4 sm:p-5 space-y-4">
      <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_10rem]">
        {field('keyword', '검색어', 'search', { placeholder: '예: 한국 요리, cooking, 日本料理', autoComplete: 'off', maxLength: 200 })}
        <label className="text-xs text-ink2">언어
          <select aria-label="언어" name="relevance_language" value={filters.relevance_language} onChange={(event) => onChange('relevance_language', event.target.value)} className={`${inputClass} mt-1.5`}>
            <option value="">언어 힌트 없음</option>
            <option value="ko">한국어</option><option value="en">영어</option><option value="ja">일본어</option>
          </select>
        </label>
      </div>
      <div className="grid grid-cols-1 min-[380px]:grid-cols-2 lg:grid-cols-3 gap-4">
        {field('min_views', '최소 조회수', 'number', { min: 0, max: 10 ** 15, step: 1 })}
        {field('min_duration_seconds', '최소 길이 (초)', 'number', { min: 1, max: 86400, step: 1 })}
        {field('max_duration_seconds', '최대 길이 (초)', 'number', { min: 1, max: 86400, step: 1 })}
        {field('published_after', '업로드 시작일', 'date')}
        {field('published_before', '업로드 종료일 (포함)', 'date')}
        <label className="text-xs text-ink2">최대 결과 수
          <select aria-label="최대 결과 수" name="max_results" value={filters.max_results} onChange={(event) => onChange('max_results', event.target.value)} className={`${inputClass} mt-1.5`}>
            {[10, 20, 30, 50].map((value) => <option key={value} value={String(value)}>{value}개</option>)}
            {![10, 20, 30, 50].includes(Number(filters.max_results)) && <option value={filters.max_results}>{filters.max_results}개 (이력)</option>}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-4">
        <div className="text-xs text-muted space-y-1"><p><span className="text-ok">CC BY</span> 라이선스 후보만 검색합니다.</p><p>날짜는 기기의 시간대를 기준으로 해당 날짜 전체를 포함합니다.</p></div>
        <div className="flex gap-2">
          {loading && <button type="button" onClick={onCancel} className="btn-ghost px-4 py-2.5">대기 중단</button>}
          <button type="submit" disabled={loading} className="btn-primary px-5 py-2.5 disabled:opacity-50">{loading ? '검색 중…' : '영상 검색'}</button>
        </div>
      </div>
    </form>
  );
}
