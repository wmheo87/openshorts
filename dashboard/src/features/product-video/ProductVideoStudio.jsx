import LocalizedFileInput from '../../i18n/LocalizedFileInput';
import LocalizedDiagnostic from '../../i18n/LocalizedDiagnostic';
import { t as uiT, useUiLocale } from "../../i18n/runtime.js";
import { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../../lib/api';

const PENDING = 'product_video_pending_v1';
const DRAFT = 'product_video_draft_v1';
function read(key) { try { return JSON.parse(sessionStorage.getItem(key) || 'null'); } catch { return null; } }
function write(key, value) { try { if (value) sessionStorage.setItem(key, JSON.stringify(value)); else sessionStorage.removeItem(key); } catch { /* in-memory lock still applies */ } }
async function jsonRequest(path, options) {
  const res = await apiFetch(`/api/saasshorts/product${path}`, options);
  const data = await res.json();
  if (!res.ok) { const error = new Error(typeof data.detail === 'string' ? data.detail : '요청을 확인해 주세요.'); error.status = res.status; throw error; }
  return data;
}
const input = 'input-field w-full';

export default function ProductVideoStudio({ geminiApiKey }) {
  useUiLocale();
  const [scenes, setScenes] = useState(() => read(DRAFT)?.scenes || []);
  const [description, setDescription] = useState(() => read(DRAFT)?.description || '');
  const [script, setScript] = useState(() => read(DRAFT)?.script || null);
  const [music, setMusic] = useState(null);
  const [musicVolume, setMusicVolume] = useState(.12);
  const [transition, setTransition] = useState('fade');
  const [voice, setVoice] = useState('Kore');
  const [rights, setRights] = useState(false);
  const [paid, setPaid] = useState(false);
  const [content, setContent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(() => read(PENDING));
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const [catalog, setCatalog] = useState([]);
  const [ttsModel, setTtsModel] = useState('확인 중');
  const [video, setVideo] = useState('');
  const lock = useRef(false);
  const urls = useRef(new Set());

  useEffect(() => { jsonRequest('/providers').then(data => { setCatalog(Array.isArray(data.providers) ? data.providers : []); setTtsModel(data.tts_model || '미확인'); }).catch(e => setError(e.message)); }, []);
  useEffect(() => { write(DRAFT, { scenes: scenes.map(({ preview: _preview, ...scene }) => scene), description, script }); }, [scenes, description, script]);
  useEffect(() => () => { urls.current.forEach(url => URL.revokeObjectURL(url)); }, []);

  useEffect(() => {
    if (!pending) return undefined;
    let cancelled = false, inFlight = false;
    const poll = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const data = await jsonRequest(`/requests/${pending.request_id}`);
        if (cancelled) return;
        setStatus(data); setError('');
        if (data.state === 'interrupted') { setError(data.error); return; }
        if (['completed', 'failed', 'expired'].includes(data.state)) {
          if (data.script) setScript(data.script);
          if (data.result) {
            const response = await apiFetch(`/api/saasshorts/product/download/${pending.request_id}`);
            if (!response.ok) throw new Error('결과 MP4가 없거나 다운로드 권한을 확인할 수 없습니다.');
            const url = URL.createObjectURL(await response.blob()); urls.current.add(url);
            if (!cancelled) setVideo(url);
          }
          if (data.error) setError(data.error);
          write(PENDING, null); setPending(null); lock.current = false;
        }
      } catch (e) { if (!cancelled) setError(`${e.message} 접수 여부를 확인 중입니다. 자동 POST 재전송은 하지 않습니다.`); }
      finally { inFlight = false; }
    };
    poll(); const timer = setInterval(poll, 1500);
    return () => { cancelled = true; clearInterval(timer); };
  }, [pending]);

  const change = (index, values) => { setScenes(previous => previous.map((s, i) => i === index ? { ...s, ...values } : s)); if ('note' in values || 'start' in values || 'end' in values) setScript(null); setContent(false); };
  const upload = async (files, isMusic = false) => {
    if (!rights || busy || pending) return;
    setBusy(true); setError('');
    try {
      if (!isMusic && scenes.length + files.length > 10) throw new Error('최대 10개 장면을 사용하세요.');
      for (const file of files) {
        const kind = isMusic ? 'music' : file.type.startsWith('image/') ? 'image' : 'video';
        const form = new FormData(); form.append('file', file); form.append('kind', kind); form.append('rights_confirmed', 'true');
        const asset = await jsonRequest('/assets', { method: 'POST', body: form });
        if (isMusic) setMusic(asset);
        else {
          const preview = URL.createObjectURL(file); urls.current.add(preview);
          setScenes(previous => [...previous, { asset_id: asset.id, kind, source_duration: asset.duration,
            start: 0, end: Math.min(3, asset.duration || 3), duration: 3, crop: 'center', motion: 'zoom', note: '', preview }]);
          setScript(null); setContent(false);
        }
      }
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  const submit = async action => {
    if (lock.current || pending || busy || !rights || !paid || !scenes.length || (action === 'generate' && (!script || !content))) return;
    lock.current = true; setError(''); setVideo(''); setStatus(null);
    const request = { request_id: crypto.randomUUID(), action };
    write(PENDING, request); setPending(request); setPaid(false);
    const body = { request_id: request.request_id, scenes: scenes.map(({ kind: _kind, source_duration: _source, preview: _preview, ...scene }) => scene),
      description, rights_confirmed: true, paid_confirmed: true, content_confirmed: content,
      script: action === 'generate' ? script : null, voice, music_id: music?.id || null, music_volume: musicVolume, transition };
    try {
      await jsonRequest(`/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(geminiApiKey ? { 'X-Gemini-Key': geminiApiKey } : {}) }, body: JSON.stringify(body) });
    } catch (e) {
      // A response might be lost after acceptance. Keep the same request ID and poll only.
      if ([400, 401, 403, 410, 413, 422].includes(e.status)) {
        write(PENDING, null); setPending(null); lock.current = false; setError(e.message);
      } else setError(`${e.message} 서버에 이 요청 ID가 접수됐는지 확인 중입니다. 자동 재전송하지 않습니다.`);
    }
  };
  const disabled = busy || !!pending;

  return <section className="h-full overflow-y-auto p-4 sm:p-6 space-y-5" aria-label={uiT("제품 영상형 제작")}>
    <h1 className="text-xl text-ink">{uiT("승인된 제품 원본으로 쇼핑 쇼츠 만들기")}</h1>
    <p className="text-sm text-muted">{uiT("fal.ai·AI 배우·립싱크 없이 원본 영상/사진 + Gemini 대본·TTS + FFmpeg로 제작합니다. 원본 소리는 사용하지 않으며 선택한 배경음만 섞습니다. 긴 음성에서는 선택 영상의 마지막 프레임을 정지 표시할 수 있습니다.")}</p>
    <details><summary>{uiT("공급자별 지원 기능과 필수 키")}</summary><div className="overflow-x-auto"><table className="text-xs w-full"><thead><tr>{['공급자', '사용 가능', 'AI 이미지', 'AI 이미지→영상', '아바타', '립싱크', '승인 원본 합성'].map(h => <th key={h}>{uiT(h)}</th>)}</tr></thead><tbody>{catalog.map(p => <tr key={p.id}><td>{uiT(p.id)}</td><td>{uiT(p.available ? '가능' : '미구현·검증 전')}</td>{['image_generation', 'image_to_video', 'avatar', 'lipsync', 'approved_media_composition'].map(key => <td key={key}>{uiT(p.capabilities ? p.capabilities[key] ? '지원' : '미지원' : '미확인')}</td>)}</tr>)}</tbody></table></div></details>
    <p className="text-xs text-muted">{uiT("구성된 Gemini TTS 모델: ")}{uiT(ttsModel)}{uiT(". 실제 계정 이용·음성 생성은 별도 확인이 필요합니다.")}</p>
    <p className="text-sm text-warn">{uiT("필수 키: Gemini 사용자 키. 제품 영상형 fal.ai 비용: $0 (호출 없음). Gemini 대본·TTS 요금은 미확인으로 무료를 보장하지 않습니다. 로컬 컴퓨팅 비용 별도. 배우형은 fal.ai와 선택한 TTS 비용이 추가됩니다. 실패도 과금될 수 있으며 다른 유료 공급자로 자동 전환하지 않습니다.")}</p>
    <label className="block text-sm"><input type="checkbox" checked={rights} onChange={e => setRights(e.target.checked)} disabled={disabled} />{uiT(" 원본 영상·사진·음원의 사용 및 편집 권리를 확인했습니다.")}</label>
    <label className="block text-sm">{uiT("제품 영상·사진 업로드")}<LocalizedFileInput aria-label={uiT("제품 영상·사진 업로드")} multiple accept="video/mp4,video/webm,video/quicktime,image/png,image/jpeg,image/webp" disabled={!rights || disabled} onChange={e => upload([...e.target.files])} /></label>
    {scenes.map((scene, index) => <fieldset key={`${scene.asset_id}-${index}`} disabled={disabled} className="card p-3 space-y-2"><legend>{uiT("장면 ")}{uiT(index + 1)} · {uiT(scene.kind === 'video' ? '원본 영상' : '사진')}</legend>
      {!scene.preview && <button className="btn-ghost p-2" onClick={async () => { try { const response = await apiFetch(`/api/saasshorts/product/assets/${scene.asset_id}`); if (!response.ok) throw new Error('원본이 만료됐거나 접근 권한이 없습니다.'); const url = URL.createObjectURL(await response.blob()); urls.current.add(url); setScenes(old => old.map((item, i) => i === index ? { ...item, preview: url } : item)); } catch (e) { setError(e.message); } }}>{uiT("원본 미리보기 불러오기")}</button>}
      {scene.preview && (scene.kind === 'video' ? <video className="max-h-48" src={scene.preview} controls /> : <img className="max-h-48" src={scene.preview} alt={uiT(`장면 ${index + 1} 원본`)} />)}
      <label className="block">{uiT("실제 원본에 보이는 내용(추정 효과·가짜 사용 장면 금지)")}<input aria-label={uiT(`장면 ${index + 1} 내용`)} className={input} maxLength={400} value={scene.note} onChange={e => change(index, { note: e.target.value })} /></label>
      {scene.kind === 'video' ? <div className="flex gap-2"><label>{uiT("시작(초)")}<input aria-label={uiT(`장면 ${index + 1} 시작`)} type="number" min={0} max={scene.source_duration} step="0.1" value={scene.start} onChange={e => change(index, { start: Number(e.target.value) })} /></label><label>{uiT("끝(초)")}<input aria-label={uiT(`장면 ${index + 1} 끝`)} type="number" min={0} max={scene.source_duration} step="0.1" value={scene.end} onChange={e => change(index, { end: Number(e.target.value) })} /></label></div> : <><label>{uiT("사진 시간 비중")}<input aria-label={uiT(`장면 ${index + 1} 사진 시간`)} type="number" min={1} max={15} value={scene.duration} onChange={e => change(index, { duration: Number(e.target.value) })} /></label><label>{uiT("사진 움직임")}<select aria-label={uiT(`장면 ${index + 1} 움직임`)} value={scene.motion} onChange={e => change(index, { motion: e.target.value })}><option value="none">{uiT("없음")}</option><option value="zoom">{uiT("확대")}</option><option value="pan">{uiT("팬")}</option></select></label></>}
      <label>{uiT("9:16 크롭 위치")}<select aria-label={uiT(`장면 ${index + 1} 크롭`)} value={scene.crop} onChange={e => change(index, { crop: e.target.value })}><option value="center">{uiT("가운데")}</option><option value="left">{uiT("왼쪽")}</option><option value="right">{uiT("오른쪽")}</option></select></label>
      <button className="btn-ghost p-2" disabled={index === 0} onClick={() => { setScenes(old => { const next = [...old]; [next[index-1], next[index]] = [next[index], next[index-1]]; return next; }); setScript(null); }}>{uiT("위로 이동")}</button><button className="btn-ghost p-2" onClick={() => { setScenes(old => old.filter((_, i) => i !== index)); setScript(null); }}>{uiT("장면 제외")}</button>
    </fieldset>)}
    <label className="block">{uiT("확인된 상품 정보")}<textarea aria-label={uiT("확인된 상품 정보")} className={input} maxLength={4000} disabled={disabled} value={description} onChange={e => { setDescription(e.target.value); setScript(null); }} placeholder={uiT("확인된 사양·원화 가격만 입력하세요. 미확인 효능·할인율·후기를 만들지 않습니다.")} /></label>
    <div className="flex flex-wrap gap-4"><label>{uiT("장면 전환")}<select aria-label={uiT("장면 전환")} disabled={disabled} value={transition} onChange={e => setTransition(e.target.value)}><option value="fade">{uiT("페이드")}</option><option value="cut">{uiT("컷")}</option></select></label><label>{uiT("한국어 Gemini 음성")}<select aria-label={uiT("제품형 한국어 음성")} disabled={disabled} value={voice} onChange={e => setVoice(e.target.value)}><option>{uiT("Kore")}</option><option>{uiT("Puck")}</option></select></label></div>
    <label className="block">{uiT("권리 확인된 배경음 업로드(선택)")}<LocalizedFileInput aria-label={uiT("배경음 업로드")} accept="audio/mpeg,audio/wav,audio/mp4,audio/ogg" disabled={!rights || disabled} onChange={e => e.target.files[0] && upload([e.target.files[0]], true)} /></label>
    {music && <div><span>{uiT("배경음 선택됨")}</span><label>{uiT("배경음 음량")}<input aria-label={uiT("배경음 음량")} type="range" min={0} max={.4} step={.01} value={musicVolume} disabled={disabled} onChange={e => setMusicVolume(Number(e.target.value))} /></label><button className="btn-ghost" disabled={disabled} onClick={() => setMusic(null)}>{uiT("배경음 없음")}</button></div>}
    {script && <label className="block">{uiT("한국어 내레이션 검토·수정")}<textarea aria-label={uiT("한국어 내레이션")} className={input} value={script.full_narration} maxLength={1200} disabled={disabled} onChange={e => { setScript({ ...script, full_narration: e.target.value }); setContent(false); }} /></label>}
    <label className="block"><input type="checkbox" checked={paid} disabled={disabled} onChange={e => setPaid(e.target.checked)} />{uiT(" 이번 Gemini 유료 요청의 비용·요금 미확인·실패 시 과금 가능성을 확인하고 실행에 동의합니다.")}</label>
    {script && <label className="block"><input type="checkbox" checked={content} disabled={disabled} onChange={e => setContent(e.target.checked)} />{uiT(" 원본과 대본을 검토했으며 상품 효능·사용 장면·가격·후기를 임의로 꾸미지 않았습니다.")}</label>}
    <div className="flex flex-wrap gap-3"><button className="btn-primary p-3" disabled={disabled || !rights || !paid || !scenes.length} onClick={() => submit('analyze')}>{uiT("제품 대본 생성")}</button><button className="btn-primary p-3" disabled={disabled || !rights || !paid || !content || !script} onClick={() => submit('generate')}>{uiT("제품 MP4 제작")}</button></div>
    {pending && <p role="status">{uiT("요청 ")}{uiT(pending.request_id)}{uiT(" · 접수/대기/진행 상태 확인 중. 페이지 새로고침 시 조회만 재개합니다.")}</p>}
    {status && <div aria-live="polite"><p>{uiT("상태: ")}{uiT(status.state)}</p>{status.logs?.map((log, i) => <p key={i}>{<LocalizedDiagnostic value={log} />}</p>)}</div>}
    {error && <p role="alert" className="text-warn">{<LocalizedDiagnostic value={error} error />}</p>}
    {video && <div><video aria-label={uiT("제품 쇼츠 미리보기")} className="max-h-96 max-w-full" src={video} controls /><a className="btn-primary p-3 inline-block" href={video} download="product-short.mp4">{uiT("MP4 다운로드")}</a></div>}
    {pending && <div className="text-xs text-muted"><p>{uiT("응답 유실 시 자동 재전송하지 않습니다. 서버에 작업이 없음을 관리자가 확인하기 전에는 새 요청을 만들지 마세요.")}</p><button className="btn-ghost p-2" onClick={() => { if (window.confirm(uiT('관리자가 서버에서 이 작업이 실행 중이 아니며 중복 과금 위험이 없음을 확인했습니까?'))) { write(PENDING, null); setPending(null); lock.current = false; } }}>{uiT("서버 확인 후 제출 잠금 해제")}</button></div>}
  </section>;
}
