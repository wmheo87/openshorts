# AI Shorts Studio P2 — Video Discovery UI

## 범위

P0/P1이 병합된 `main` (`672e5d4e695199fc5f4ec42e6fd4f858a40ddf6b`)을 기준으로 기존 React 대시보드에 opt-in `Video Discovery` 메뉴를 추가했다. `activeTab`/`navItems`와 기존 Tailwind 색상·폰트·버튼을 재사용한다. 모바일에서는 전체 탐색 드로어에만 추가해 하단 탭 수를 늘리지 않는다.

P1 백엔드와 기존 편집 엔진은 수정하지 않는다. 프런트엔드는 YouTube 키를 읽거나 보관하지 않고 실제 제작·원본 다운로드·서버 프로젝트 저장을 요청하지 않는다. 선택 및 권리 검토 체크는 현재 화면의 React 상태일 뿐이다. 탭 이동/새로고침 시 사라질 수 있으며 영구적인 확인 기록이 아니다. P3 연결은 포함하지 않는다.

## 실행: 기존 전체 백엔드

1. 기존 백엔드 환경에서 `DISCOVERY_ENABLED=1`, `YOUTUBE_API_KEY`를 설정하고 재시작한다. 실제 키는 Git/프런트엔드/채팅에 넣지 않는다.
2. `dashboard/.env.example`을 참고해 ignored 파일 `dashboard/.env.local`을 만든다.

```dotenv
VITE_DISCOVERY_ENABLED=1
VITE_PROXY_TARGET=http://localhost:8000
```

3. `dashboard/`에서 `npm ci`, `npm run dev -- --host 127.0.0.1 --port 5175`를 실행한다.
4. 앱에서 `Video Discovery` 메뉴를 선택한다. 해시 진입점 `#app?tab=discovery`도 지원한다. 모바일은 `open navigation` 메뉴 버튼에서 찾는다.

UI 플래그 기본값은 off다. `VITE_DISCOVERY_ENABLED=1`은 UI 노출만 제어하며 서버의 `DISCOVERY_ENABLED`나 키 검사를 우회하지 않는다. 두 설정은 별개다. 변경 후 Vite를 재시작하고 production에서는 다시 빌드해야 한다. 기존 세션에 discovery 탭이 남아 있어도 UI가 꺼져 있으면 해당 화면을 복구하지 않는다.

## 실행: 독립 P1 Discovery 서비스

P1 독립 서비스가 8002, 기존 백엔드가 8000일 때 다음 개발 환경을 사용한다.

```dotenv
VITE_DISCOVERY_ENABLED=1
VITE_PROXY_TARGET=http://localhost:8000
VITE_DISCOVERY_PROXY_TARGET=http://localhost:8002
```

개발 요청은 상대 경로를 사용하므로 **`VITE_API_URL`은 비워 둔다**. 값이 설정돼 있으면 기존 공통 API 클라이언트가 해당 origin으로 직접 호출하므로 Vite 프록시를 통과하지 않는다.

`vite.config.js`는 구체적인 `/api/discovery` 규칙을 `/api` 앞에 등록한다. 탐색만 독립 서비스로 보내고 config/status/process 등 기존 API는 계속 기존 백엔드로 보낸다. 별도 target이 없으면 탐색도 기존 백엔드로 간다. 환경변수는 셸 및 Vite의 `.env.local` 등 해당 mode 파일에서 읽는다.

Docker Compose 개발 통합 예시(저장소 루트):

```bash
docker compose -f docker-compose.yml -f docker-compose.discovery.yml -f docker-compose.discovery-ui.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.discovery.yml -f docker-compose.discovery-ui.yml up --build
```

기존 전체 스택에 P1 독립 서비스를 추가하고 frontend의 `/api/discovery`만 `discovery:8000`으로 보낸다. API 키는 P1 Compose의 서버 환경에만 주입된다. 기존 P1 데이터 볼륨을 유지한다. 데이터 삭제가 필요한 상황이 아니면 `down -v`를 쓰지 않는다.

