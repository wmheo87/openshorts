# 한국어 쇼핑 쇼츠 — Gemini TTS 선택 경로 (후속 PR)

기존 한국어 지원 커밋 `7c71184083ddf955b2373d56b60b0bde409d1afa`를 수정하지 않고 그 위의 `feature/korean-gemini-tts` 브랜치에 분리했다. 기존 PR을 먼저 병합하고 후속 PR을 main으로 변경하는 순서다. 기존 브랜치는 그대로 보존한다. 기존 한국어 지원의 자동 PR 생성은 GitHub Forbidden 오류로 차단된 상태이며, Push된 브랜치와 수동 PR 생성 링크가 준비되어 있다.

## 모델 검증 상태

요청한 `gemini-3.8-flash-lite-tts`를 기본 모델 문자열로 설정했다. **이 모델의 실제 존재·계정 이용 가능 여부·요금·무료 할당량·한국어 합성 성공은 확인하지 못했다.** 공식 Google 문서 접근은 환경 프록시에서 403 Forbidden이었으며 실제 API 키도 없었다. 모델이 존재한다고 단정하거나 비슷한 다른 모델로 자동 대체하지 않는다.

기존 고정 의존성 google-genai==1.75.0과 현재 개발 환경 2.33.0에서 GenerateContentConfig/SpeechConfig/VoiceConfig/PrebuiltVoiceConfig를 사용한 실제 SDK HTTP 직렬화·응답 파싱 테스트가 통과했다. SDK 호환성과 특정 모델의 실서비스 지원 여부는 별개다.

실행 시 `/api/saasshorts/tts-model`이 해당 사용자 키로 models.get을 호출한다. 모델 조회와 generateContent 지원을 확인하기 전에는 버튼을 활성화하지 않으며 생성 API에서도 다시 검사한다. 조회 성공 응답에도 `audio_synthesis_verified: false`를 유지한다. 카탈로그 조회만으로 AUDIO 출력·한국어 발음·음성명 사용 가능 여부까지 증명할 수 없으며 실제 합성은 별도 확인 대상이다. 카탈로그/권한/할당량 문제가 있으면 제작을 접수하지 않는다.

운영자가 실제 계정에서 확인한 모델이 다르면 `GEMINI_TTS_MODEL` 환경변수로 명시적으로 변경할 수 있다. 이것은 사용자가 선택하는 설정이며 자동 fallback이 아니다. 확인할 공식 자료:

- https://ai.google.dev/gemini-api/docs/speech-generation
- https://ai.google.dev/gemini-api/docs/models
- https://ai.google.dev/gemini-api/docs/pricing

## 사용자 흐름과 키

한국어 새 작업의 기본 공급자는 Gemini TTS이며 Configure Video에서 ElevenLabs로 명시적으로 변경할 수 있다. 영어·스페인어 기본 경로와 기존 ElevenLabs 한국어 음성 확인·미리듣기는 유지한다. Gemini 음성은 Kore/Puck prebuilt voice 설정을 제공하되 실계정 합성은 미검증임을 안내한다. 미리듣기용 유료 합성을 자동 호출하지 않는다.

Gemini 선택 시 ElevenLabs 키·음성 ID가 필수가 아니며 ElevenLabs API를 호출하지 않는다. Gemini 키는 기존 Settings의 Gemini 키를 X-Gemini-Key 헤더로 보내고 self-host에서는 GEMINI_API_KEY 환경변수도 사용할 수 있다. fal.ai 키는 기존대로 필요하다.

호스팅 환경에서도 TTS는 사용자 키를 사용하는 BYOK이다. 기존 managed 과금 키나 플랜 크레딧을 새 TTS에 임의 사용하지 않는다. 기존 entitlement 검사는 유지하고 cloud/나 과금 구조는 변경하지 않았다. 기존 분석용 managed Gemini 동작과 TTS용 사용자 키는 구분한다.

```json
{
  "script": {"language": "ko", "title": "상품 안내", "full_narration": "상품 정보와 현재 가격을 확인해 주세요"},
  "tts_provider": "gemini",
  "gemini_voice": "Kore",
  "video_mode": "lowcost"
}
```

기존 `/api/saasshorts/generate`에 위 선택 필드만 추가했다. 공급자를 생략하면 한국어는 Gemini, en/es는 ElevenLabs를 사용한다. 기존 한국어 ElevenLabs 클라이언트는 `tts_provider: "elevenlabs"`를 명시하면 기존 동작을 유지한다. Gemini의 영어/스페인어 합성은 이번 범위에 포함하지 않고 명확히 거부한다.

## 음성·영상 연결과 실패

