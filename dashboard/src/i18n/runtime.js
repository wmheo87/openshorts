import { useSyncExternalStore } from 'react';
import { messages } from './messages.js';
export const UI_LOCALE_KEY = 'openshorts_ui_locale';
export const UI_LOCALES = ['ko-KR', 'en-US'];
const subscribers = new Set();
function initialLocale() {
  try { const saved = localStorage.getItem(UI_LOCALE_KEY); if (UI_LOCALES.includes(saved)) return saved; } catch { /* private mode */ }
  return 'ko-KR';
}
let locale = initialLocale();
export function getUiLocale() { return locale; }
export function setUiLocale(next) {
  if (!UI_LOCALES.includes(next)) return;
  locale = next;
  try { localStorage.setItem(UI_LOCALE_KEY, next); } catch { /* keep session selection */ }
  if (typeof document !== 'undefined') document.documentElement.lang = next;
  subscribers.forEach(listener => listener());
}
export function useUiLocale() { return useSyncExternalStore(listener => { subscribers.add(listener); return () => subscribers.delete(listener); }, getUiLocale, () => 'ko-KR'); }
if (typeof document !== 'undefined') document.documentElement.lang = locale;
if (typeof window !== 'undefined') window.addEventListener('storage', event => {
  if (event.key !== UI_LOCALE_KEY) return;
  locale = UI_LOCALES.includes(event.newValue) ? event.newValue : 'ko-KR';
  document.documentElement.lang = locale; subscribers.forEach(listener => listener());
});
const normalized = text => text.replace(/\s+/g, ' ').trim();
const folded = new Map(Object.keys(messages).map(key => [key.toLowerCase(), key]));
const patterns = Object.keys(messages).filter(key => /\{\d+\}/.test(key)).map(key => {
  const parts = key.split(/(\{\d+\})/); const indexes = [];
  const pattern = parts.map(part => { if (/^\{\d+\}$/.test(part)) { indexes.push(part); return '([\\s\\S]*?)'; } return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/ /g, '\\s+'); }).join('');
  return { key, indexes, regex: new RegExp('^'+pattern+'$') };
});
export function translateForLocale(value, target = locale) {
  if (typeof value !== 'string' || !value.trim()) return value;
  const key = normalized(value);
  const actual = messages[key] ? key : folded.get(key.toLowerCase());
  let translated;
  if (actual) translated = messages[actual][target] ?? key;
  else for (const entry of patterns) {
    const match = entry.regex.exec(value.trim()); if (!match) continue;
    translated = (messages[entry.key][target] ?? entry.key).replace(/\{\d+\}/g, token => {
      const index = entry.indexes.indexOf(token); return index < 0 ? token : match[index+1];
    }); break;
  }
  if (translated === undefined) return value;
  return (value.match(/^\s+/)?.[0] || '') + translated + (value.match(/\s+$/)?.[0] || '');
}
export const t = translateForLocale;
export function formatUiDate(value, options = {}) {
  const date = new Date(value); if (Number.isNaN(date.getTime())) return t('Unknown date');
  return new Intl.DateTimeFormat(locale, { ...(locale === 'ko-KR' ? { timeZone: 'Asia/Seoul' } : {}), ...options }).format(date);
}
export function formatUiMoney(value, currency = 'USD') {
  return new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: currency === 'KRW' ? 0 : 2 }).format(value);
}
