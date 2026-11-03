# 한국어 중심 UI / Korean-first interface

## 범위와 브랜치

`feature/korean-ui-i18n`은 원격 main `af7ef8338c042ddd07ae385d7bb4d1d7162e4119`에서 시작했다. 작업 중 원격 main을 다시 조회해 같은 SHA임을 확인했다. main에는 한국어 쇼핑 쇼츠 PR #5만 병합되어 있었고 Gemini TTS 및 제품 영상형은 없었다. 기존 작업을 잃지 않도록 다음 커밋을 별도 feature 브랜치에 보존했다.

- `760c356`: 기존 Gemini TTS 구현을 cherry-pick한 보존 커밋.
- `1c74bd4`: 기존 제품 영상형·영상 공급자 인터페이스를 cherry-pick한 보존 커밋.

따라서 main 대상 PR에는 이 두 선행 기능과 UI 현지화가 함께 포함된다. 기존 feature 브랜치는 변경하지 않았다. UI 현지화 작업 자체는 dashboard와 이 문서만 변경한다. `cloud/`, 기존 배포·과금 로직, API 경로·페이로드 키·DB·모델 ID를 변경하지 않는다. main에 직접 커밋하거나 자동 병합하지 않는다.

## 사용 방법과 구조

- 기본 UI 로케일: `ko-KR`. 화면 언어 선택에서 `en-US`로 전환한다.
- 마지막 선택만 `localStorage.openshorts_ui_locale`에 저장한다. 다른 설정 키와 저장 데이터는 그대로 유지한다.
- 지원하지 않는 저장값은 한국어로 처리한다. 로케일 저장이 불가능해도 i18n 모듈은 세션 내 선택을 유지한다. 기존 앱 전체의 localStorage 차단 환경 지원을 보장하는 것은 아니다.
- 문서의 `html.lang`을 변경하고 다른 탭의 storage 이벤트에도 반응한다. 로케일 변경은 컴포넌트를 강제로 다시 마운트하거나 제작 API를 호출하지 않는다.
- 쇼츠 대본·TTS의 `ko/en/es`는 각 제작 기능의 기존 상태로 관리한다. UI를 영어로 바꿔도 영상 언어·선택 음성·공급자·입력 URL은 바뀌지 않는다.

`dashboard/src/i18n/`:

| 파일 | 역할 |
| --- | --- |
| `runtime.js` | 로케일 저장, React 구독, 번역·보간, 날짜·통화 포맷 |
| `locales/ko-KR.js`, `locales/en-US.js` | 공통 번역 카탈로그. 기존 표시 문구를 키로 사용 |
| `extra-messages.js` | 동적 상태·진단·도움말 등 추가 문구 |
| `messages.js` | 카탈로그 통합 |
| `LanguageSwitcher.jsx` | 한국어/영어 선택 |
| `LocalizedText.jsx` | 모듈 수준 JSX 상수도 렌더 시점의 로케일로 표시 |
| `diagnostics.js`, `LocalizedDiagnostic.jsx` | 알려진 상태 번역, 알 수 없는 기술 오류의 안내와 원문 진단 표시 |
| `LocalizedFileInput.jsx` | 브라우저 기본 파일 버튼 대신 번역 가능한 업로드 버튼 |
| `passthrough.json` | 검수한 브랜드·코드·폰트 등 원문 유지 항목 |

정적 JSX, 버튼·모달·툴팁, placeholder, aria-label, alert/confirm, 처리 상태, 빈 상태, 검색/정렬, 편집·다운로드 안내를 렌더 시점에 번역한다. 사용자 영상 제목·채널명·검색어·생성 대본·인용문·자막 단어·해시태그는 번역 대상에서 제외한다. 템플릿의 `{0}` 등은 표시값 보간이며 HTML/eval을 사용하지 않는다. 새로운 문구는 양 언어 카탈로그에 추가하고 렌더 경계에서 `t`를 호출한다. API 요청 생성이나 상태 저장 시 번역하지 않는다.

## 변경 화면

쇼츠 편집(Clip Generator), AI 쇼츠 제작(제품 영상형/AI 배우형), 영상 찾기(Discovery), 영상 보관함(UGC Gallery), 유튜브 스튜디오, AI 에이전트, 설정, 작업 기록, 조건부 자동 제작(Autopilot), 결과 카드, 클립·화면 재구성·자막·후킹·더빙·예약 모달, 계정·로그인·요금제·쿠키 동의·온보딩·MCP 연결 도움말, 소개/법적 문서 안내 화면.

영문 공급자/모델 이름을 한국어로 바꾸지 않는다. 내부 `Low Cost/Premium` 값은 유지하고 표시 문구는 `저비용/프리미엄`으로 제공한다.

## 타이포그래피와 표시

