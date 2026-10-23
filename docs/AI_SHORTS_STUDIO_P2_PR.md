# PR 제목

feat: add Video Discovery dashboard for P1 search API

## 변경 내용

키워드로 영상을 찾고 비교할 화면이 없던 기존 대시보드에 opt-in `Video Discovery` 탭을 추가합니다. P1 검색/이력 API를 기존 apiFetch로 연결하고, 한·영·일 검색어, 조회수·길이·날짜·결과 수 필터, 점수/조회수/최신순 정렬, 영상 카드·선택 상세·권리 안내·검색 이력 재실행을 제공합니다.

날짜는 브라우저 시간대의 달력 경계를 ISO UTC로 변환해 종료일 전체를 포함합니다. 과거 검색 재실행은 원본 ISO 경계를 보존합니다. CC BY는 고정 조건이며 자체 점수는 바이럴 확률이 아닙니다. 선택과 권리 검토 체크는 화면 상태로만 유지하며 서버 영속화·영상 생성·다운로드를 요청하지 않습니다.

UI는 `dashboard/src/features/discovery/`로 분리하고 기존 activeTab/navItems와 디자인 토큰을 유지합니다. 모바일에는 드로어 메뉴만 추가합니다. Gemini/Upload-Post 키 경고는 필요 없는 새 탐색 화면에서만 숨기고 기존 화면에서는 유지합니다.

`VITE_DISCOVERY_ENABLED=1`로 UI를 활성화합니다. Vite의 구체적인 `/api/discovery` 프록시는 선택적 독립 P1 서비스로 보내고 나머지 `/api` 경로는 기존 백엔드에 유지합니다. Docker UI override, production build arg, 환경 예제, 실행 안내 및 CI 테스트를 추가합니다. 프런트엔드에서 YouTube 키를 보관하지 않으며 서버의 기능/키 검사를 우회하지 않습니다.

## 검증

- Node 유틸리티/실제 Vite HTTP 프록시 테스트: **7 passed**.
- Chromium desktop/Pixel 7 모바일 에뮬레이션: **40 passed**, 자동 재시도 없음. 렌더링·정확 요청·3개 언어·정렬·선택·원본 링크·이력·빈 결과·오류·시간 초과·취소·텍스트 안전성·뷰포트 넘침·기존 메뉴·UI off를 검증했습니다.
- UI 활성 production build 성공; 변경 JS 대상 ESLint 성공.
- 전체 lint는 기존 기준선과 동일한 **10 errors**로 실패했습니다: `public/op1.js` 5, `Legal.jsx` 1, `PricingPage.jsx` 1, `lib/consent.js` 3. 신규 lint 오류는 없습니다.
- 전체 백엔드: **1,291 passed / 29 skipped / 8 failed**. P0/P1부터 있던 직접 DNS 의존 실패이며 기존 테스트·보안 검사를 바꾸지 않았습니다.
- 실제 전체/독립 FastAPI의 이력 HTTP 응답 및 config 라우팅, Compose 설정 병합, `git diff --check` 검증 성공.

## 범위 및 제한

P0/P1이 병합된 `main` `672e5d4`에서 분기했으며 이전 커밋을 중복 추가하지 않습니다. P1 Python 모듈·기존 영상 엔진·cloud/·인증·사용량·결제·업로드·TTS는 수정하지 않았습니다. 신규 개발 의존성은 Playwright 테스트 도구이며 runtime dependency는 추가하지 않았습니다.

실 YouTube 검색은 서버 키로 별도 확인해야 합니다. Windows Docker Desktop/실제 모바일 기기와 production reverse proxy/전체 Docker 스택은 미검증입니다. 모바일 에뮬레이션 결과를 해당 환경의 검증으로 간주하지 않습니다. 제작/프로젝트 영속화는 이후 P3 범위이며 이번 PR에는 포함하지 않습니다.

설치·실행·API 연결·결과 상세: [STUDIO_DISCOVERY_UI.md](STUDIO_DISCOVERY_UI.md).
