import test from 'node:test';
import assert from 'node:assert/strict';
import ko from '../src/i18n/locales/ko-KR.js';
import en from '../src/i18n/locales/en-US.js';
import { messages } from '../src/i18n/messages.js';
import { getUiLocale, setUiLocale, t, translateForLocale, formatUiDate, formatUiMoney } from '../src/i18n/runtime.js';
test('Korean default and navigation, independent supported UI locales', () => {
  assert.equal(getUiLocale(),'ko-KR');
  for(const [source,target] of [['Clip Generator','쇼츠 편집'],['AI Shorts','AI 쇼츠 제작'],['Video Discovery','영상 찾기'],['UGC Gallery','영상 보관함'],['YouTube Studio','유튜브 스튜디오'],['AI Agent','AI 에이전트'],['Settings','설정'],['History','작업 기록']]) assert.equal(t(source),target);
  setUiLocale('unsupported');assert.equal(getUiLocale(),'ko-KR');
  setUiLocale('en-US');assert.equal(t('Clip Generator'),'Clip Generator');assert.equal(t('영상 검색'),'Search videos');setUiLocale('ko-KR');
});
test('catalog parity and interpolation preserve meaningful values', () => {
  assert.deepEqual(Object.keys(ko).sort(),Object.keys(en).sort());
  const exceptions=new Set(['{0} star{1}','{0} scene{1} reframed by hand']);
  for(const [source,versions] of Object.entries(messages)) for(const value of Object.values(versions)) {
    assert.equal(typeof value,'string',source);
    for(const placeholder of source.match(/\{\d+\}/g)||[]) if(!(exceptions.has(source)&&placeholder==='{1}')) assert.ok(value.includes(placeholder),source+': '+placeholder);
  }
  assert.equal(t('Input: raw  title | Output: generated'),'입력: raw  title | 출력: generated');
  assert.equal(translateForLocale('임의 사용자 대본 — keep exactly','en-US'),'임의 사용자 대본 — keep exactly');
  assert.equal(t('gemini-3.8-flash-lite-tts'),'gemini-3.8-flash-lite-tts');
});
test('Korean dates and currencies format without exchange conversion', () => {
  assert.match(formatUiDate('2026-11-02T00:00:00Z'),/2026/);assert.match(formatUiMoney(12000,'KRW'),/12,000/);
  setUiLocale('en-US');assert.equal(formatUiMoney(12,'USD'),'$12.00');setUiLocale('ko-KR');
});
test('diagnostics retain actionable Korean provider messages and summarize English logs',async()=>{
  const {diagnosticSummary}=await import('../src/i18n/diagnostics.js');
  assert.equal(diagnosticSummary('YouTube API 키가 설정되지 않았습니다.',true),'YouTube API 키가 설정되지 않았습니다.');
  assert.equal(diagnosticSummary('ffmpeg encoder error',true),'요청을 완료하지 못했습니다.');
  assert.equal(diagnosticSummary('FFmpeg rendered'),'영상을 합성하는 중');
});
