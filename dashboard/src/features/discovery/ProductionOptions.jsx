export default function ProductionOptions({ options, onChange, disabled }) {
  const selectClass = 'mt-1.5 w-full rounded-input border border-rule2 bg-paper px-3 py-2 text-sm text-ink';
  return <fieldset disabled={disabled} className="grid grid-cols-1 sm:grid-cols-3 gap-3 border-t border-rule pt-4">
    <legend className="text-sm text-ink pt-3">쇼츠 제작 옵션</legend>
    <label className="text-xs text-muted">목표 쇼츠 수<select aria-label="목표 쇼츠 수" value={options.targetClips} onChange={(e) => onChange({ ...options, targetClips: e.target.value })} className={selectClass}><option value="">엔진 기본값</option>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={String(n)}>{n}개</option>)}</select></label>
    <label className="text-xs text-muted">클립 길이<select aria-label="클립 길이" value={options.maxSeconds} onChange={(e) => onChange({ ...options, maxSeconds: e.target.value })} className={selectClass}><option value="">엔진 기본값</option><option value="30">15~30초</option><option value="60">15~60초</option></select></label>
    <label className="text-xs text-muted">AI 후킹 문구<select aria-label="AI 후킹 문구" value={options.autoHook} onChange={(e) => onChange({ ...options, autoHook: e.target.value })} className={selectClass}><option value="">엔진 기본값</option><option value="1">켜기</option><option value="0">끄기</option></select></label>
    <p className="text-xs text-muted sm:col-span-3">출력 9:16 세로형 · 레이아웃 자동 선택 · 개수와 길이는 목표값이며 실제 결과는 원본과 엔진 판단에 따라 달라집니다.</p>
  </fieldset>;
}