한국어 대본 → GenAI AUDIO → inline PCM/검증된 WAV → mono WAV → FFmpeg MP3 → 기존 fal.ai Low Cost/Premium 립싱크 → 기존 한국어 Whisper/ASS → MP4를 재사용한다. PCM의 MIME, 명시된 샘플레이트, 길이를 검사하고 비정상·빈 응답이나 변환 실패를 오류로 처리한다.

Gemini 음성은 fal.ai 배우 이미지 생성보다 먼저 생성한다. TTS가 실패하면 fal.ai 작업과 ElevenLabs를 호출하지 않는다. SDK synthesis 재시도는 1회 요청으로 제한하며 타임아웃이나 공급자 오류 후 다른 유료 API로 전환하지 않는다. 사용자 명시적 재시도는 별도 요청이므로 비용 발생 가능성을 확인해야 한다.

Gemini 캐시 파일명에는 모델·음성·대본의 hash를 포함해 기존 ElevenLabs 음성/입 모양이나 다른 Gemini 음성을 잘못 재사용하지 않는다. 키는 hash·파일명·출처 파일·로그에 저장하지 않는다.

요금표를 확인하지 못했으므로 Gemini TTS 예상 비용은 **요금 미확인(0원 보장 아님)**으로 표시한다. fal.ai의 기존 항목별 추정과 분리하고, 결과의 Gemini 비용/전체 합계는 null이며 known_subtotal만 숫자로 제공한다. 실패도 과금될 수 있음을 오류에 포함한다. ElevenLabs 구독이 필요 없다는 것이 전체 영상 제작이 무료라는 뜻은 아니다.

## 검증 (2026-11-02, 한국 시간)

외부 유료 API는 모두 mock이며 실제 Gemini·ElevenLabs·fal.ai 합성 호출은 0회다.

- 신규 Gemini 백엔드 15개 + 기존 한국어/ElevenLabs 31개: **46 통과**
- SDK 1.75.0을 별도 경로에 설치한 동일 Gemini 테스트: **15 통과** (의존성 핀 변경 없음)
- 전체 Python: **1358 통과, 29 건너뜀, 기존 DNS/URL 보안 관련 8 실패**
- Playwright 데스크톱/모바일: **94 통과** (기존 Discovery/Clip Generator 80개, ko/en/es/ElevenLabs 및 Gemini 14개)
- Node 유틸리티 12개, production build, 변경 영역 ESLint: 통과
- HTTP MockTransport로 실제 SDK JSON/응답을 사용하고 합성 무음 PCM을 실제 FFmpeg로 WAV/MP3로 변환했다. 이것은 한국어 발화나 실제 유료 합성 검증이 아니다.

신규 테스트는 모델 미존재/권한/할당량 오류, 단일 합성 요청, 자동 fallback 금지, 비정상 오디오 거부, ElevenLabs 키 없는 접수, managed 키 미사용, 두 립싱크 연결, 한글 자막, 미확인 요금, 기본 공급자와 UI 요청/차단을 확인한다. 기존 테스트를 비활성화하지 않았다. 브라우저·asyncio 테스트는 환경의 로컬 소켓 제한 때문에 허용된 샌드박스 밖에서 실행했다. 원격 CI 성공은 아직 확인하지 않았다.

```bash
.venv/bin/python -m pytest tests/test_gemini_tts.py tests/test_saasshorts_korean.py -q
.venv/bin/python -m pytest tests/ -q
cd dashboard
npm run test:unit
npm run test:discovery
VITE_DISCOVERY_ENABLED=1 npm run build
npx eslint src/components/SaaShortsTab.jsx src/components/AdvancedBanner.jsx src/App.jsx tests/discovery/korean-shorts.spec.js --max-warnings 0
```

## 남은 수동 검증

1. API 키를 보안 설정에 넣고 요청 모델의 실제 계정 조회·AUDIO 지원·지원 음성·요금/무료 할당량을 확인한다. 현재 모델명이 유효하지 않다면 운영자가 확인한 모델명을 명시적으로 설정해야 하며, 검증 전 기본 모델이 동작한다고 가정하지 않는다.
2. 비용을 확인하고 소량의 한국어 합성을 명시적으로 실행해 발음·원화/숫자·브랜드명·샘플레이트를 확인한다.
3. Low Cost/Premium 각각 실제 음성으로 입 모양·컷 타이밍·Whisper 정확도·ASS 싱크·최종 MP4 재생을 검수한다.
4. 공급자 실패·응답 유실 후 청구 여부와 재시도 비용을 계정 콘솔에서 확인한다.
5. 전체 Docker 이미지/Windows, 실제 한국어 상품 사실성과 광고 고지를 검증한다.

실영상 검증 없이 한국어 립싱크가 정상이라고 단정하지 않는다. 기존 한국어 지원 문서의 실제 음성·Windows 미검증 사항도 그대로 유효하다.