production frontend Docker 빌드는 `VITE_DISCOVERY_ENABLED=1` build arg를 지원한다(기본 `0`). Production nginx에는 Vite 개발 프록시가 없으므로 운영 reverse proxy에서 구체적인 `/api/discovery/`를 탐색 서버에, 나머지 API를 기존 서버에 라우팅해야 한다. 기존 nginx를 범용 프록시로 변경하지 않았다. 기존 `VITE_API_URL`을 쓸 경우 해당 API origin이 두 경로를 올바르게 처리해야 한다. 운영 인증·TLS는 기존 배포 정책에 맞춰 구성한다.

## P1 API 계약과 화면 동작

- 검색: `POST /api/discovery/search`. 기존 `apiFetch`를 재사용하며 keyword, relevance_language, min_views, min_duration_seconds, max_duration_seconds, published_after, published_before, max_results를 실제 필드명 그대로 보낸다.
- 검색어: 한국어·영어·일본어 Unicode 지원. 언어는 검색 힌트이며 영상 언어를 보장하는 필터는 아니다. CC BY 검색 조건은 고정 안내로 표시하며 해제 가능한 필터를 두지 않는다.
- 숫자 검증: 조회수 0~10^15, 길이 1~86,400초, 최소≤최대, 결과 수 1~50. 기본 선택은 20개다. UI 선택값은 10/20/30/50이며 다른 유효한 이력의 상한도 유지한다.
- 날짜: 사용자의 브라우저 시간대에서 시작일 자정과 종료일 **다음 날 자정**을 UTC ISO 8601 `Z`로 전송한다. 종료일 당일 전체를 포함한다. 다음 날은 달력 연산으로 구해 DST의 23/25시간 일자도 다룬다. 서버 `published_before`는 exclusive다.
- 영상 카드: 썸네일/대체 UI, 제목, 채널, 조회수, 길이, 게시일, 점수, CC BY 후보 표시, 안전한 원본 링크, 선택 버튼. 제목·설명은 React 일반 텍스트로만 렌더링한다.
- 정렬: 수집된 후보 내 점수/조회수/최신순. 브라우저 복사본만 정렬하며 정렬 때문에 API를 다시 호출하지 않는다. 동점은 ID로 결정한다.
- 응답 안내: total, cache_hit, fetched_at, limited를 표시하고 서버 score_notice/rights_notice 원문도 펼쳐 볼 수 있다. 자체 점수와 권리 관련 한국어 안내를 함께 표시한다.
- 상세 패널: 원본/메타데이터 확인 시각과 점수 구성요소, CC BY 및 제3자 권리 안내. 선택 또는 확인 체크만으로 서버 저장·제작을 시작하지 않는다. 새 검색/다른 영상 선택 시 확인 상태를 초기화한다.
- 이력: `GET /api/discovery/history?limit=10&before_id=...`. 최근 검색 조건·시각·성공/실패/미완료·결과 수·캐시 여부, 이전 이력 더 보기와 수동 새로고침. 검색 종료 시 로컬 이력을 갱신한다(추가 YouTube 검색은 하지 않음).
- 이력 재검색: 원래 P1 request를 그대로 POST한다. 비자정 ISO 경계나 null 언어도 보존한다. 날짜 입력은 로컬 일자로 보이지만 ‘이 조건으로 다시 검색’의 최초 요청은 원본 경계다. 이후 사용자가 폼으로 새 검색하면 입력된 로컬 날짜 전체를 기준으로 한다. 과거 결과 집합을 영구 복원한다고 표현하지 않는다.

## 오류·요청 제어

필수 입력·잘못된 날짜/숫자는 HTTP 호출 전에 한국어 필드 오류를 표시한다. 서버 422/429/502/503/504와 P1의 provider_not_configured, discovery_disabled, quota/rate/storage/provider 오류 코드를 한국어로 매핑한다. 원문 오류 body를 무조건 노출하지 않는다.

검색은 1회만 전송하고 자동 재시도하지 않는다. 검색 중 중복 제출/이력 재검색을 막고 10초 이후 지연 안내를 표시한다. 브라우저 응답 대기 상한은 75초다. ‘대기 중단’은 브라우저 fetch만 abort하며 서버의 이미 진행 중인 API 호출을 취소하는 기능은 아니다. 이 한계를 메시지로 알린다. 탭 해제 시 fetch와 타이머를 정리하고 오래된 응답이 새 화면을 덮지 않도록 요청 순번으로 가드한다.

