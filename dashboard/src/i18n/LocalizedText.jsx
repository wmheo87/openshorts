import { t, useUiLocale } from './runtime.js';
// Module-level JSX constants must translate when rendered, not when imported.
export default function LocalizedText({ value }) {
  useUiLocale();
  return t(value);
}
