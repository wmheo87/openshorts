# AI Shorts: 한국어(ko-KR) 실물 상품 쇼핑 쇼츠

기준 main: `a5ebe00464b0746d5bb81c51c19782d219a93325` (P3 병합 포함).
브랜치: `feature/korean-shopping-shorts`. main 직접 커밋·자동 병합은 하지 않는다.

## 변경과 사용 방법

- AI Shorts의 새 작업 기본 언어는 한국어(ko)이다. English와 Español, 기존 UGC/Before/After 등 스타일, Low Cost/Premium을 유지한다. 기존 캐시 작업은 저장된 대본 언어를 복원하며, 언어 필드 없는 옛 캐시는 기존 영어 작업으로 취급한다.
- 상품 URL 또는 확인된 상품 설명을 입력하고 대본을 생성한다. 한국어 URL 입력은 기존 SSRF 보호가 있는 스크래퍼를 재사용하지만 해외 SaaS 전용 리서치·분석 프롬프트는 사용하지 않는다. 판매 페이지 원문을 대본의 참고 데이터로 보존한다.
- 한국어 제목·내레이션·후킹·자막·캡션·해시태그를 요청한다. 원화 가격은 입력에 명시된 금액만 사용하며 외화 환산 가격, 확인되지 않은 효과·후기·성능·할인율·사용 경험을 만들어내지 않도록 지시한다. CTA는 판매 페이지의 상품 정보·현재 가격 확인 안내를 사용하고 링크 위치·제휴 관계를 가정하지 않는다. Before/After에도 동일한 사실성 지시를 적용한다.
- 상품 원문은 독립적인 사실 검증 결과가 아니다. 생성 모델의 지시 준수가 자동 보장되는 것은 아니므로 게시 전 상품 외형·효과·가격·광고/제휴 고지를 검토해야 한다.
- 배우 설명과 b-roll 설명만 기존 영상 모델에 필요한 영어를 유지한다. 한국어 프롬프트에는 기존 유럽인 외모 고정 지시나 해외 SaaS 예시를 보내지 않는다.

Settings의 기존 Gemini, ElevenLabs, fal.ai 키 입력 경로를 사용한다. 키는 저장소나 프런트엔드 빌드 환경변수에 넣지 않는다. 새 TTS 공급자나 배포·과금 구조는 추가하지 않았다.

## 음성 선택과 미리듣기

기존 `/api/saasshorts/voices`가 실제 계정의 ElevenLabs 목록을 조회한다. 응답에 한국어 지원 메타데이터와 한국어 샘플 URL을 추가한다.

- labels.language/accent가 ko/ko-KR/korean/한국어이거나 verified_languages에 한국어가 있는 음성만 한국어 후보로 표시한다.
- verified_languages의 한국어 preview_url을 우선 사용한다. 언어 라벨이 한국어인 음성은 해당 음성의 preview_url도 사용한다. 한국어임을 확인하지 못한 일반 영어 샘플은 한국어 미리듣기로 표시하지 않는다.
- 후보는 사용자가 직접 선택한다. 기존 영어 기본 음성으로 자동 대체하지 않는다. 계정 조회 실패·기본 목록 응답·한국어 메타데이터 없음이면 안내하고 생성 버튼을 비활성화한다.
- HTML audio 컨트롤로 공급자 샘플을 미리듣는다. 한국어 샘플 URL이 없거나 로딩에 실패하면 명확히 안내한다. 라이브러리·키를 바꾼 뒤에는 페이지를 새로고침해 목록을 다시 조회할 수 있다.
- 생성 API도 유료 작업 시작 전에 계정 음성 목록을 새로 확인하여 선택 ID의 한국어 메타데이터와 계정 가용성을 검사한다. 프런트엔드 값만 믿지 않는다. 기존 entitlement, API 키, 소유자, URL/출력 경로 검사 등은 유지한다.

메타데이터는 발음·음질·립싱크를 실제 검수했다는 의미가 아니다. 메타데이터가 없는 커스텀 음성은 한국어로 말할 수 있더라도 안전하게 후보에서 제외된다. 계정별 실제 음성 목록·권한·샘플은 별도 실계정 확인이 필요하다.

## API와 제작 경로

`POST /api/saasshorts/analyze`는 ko, ko-KR, en, es를 허용한다. 기존 API 클라이언트의 생략 기본값은 en으로 유지한다. ko-KR은 ko로 정규화하고 서버가 각 대본의 language를 기록한다.

```json
{
  "description": "스테인리스 텀블러, 판매 페이지에 명시된 가격 12000원",
  "language": "ko",
  "num_scripts": 3,
  "style": "ugc",
  "actor_gender": "female"
}
```

`POST /api/saasshorts/generate`는 기존 script와 voice_id를 사용한다. 한국어 script에는 `language: "ko"`가 보존되고 voice_id는 실제 계정에서 확인한 ID를 명시해야 한다. FAL/ElevenLabs 헤더 검사는 유지하며 기본 음성 미지정·한국어 미확인 음성은 작업 생성 전에 400, 조회 예외는 503을 반환한다. 새 언어 전용 제작 엔진은 없다.

