import { t, useUiLocale } from './runtime.js';
import { diagnosticSummary } from './diagnostics.js';
export default function LocalizedDiagnostic({ value, error = false }) {
  useUiLocale();
  const raw = String(value ?? '');
  const summary = diagnosticSummary(raw, error);
  return <span className="break-words">{summary}{summary !== raw && <button type="button" className="ml-2 underline text-xs" onClick={() => window.alert(raw)}>{t('Technical details')}</button>}</span>;
}