이력 실패는 검색 오류와 별도로 표시한다. 이미지 로딩 실패/썸네일 없음, 0개 결과도 각각 명시한다. 외부 원본 링크는 HTTPS YouTube origin만 허용하며 `target=_blank`와 `noopener noreferrer`를 적용한다. 추천 점수는 바이럴 확률이 아니고 CC BY 메타데이터도 이용 권리 보증이 아니다.

## 파일과 테스트

신규 UI는 `dashboard/src/features/discovery/`의 DiscoveryPage, SearchFilters, VideoCard, VideoGrid, VideoDetail, SearchHistory, api, utils, strings로 분리했다. `App.jsx`에는 플래그/탭/딥링크/복구 가드와 새 화면의 키 안내 범위를 적용한다. Discovery에는 필요하지 않은 Gemini/Upload-Post 키 경고를 새 탭에서만 숨기고 기존 화면에서는 유지한다. 기존 API 클라이언트·인증·cloud/·영상 엔진에는 변경이 없다.

```bash
# dashboard 디렉터리
npm ci
npm run test:unit
npx playwright install chromium
npm run test:discovery
npm run build
npm run lint
```

브라우저 테스트는 Playwright Chromium의 desktop/Pixel 7 모바일 뷰포트에서 실행한다. Node 내장 테스트 러너로 날짜/DST/정렬/입력과 실제 Vite 프록시 분리를 검증한다. 테스트 mock은 P1 구조를 사용하며 외부 키·다운로드·엔진 호출을 필요로 하지 않는다. CI의 기존 frontend-build job에 unit/browser 단계를 추가했다. 시스템 Chromium을 사용할 때는 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`를 해당 실행 파일로 지정할 수 있다. 일반 CI에서는 Playwright 설치 브라우저를 사용한다.

Linux Chromium 모바일 에뮬레이션은 실제 Android/iOS 기기나 Windows Docker Desktop 검증이 아니다. 실 YouTube 검색에는 유효한 서버 키와 제공자 정책/할당량 검증이 필요하다. 전체 Docker ML 스택과 production reverse proxy 기동은 P2 UI 테스트로 검증되지 않는다.

### P2 실행 결과

- Node 유틸리티/실제 Vite 프록시 테스트: **7 passed**. Seoul/DST 날짜 경계, 원본 P1 필드, 정렬, 입력 검증, `/api/discovery`와 기존 `/api`의 목적지 분리를 확인했다.
- Chromium 브라우저: **40 passed** (desktop 20 + Pixel 7 모바일 에뮬레이션 20). 메뉴/필터/한·영·일 검색어/정렬/선택/원본 팝업/권리 안내/이력과 페이지/빈 결과/서버 오류/네트워크 실패/지연·중단·75초 타임아웃/HTML 텍스트 안전성/가로 넘침/기능 off를 검증했다.
- `VITE_DISCOVERY_ENABLED=1 npm run build`: 성공. 기존 500 kB chunk 크기 경고는 존재한다.
- 새 파일과 수정한 JS 파일 대상 ESLint: 성공. 전체 `npm run lint`는 변경 전부터 있던 **10 errors**가 그대로 남아 실패했다(`public/op1.js` 5, `Legal.jsx` 1, `PricingPage.jsx` 1, `lib/consent.js` 3). 기존 파일을 무관하게 수정하거나 lint 규칙을 꺼서 숨기지 않았다.
- 전체 백엔드 `pytest tests/ -q`: **1,291 passed / 29 skipped / 8 failed**. 기존 P1과 동일한 직접 DNS 의존 실패 8건이며 신규 백엔드 실패는 없다. 테스트/보안 검사는 변경하지 않았다.
- 실제 HTTP 라우팅: 전체 FastAPI/독립 P1 앱에서 `/api/discovery/history` 200 및 P1 응답 구조 확인. 기존 `/api/config`는 전체 앱에서 정상이고 독립 앱에는 없음을 확인했다. 검증용 프로세스는 종료했고 외부 YouTube 호출·영상 작업은 실행하지 않았다.
- 세 Compose 파일 병합 `config --quiet`, `git diff --check`: 성공.

## P3 제작 연결

P3에서 선택 후 권리·다운로드 확인과 기존 제작 엔진 연결을 추가했다. P2 당시의 미구현 범위와 구분하며, 현재 실행·검증 방법은 [제작 연결 문서](STUDIO_DISCOVERY_ENGINE.md)를 따른다.