기존 eleven_multilingual_v2 TTS와 Low Cost(Hailuo + VEED)/Premium(Kling Avatar) 경로에 선택 음성과 내레이션을 전달한다. 한국어는 유럽 언어용 Parakeet을 거치지 않고 기존 Whisper 런타임을 language=ko와 단어 타임스탬프로 호출한다. 완료·실패 시 모델 해제는 finally로 유지한다. 다른 Clip Generator의 전사 설정이나 전역 환경은 변경하지 않는다.

ASS는 실제 음성의 단어 타임스탬프를 사용한다. 한국어에는 Noto Sans CJK KR, 76pt와 최대 16자 단위 줄바꿈을 적용하며 en/es의 Arial Black·대문자 스타일은 유지한다. Docker에 fonts-noto-cjk를 추가했다. Docker 외 환경에는 해당 폰트 설치가 필요하다. 샘플 렌더에서 한글 글리프와 줄바꿈은 확인했지만 실제 음성 길이·영상 컷·입 모양의 동기화와 모든 제품명/혼합 문자의 가독성은 실영상 검수가 필요하다.

## 검증 결과 — 2026-11-02 (한국 시간)

외부 Gemini·ElevenLabs·fal.ai 호출은 모두 mock이며 유료 생성은 실행하지 않았다.

| 검사 | 결과 |
|---|---|
| 한국어/영어/스페인어 Python 신규 테스트 | 31 통과 |
| Discovery P1~P3 백엔드 | 85 통과 |
| 기존 Discovery·Clip Generator 데스크톱/모바일 브라우저 | 80 통과 |
| 신규 한국어 선택·음성·요청 및 en/es 브라우저 | 10 통과 |
| 기존 Node 유틸리티·프록시 | 12 통과 |
| production build (Discovery 활성) | 통과 |
| 변경 프런트엔드/브라우저 테스트 ESLint | 통과 |
| 전체 Python | 1343 통과, 29 건너뜀, 기존 DNS 관련 8 실패 |
| 실제 FFmpeg/libass 한글 자막 샘플 렌더 | 통과: NotoSansCJKkr-Bold 선택, 글리프와 줄바꿈 시각 확인 |

전체 Python의 기존 실패는 test_partial_processing 2개, test_process_handover 1개, test_short_source_gate 4개, test_yt_clients 1개로 이전 P3 환경과 동일한 DNS/URL 보안 검사 관련 실패다. 보안 검사나 기존 테스트를 비활성화하지 않았다. 전체 테스트가 모두 통과한 상태는 아니다.

신규 테스트는 ko/ko-KR 정규화, Gemini 프롬프트, 언어 보존, 계정 음성 메타데이터·한국어 샘플 선택, 기본 영어 음성 거부, 키 검사, 공급자 오류, Whisper 타임스탬프·모델 해제, ASS UTF-8·폰트·줄바꿈과 Low Cost/Premium 전체 연결(mock)을 포함한다. 브라우저 테스트는 기존 Playwright 디렉터리 안에 두어 기존 CI에서 자동 수집한다. remote CI 성공은 별도 확인이 필요하다.

재현:

```bash
.venv/bin/python -m pytest tests/test_saasshorts_korean.py tests/studio/ -q
.venv/bin/python -m pytest tests/ -q
cd dashboard
npm run test:unit
npm run test:discovery
VITE_DISCOVERY_ENABLED=1 npm run build
npx eslint src/components/SaaShortsTab.jsx tests/discovery/korean-shorts.spec.js --max-warnings 0
```

현재 클라우드 브라우저 검증은 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium을 사용했다. 일반 환경/CI는 Playwright 브라우저 설치 후 실행한다.

## 남은 실영상 검증과 범위

- 실제 계정의 한국어 음성 목록·한국어 샘플 재생·eleven_multilingual_v2 합성 결과
- 한국어 숫자·원화·브랜드명 발음, 말 속도·문장 길이·컷 타이밍
- Low Cost와 Premium 각각의 한국어 입 모양·음성 동기화
- 실제 한국어 음성의 Whisper 인식 정확도, 자막 싱크와 혼합 문자 줄바꿈
- 실제 상품 외형·사실성·광고/제휴 고지 검수
- 수정된 전체 Docker 이미지 빌드·Windows 실행

API 키가 환경에 없으며 실계정 조회/합성/립싱크를 수행하지 않았다. 한국어 립싱크가 정상이라고 단정하지 않는다. 자막 샘플은 합성 배경 위 렌더로, 실물 상품 영상이나 AI 배우 영상 제작 검증이 아니다.

cloud/, 기존 배포·과금 코드, Discovery/Clip Generator 엔진은 수정하지 않았다. Gemini TTS 전환, SNS 소스 보관함 등 별도 기능과 자동 병합은 포함하지 않는다. 기본 MIT 라이선스 영역만 변경하며 별도 라이선스인 cloud/ 코드를 복사하지 않았다.
