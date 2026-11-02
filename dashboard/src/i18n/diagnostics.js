import { getUiLocale, t } from './runtime.js';
export function diagnosticSummary(value, error = false) {
  const text = String(value ?? '');
  const translated = t(text);
  if (getUiLocale() === 'en-US') return translated === text && /[가-힣]/.test(text) ? t(error ? 'Request failed' : 'Technical log') : translated;
  if (translated !== text || /[가-힣]/.test(text) || !/[A-Za-z]{3}/.test(text)) return translated;
  if (error || /error|fail|exception/i.test(text)) return t('Request failed');
  const stages = [ [/quota|429/i, 'Quota limit reached'], [/whisper|transcrib/i, 'Transcribing audio'],
    [/subtitle|caption/i, 'Preparing subtitles'], [/download|yt-dlp/i, 'Downloading source'],
    [/b.?roll/i, 'Preparing b-roll'], [/actor|hailuo|kling|lipsync/i, 'Preparing actor video'],
    [/tts|voiceover|audio/i, 'Preparing voiceover'], [/render|composit|ffmpeg/i, 'Rendering video'],
    [/analy|gemini/i, 'Analyzing video'], [/queue|waiting/i, 'Waiting in queue'],
    [/complete|success|ready|finished/i, 'Completed'], [/upload/i, 'Uploading'], [/start/i, 'Starting'] ];
  return t(stages.find(([pattern]) => pattern.test(text))?.[1] || 'Technical log');
}
