import { useState } from 'react';
import { apiFetch } from '../../lib/api';
import { t, useUiLocale, formatUiMoney } from '../../i18n/runtime';

async function request(action, body) {
  const response = await apiFetch(`/api/saasshorts/product/url/${action}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '상품 URL 요청을 처리하지 못했습니다.');
  return data;
}
export default function ProductUrlInput({ disabled, remaining, onBusy, onFacts, onImported }) {
  useUiLocale();
  const [url, setUrl] = useState('');
  const [result, setResult] = useState(null);
  const [selected, setSelected] = useState([]);
  const [confirmed, setConfirmed] = useState([]);
  const [imported, setImported] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState([]);
  const analyze = async () => {
    if (disabled || busy || !url.trim()) return;
    setBusy(true); onBusy(true); setError(''); setErrors([]); setResult(null); setSelected([]); setConfirmed([]); setImported([]);
    try { setResult(await request('analyze', { url: url.trim() })); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); onBusy(false); }
  };
  const take = async () => {
    if (disabled || busy || !selected.length || selected.length > remaining || selected.some(id => !confirmed.includes(id))) return;
    setBusy(true); onBusy(true); setError(''); setErrors([]);
    try {
      const data = await request('import', { analysis_id: result.analysis_id, candidate_ids: selected, rights_confirmed: true });
      const done = data.imported_candidate_ids || data.assets.map(a => a.candidate_id);
      setImported(old => [...new Set([...old, ...done])]); setSelected(old => old.filter(id => !done.includes(id)));
      setErrors(data.errors); onImported(data.assets);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); onBusy(false); }
  };
  const facts = result ? [result.name && `상품명: ${result.name}`, result.brand && `브랜드: ${result.brand}`,
    result.description, result.price && `판매 페이지 표시 가격: ${result.price.amount} ${result.price.currency}`,
    ...result.features, `출처: ${result.source_url}`].filter(Boolean).join('\n').slice(0, 4000) : '';
  return <section className="card p-4 space-y-3 min-w-0 break-words" aria-label={t('상품 URL로 자동 제작')}>
    <h2 className="text-lg text-ink">{t('상품 URL로 자동 제작')}</h2>
    <p className="text-sm text-muted">{t('공개 상품 페이지의 표준 메타데이터만 분석합니다. 쿠팡·네이버는 현재 지원하지 않습니다. 수집 불가 시 직접 업로드를 사용하세요.')}</p>
    <label className="block">{t('상품 URL 입력')}<input className="input-field w-full" type="url" maxLength={4096} aria-label={t('상품 URL 입력')} placeholder="https://shop.example.com/products/item" value={url} disabled={disabled || busy} onChange={e => { setUrl(e.target.value); setResult(null); setSelected([]); setConfirmed([]); setImported([]); setError(''); setErrors([]); }} /></label>
    <button className="btn-ghost p-3" disabled={disabled || busy || !url.trim()} onClick={analyze}>{t('상품 분석')}</button>
    <p className="text-xs text-muted">{t('상품 분석·자료 가져오기는 Gemini나 유료 영상 API를 호출하지 않습니다. 대본·TTS 제작 비용은 별도로 확인해야 합니다.')}</p>
    {busy && <p role="status">{t('공개 자료 확인 중 · 자동 재시도 없음')}</p>}
    {error && <p role="alert" className="text-warn break-words">{t(error)}</p>}
    {result && <div className="space-y-3">
      <a className="text-brass break-all" href={result.source_url} target="_blank" rel="noopener noreferrer">{result.source_site}</a>
      <dl className="text-sm space-y-2"><div><dt>{t('상품명')}</dt><dd>{result.name || t('정보 없음')}</dd></div><div><dt>{t('브랜드')}</dt><dd>{result.brand || t('정보 없음')}</dd></div><div><dt>{t('판매 페이지 표시 가격')}</dt><dd>{result.price ? formatUiMoney(Number(result.price.amount), result.price.currency) : t('확인 가능한 가격 없음')}</dd></div></dl>
      <p className="text-sm whitespace-pre-wrap break-words">{result.description}</p>
      <ul className="text-sm">{result.features.map((feature, i) => <li key={i}>{feature}</li>)}</ul>
      <p className="text-sm text-warn">{t('판매 페이지의 표시 정보이며 사실·현재 가격·사용 권리를 보증하지 않습니다. 원문에 없는 효능·리뷰·할인율을 만들지 않습니다.')}</p>
      <button className="btn-ghost p-2" disabled={disabled || busy} onClick={() => onFacts(facts)}>{t('확인 후 상품 정보를 제작 입력에 적용')}</button>
      <p className="text-xs text-muted">{t('권리 확인 전에는 원본 파일을 서버로 가져오지 않습니다. 후보의 원본 링크에서 확인하고, 권리 확인 후 가져온 자료를 장면에서 미리보세요.')}</p>
      {!result.candidates.length && <p>{t('이미지·영상 후보를 찾지 못했습니다. 직접 업로드를 사용하세요.')}</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{result.candidates.map(candidate => <article className="border border-rule rounded-input p-3 space-y-2 min-w-0" key={candidate.id} aria-label={t(`자료 후보 ${Number(candidate.id) + 1}`)}>
        <p>{t(candidate.kind === 'video' ? '원본 영상' : '사진')} · {candidate.source_site} · {candidate.origin === 'jsonld' ? 'JSON-LD' : candidate.origin === 'opengraph' ? 'Open Graph' : 'HTML'}</p>
        {candidate.kind === 'image' && <p className="text-xs text-muted">{t(candidate.role === 'primary' ? '대표 이미지' : '추가 이미지')}</p>}
        {candidate.label && <p className="text-sm break-words">{candidate.label}</p>}
        <p className="text-xs">{candidate.width && candidate.height ? `${candidate.width} × ${candidate.height}` : t('크기 미확인 · 가져올 때 검증')}{candidate.duration_hint ? ` · ${t('원문 영상 길이')}: ${candidate.duration_hint}` : ''}</p>
        <a className="text-xs text-brass break-all block" href={candidate.url} target="_blank" rel="noopener noreferrer">{candidate.url}</a>
        <p>{t(imported.includes(candidate.id) ? '권리 확인 후 가져옴' : confirmed.includes(candidate.id) ? '사용자 권리 확인됨' : '사용 권리 미확인')}</p>
        <label className="block text-sm"><input type="checkbox" disabled={disabled || busy || imported.includes(candidate.id) || (!selected.includes(candidate.id) && selected.length >= remaining)} checked={selected.includes(candidate.id)} onChange={e => setSelected(old => e.target.checked ? [...old, candidate.id] : old.filter(id => id !== candidate.id))} />{t('제작에 사용할 자료 선택')}</label>
        <label className="block text-sm"><input type="checkbox" disabled={disabled || busy || imported.includes(candidate.id)} checked={confirmed.includes(candidate.id)} onChange={e => setConfirmed(old => e.target.checked ? [...old, candidate.id] : old.filter(id => id !== candidate.id))} />{t('이 자료의 사용·편집 권리를 확인했습니다')}</label>
      </article>)}</div>
      {result.candidates.length > 0 && <button className="btn-primary p-3" disabled={disabled || busy || !selected.length || selected.length > remaining || selected.some(id => !confirmed.includes(id))} onClick={take}>{t('권리 확인한 선택 자료 가져오기')}</button>}
      {errors.map(item => <p role="alert" className="text-warn break-words" key={item.candidate_id}>{t(item.message)}</p>)}
    </div>}
  </section>;
}
