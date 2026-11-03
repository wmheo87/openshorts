import { extraMessages } from './extra-messages.js';
import ko from './locales/ko-KR.js';
import en from './locales/en-US.js';
export const messages = { ...Object.fromEntries(Object.keys(ko).map(key => [key, { 'ko-KR': ko[key], 'en-US': en[key] }])), ...extraMessages };
