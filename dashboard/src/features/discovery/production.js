import { errorMessage } from './strings.js';

export const PENDING_PRODUCTION_KEY = 'openshorts_discovery_pending_submission';

export function readPendingProduction() {
  try { return JSON.parse(sessionStorage.getItem(PENDING_PRODUCTION_KEY) || 'null'); }
  catch { return null; }
}

export function rememberProduction(source) {
  try { sessionStorage.setItem(PENDING_PRODUCTION_KEY, JSON.stringify({ source, started_at: new Date().toISOString() })); }
  catch { /* The in-memory submission lock still applies when storage is unavailable. */ }
}

export function clearPendingProduction() {
  try { sessionStorage.removeItem(PENDING_PRODUCTION_KEY); } catch { /* best effort */ }
}

export function knownProductionRejection(code) {
  return ['provider_not_configured', 'discovery_disabled', 'discovery_configuration_error',
    'discovery_storage_unavailable', 'provider_unavailable', 'provider_timeout',
    'provider_access_denied', 'provider_rate_limited', 'invalid_provider_response',
    'local_quota_exceeded', 'youtube_quota_exceeded'].includes(code);
}

export function buildProductionData(video, options, rightsConfirmed, downloadConfirmed) {
  if (!rightsConfirmed || !downloadConfirmed) throw new Error('이용 권리와 다운로드 허용 여부를 각각 확인해 주세요.');
  if (!/^[A-Za-z0-9_-]{11}$/.test(video.video_id) || video.url !== `https://www.youtube.com/watch?v=${video.video_id}` || video.license !== 'creativeCommon') throw new Error('원본 ID·URL·라이선스를 확인할 수 없습니다. 다시 검색해 주세요.');
  if (Number.isNaN(new Date(video.metadata_fetched_at).getTime())) throw new Error('원본 정보 확인 시각이 없습니다. 다시 검색해 주세요.');
  if (options.targetClips && !['1', '2', '3', '4', '5'].includes(String(options.targetClips))) throw new Error('목표 쇼츠 수는 1~5개입니다.');
  if (options.maxSeconds && !['30', '60'].includes(String(options.maxSeconds))) throw new Error('최대 길이는 30초 또는 60초입니다.');
  if (options.autoHook != null && !['', '0', '1'].includes(options.autoHook)) throw new Error('후킹 옵션을 확인해 주세요.');
  return {
    type: 'url', payload: video.url, acknowledged: true, outputFormat: 'vertical', layout: 'auto',
    targetClips: options.targetClips ? Number(options.targetClips) : null,
    clipMinSeconds: options.maxSeconds ? 15 : null, clipMaxSeconds: options.maxSeconds ? Number(options.maxSeconds) : null,
    autoHook: options.autoHook == null || options.autoHook === '' ? null : options.autoHook === '1',
    discoverySource: {
      video_id: video.video_id, url: video.url, title: video.title, channel_title: video.channel_title,
      license: video.license, metadata_fetched_at: video.metadata_fetched_at, download_authorized: true,
    },
  };
}

export function productionError(raw) {
  let detail = raw;
  try { detail = JSON.parse(String(raw)).detail; } catch { /* ordinary error text */ }
  const code = detail?.code;
  const known = {
    invalid_discovery_source: '원본 정보가 올바르지 않습니다. 다시 검색해 선택해 주세요.',
    download_not_confirmed: '다운로드 허용 여부를 별도로 확인하거나 적법하게 보유한 파일을 업로드해 주세요.',
    source_license_changed: '원본 라이선스가 변경되었거나 확인되지 않습니다. 다시 검색하고 권리를 확인해 주세요.',
    source_unavailable: '원본이 삭제·비공개·라이브 상태이거나 정보를 확인할 수 없습니다. 다시 검색하거나 보유 원본을 업로드해 주세요.',
  };
  if (known[code]) return known[code];
  if (code) return errorMessage(code);
  const message = String(typeof detail === 'string' ? detail : detail?.message || raw || '');
  if (/Missing X-Gemini|GEMINI_API_KEY|api key.*missing/i.test(message)) return '제작용 Gemini 키 또는 로컬 LLM이 설정되지 않았습니다. 설정에서 제작 키를 입력하거나 서버의 로컬 LLM을 구성해 주세요.';
  if (/URL ingest is disabled|URL.*disabled/i.test(message)) return '이 서버는 YouTube URL 처리를 허용하지 않습니다. 보호 기능을 우회하지 말고 적법하게 보유한 원본을 Clip Generator에서 업로드해 주세요.';
  if (/too short|shorter|only \d+s long|needs at least|at least.*seconds|minimum.*seconds/i.test(message)) return '원본 영상 길이가 제작 기준보다 짧습니다. 더 긴 원본을 선택해 주세요.';
  if (/ffmpeg|encoder|moov atom/i.test(message)) return 'FFmpeg 영상 처리에 실패했습니다. 로그와 서버 환경을 확인해 주세요.';
  if (/expired|missing.*files|files.*missing/i.test(message)) return '일부 결과 파일이 만료되었거나 없습니다. 사용 가능한 부분 결과만 표시합니다.';
  if (/download|yt-dlp|private|removed|unavailable|403|bot/i.test(message)) return '원본 다운로드에 실패했거나 접근이 허용되지 않습니다. 제한을 우회하지 말고 적법하게 보유한 파일을 업로드해 주세요.';
  return message.slice(0, 300) || '제작 요청을 완료하지 못했습니다. 서버 상태를 확인해 주세요.';
}
