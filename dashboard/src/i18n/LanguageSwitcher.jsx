import { getUiLocale, setUiLocale, t, useUiLocale } from './runtime.js';
export default function LanguageSwitcher() {
  useUiLocale();
  return <label className="inline-flex items-center gap-1 text-xs text-muted shrink-0"><span className="sr-only">{t('Interface language')}</span><select aria-label={t('Interface language')} value={getUiLocale()} onChange={event => setUiLocale(event.target.value)} className="max-w-28 rounded-input border border-rule bg-paper px-2 py-1.5 text-ink normal-case"><option value="ko-KR">한국어</option><option value="en-US">English</option></select></label>;
}