- 한국어 UI에는 자체 호스팅 `OpenShorts Korean UI` 폰트를 우선 사용한다. Noto Sans CJK KR의 한글·자모·라틴·구두점 서브셋이며, 수정 폰트 이름과 SIL OFL 1.1 고지를 포함한다. 외부 폰트 API 요청이 없다.
- 재생성: fonttools가 설치된 개발 환경에서 `python dashboard/scripts/subset-korean-font.py /path/to/NotoSansCJK-Regular.ttc`. KR face index 1을 사용한다. 런타임 의존성은 추가하지 않는다.
- 한국어 줄바꿈·버튼 높이·탭 레이블을 조정한다. Playwright Chromium에서 1440×1000 및 Pixel 7 크기를 검증한다. 실제 iOS/Windows 디바이스 검증은 별도다.
- 날짜·숫자는 선택 로케일로 표시한다. 공통 날짜 포매터는 한국어에서 Asia/Seoul을 사용한다. Discovery의 날짜 필터 경계는 기존 안내대로 기기 시간대이며 게시 예약의 IANA 시간대도 유지한다. 예약 시간대 선택에는 Seoul을 추가했다.
- 원화는 소수점 없이 표시할 수 있다. 기존 USD 요금은 달러 통화를 유지하며 환율 변환하거나 원화 가격을 만들어내지 않는다.
- UI 폰트·로케일 설정을 Remotion 영상 자막 언어/폰트에 주입하지 않는다.

## 검증

실행 명령(저장소 루트 또는 명시한 dashboard 디렉터리):

```bash
cd dashboard
npm run test:unit
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:discovery -- --workers=3
npm run build
npm run lint
cd ..
.venv/bin/python -m pytest tests/studio tests/test_product_video.py tests/test_gemini_tts.py tests/test_saasshorts_korean.py -q
.venv/bin/python -m pytest -q
```

Windows에서는 Playwright가 설치한 Chromium을 사용하고 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`를 생략하거나 PowerShell 환경변수로 설정한다. 이 작업에서는 Linux Chromium만 실제 실행했다.

- 프런트 단위 테스트: 최종 16개 통과. 카탈로그 언어별 키, 보간값, 기본값·언어 전환, 원문 보존, 날짜·통화, 진단 문구 및 기존 Discovery 저장/필터 로직을 확인한다.
- 관련 백엔드 mock 회귀: 150개 통과. 외부 유료 API 호출 없음.
- 전체 백엔드: 1377개 통과, 29개 건너뜀, 기존 DNS/네트워크 전제 관련 8개 실패. `test_clip_persistence.py`, `test_short_source_gate.py`, `test_yt_clients.py`가 공개 YouTube URL DNS 검증에서 실패한다. URL 보안 검사를 완화하지 않았다. 동일 실패는 UI 작업 전 전체 테스트에도 있었다.
- 프런트 빌드: 통과. 기존 번들 크기 경고 및 선택적 OpenPanel 환경변수 누락 경고가 있다.
- 전체 린트: 기존 10개 오류가 남는다. 외부 minified `public/op1.js` 5개, `Legal.jsx`와 `PricingPage.jsx`의 JSX 아이콘 인자 unused 2개, 기존 `lib/consent.js` 3개. 이 작업에서 규칙을 끄거나 파일을 제외하지 않았다.
- Playwright 전체 110개 통과 (모바일·데스크톱, 약 2분 24초). 이후 영어 화면의 한글 잔여 문구 검사를 강화한 주요 화면 12개도 모두 통과했다. 주요 화면의 양 언어·가로 넘침, 언어 저장, 폼 상태 보존, 대본 언어 독립성, 원문 제목, Discovery 권리 확인·오류·이력, 중복 요청 방지, 한국어/영어/스페인어 제작 요청, 제품 영상 업로드·재개·미리보기·다운로드, 클립 편집기·자막 모달을 포함한다.

## 의도적으로 원문을 유지하는 영역과 수동 검증

- 사용자/생성 콘텐츠, 원본 메타데이터, API 키 이름·코드·URL·모델 ID·브랜드·공급자 음성 이름, 외부 서비스 화면, OS 파일 선택 창과 브라우저 네이티브 미디어 컨트롤.
- 기술 오류·서버 로그의 상세 원문은 명시적인 '진단 정보'로 제공한다. 알려진 오류와 기본 처리 안내는 현지화한다.
- `/terms`, `/privacy` 등 서버가 별도 제공하는 법적 원문, 정적 SEO/도구 가이드 페이지와 API/MCP 문서 자체는 이번 React UI 번역 범위 밖이다. React 법적 문서 안내·링크와 MCP 연결 UI는 번역한다. 법적 번역의 공인성을 주장하지 않는다.
- 실제 결제·OAuth·소셜 게시·유료 Gemini/fal.ai/ElevenLabs 제작은 실행하지 않았다. 계정별 모델 제공 여부·요금, 한국어 음성·립싱크·자막 타이밍과 실영상 품질, Windows/macOS/iOS 렌더링은 수동 확인이 남는다.
- `gemini-3.8-flash-lite-tts`의 실제 제공 여부·계정 사용 가능성·요금은 검증되지 않았다. 기존 확인 실패 차단 및 유료 공급자 자동 전환 금지를 유지한다.
