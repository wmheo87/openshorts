# AI Shorts Studio P3 — 탐색 영상과 기존 제작 엔진 연결

## 범위와 구조

기준 main은 P2 병합 `562ce9b48bcf559990b0f225a41f7b290166e0b8`이다. P0~P2를 유지하며 신규 AI 알고리즘, cloud/ 수정, P4 영구 프로젝트 보관은 포함하지 않는다. 기존 MIT 라이선스 영역에서 연결 코드를 추가하고 별도 라이선스인 cloud/ 코드를 복제하지 않았다.

```text
Video Discovery → VideoDetail + ProductionOptions
  → 권리 확인 + 별도 다운로드 허용 확인
  → App.handleProcess → POST /api/process
  → 기존 URL 보안 검사 → fresh videos.list → 기존 길이·품질 게이트
  → 기존 작업 큐 / AI·자막·리프레이밍·FFmpeg
  → GET /api/status/{job_id} → 기존 ResultCard / MP4 다운로드
```

검색·선택만으로는 다운로드나 제작을 시작하지 않는다. CC BY 표시는 저작권·초상권·다운로드 권한 전체를 보증하지 않는다. 사용자가 두 확인란을 각각 체크해야 한다. URL 처리 정책이 금지되면 기존 보유 원본 업로드 경로로 안내하며 보호 장치를 우회하지 않는다.

## 옵션과 API

목표 클립 수는 1~5, 길이는 15~30초 또는 15~60초, 후킹은 켜기/끄기를 선택할 수 있다. 각 항목의 기본값 선택은 해당 필드를 생략해 기존 엔진 기본값을 보존한다. 출력은 vertical(9:16), 레이아웃은 기존 auto이다. 목표 수·길이는 기존 엔진에 전달하는 요청이며 실제 생성 수를 보장하지 않는다.

기존 API에 선택적인 discovery_source 필드만 추가한다. 일반 URL·파일 업로드 요청은 이 필드를 보내지 않는다.

```json
{
  "url": "https://www.youtube.com/watch?v=abcdefghijk",
  "acknowledged": true,
  "output_format": "vertical",
  "target_clips": 3,
  "clip_min_seconds": 15,
  "clip_max_seconds": 60,
  "auto_hook": "1",
  "layouts": ["auto"],
  "discovery_source": {
    "video_id": "abcdefghijk",
    "url": "https://www.youtube.com/watch?v=abcdefghijk",
    "title": "선택 당시 제목",
    "channel_title": "선택 당시 채널",
    "license": "creativeCommon",
    "metadata_fetched_at": "2026-10-23T00:00:00Z",
    "download_authorized": true
  }
}
```

접수 응답은 기존 job_id/status/partial 등에 fresh discovery_source를 추가한다. 상태 응답에도 동일한 출처를 제공한다. 서버는 canonical URL과 ID 일치, 명시적인 acknowledged, 별도 download_authorized를 검증한다. videos.list를 캐시 없이 호출해 공개·처리 완료·비라이브·CC BY 상태를 재확인한다. P1 SQLite 예산에서 호출마다 1단위를 예약한다. 품질 확인 후 사용자가 재제출하면 다시 1단위를 사용한다. 키 누락, 할당량, 재확인 실패는 작업을 접수하지 않고 오류를 반환한다. 외부 서비스 실패를 오래된 캐시로 대체해 제작하지 않는다.

출처는 기존 작업 디렉터리의 `.discovery-source.json`에 원자적으로 저장한다. 선택 당시 정보와 최신 정보, 확인 시각을 유지하며 키·쿠키는 저장하지 않는다. 기존 작업 복구/소유자 확인/TTL 정책을 따른다. 영구 프로젝트 DB가 아니다.

## 실행 구성

전체 백엔드 한 개에서 검색·재확인 예산·작업 큐를 함께 운영하는 구성을 권장한다.

```bash
docker compose -f docker-compose.yml -f docker-compose.discovery-engine.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.discovery-engine.yml up --build
```

환경변수로 YOUTUBE_API_KEY와 제작용 GEMINI_API_KEY를 제공한다. Gemini 대신 기존 로컬 LLM을 사용하려면 LLM_BASE_URL과 LLM_MODEL을 구성하고 컨테이너에서 모델에 접근할 수 있어야 한다. 키는 Git에 넣거나 VITE_ 변수로 전달하지 않는다. DISCOVERY_ENABLED=1과 프런트엔드 VITE_DISCOVERY_ENABLED=1은 overlay가 설정한다. 검색 SQLite는 studio-discovery-data named volume에 저장하고 Dockerfile에서 해당 경로를 기존 비루트 사용자에게 할당한다.

P2의 분리된 메타데이터 서비스만 켜면 검색은 가능하지만 제작 서버의 재확인은 충족되지 않는다. 제작 서버에도 Discovery 설정과 키가 필요하다. 별도 DB를 사용하는 여러 서비스의 로컬 예산은 합산되지 않으므로 프로젝트 전체 YouTube 할당량을 따로 관리해야 한다. 위 단일 백엔드 구성이 이를 단순화한다.

Windows/Linux에서 같은 Compose 파일과 named volume을 사용한다. 플랫폼별 경로·파일 잠금 API를 추가하지 않았다. 실제 Windows Docker Desktop 실행, 전체 ML Docker 이미지 빌드 및 실제 AI 생성은 이번 환경에서 검증하지 않았다.

## 상태, 중복 제출과 실패

기존 작업 접수·대기열·처리 로그·부분 결과·완료·오류 화면을 재사용한다. 서버가 제공하지 않는 숫자 진행률을 새로 만들지 않는다. 상태 요청은 겹치지 않으며 이전 작업의 늦은 응답은 화면에 반영하지 않는다.

전송 중 동기 ref 잠금과 버튼 비활성화를 적용한다. 제작 POST는 180초 후 대기를 중단할 수 있지만 서버 작업을 취소하거나 자동 재전송하지 않는다. 전송 전에 같은 탭 sessionStorage에 출처와 시각을 남긴다. 네트워크 단절, 작업 ID 없는 성공 응답, 접수 여부가 불확실한 5xx는 새로고침 후에도 제출을 잠근다. 명확한 접수 전 오류에만 명시적 재시도를 제공한다. 관리자가 서버에서 미생성을 확인한 뒤 사용자가 확인창으로 잠금을 해제할 수 있다.

서버 idempotency 키나 요청 ID 조회 기능은 없다. 탭·브라우저·클라이언트 사이의 중복 방지, 브라우저 저장소 사용 불가 시 새로고침 보호는 보장하지 않는다. 응답 유실 후 서버와 자동 조정하는 기능은 후속 과제다.

접수된 job_id와 출처는 기존 브라우저 작업 복구에 함께 저장한다. 상태 404/410이면 실패로 표시하고 자동 재제작하지 않는다. 일반 상태 연결 오류는 확인 중 경고를 표시한다. BYOK 헤더의 키를 서버 복구용으로 새로 저장하지 않으므로 재시작 후 기존 엔진의 키 복구 한계는 남는다.

Discovery의 로컬 완료 결과는 실제 파일 존재·크기·출력 경로를 확인한다. 누락·만료 파일은 unavailable로 표시하며 원래 클립 인덱스를 보존한다. 누락이 있는 완료 작업은 실패/부분 결과로 표시한다. 기존 파일 접근 권한과 다운로드 경로 검사는 유지한다.

## 검증 결과 (2026-10-23, Linux)

| 검사 | 결과 |
|---|---|
| P3 Python 테스트 | 21 통과 |
| 전체 Python | 1312 통과, 29 건너뜀, 기존과 동일한 8 실패 |
| Node 유틸리티·프록시 | 12 통과 |
| Playwright 데스크톱·모바일 | 80 통과 (P2 40개 포함) |
| Discovery 활성 production build | 통과 |
| 변경 영역 ESLint | 오류·경고 없음 |
| 전체 ESLint | 기존 4개 파일의 10 오류 유지 |
| Compose 병합 설정 검사 | 통과 |

Python 전체 실패는 변경 전에도 재현한 URL 보안 검사의 이 환경 DNS 해석 문제다. 실패 테스트는 test_partial_processing의 2개, test_process_handover의 URL 우선순위 1개, test_short_source_gate의 4개, test_yt_clients의 probe 1개다. 보안 검사를 비활성화하지 않았다. 전체 린트 기존 오류는 public/op1.js(5), Legal.jsx(1), PricingPage.jsx(1), lib/consent.js(3)이다.

Mock 검증은 정확한 요청·옵션, 두 권리 확인, 중복 클릭, 키/정책/길이/품질/할당량/라이선스 변경, 명시적 재시도, 응답 유실·시간초과·새로고침, 기존 URL 및 업로드, 대기·부분 결과·완료·실패, 소유자 확인·결과 경로 검사를 포함한다. 기존 테스트 assertion이나 URL 보안 규칙을 제거하지 않았다.

재생 테스트의 owned-preview.base64는 직접 FFmpeg로 생성한 2초 90×160 H.264 합성 단색 영상이다. 브라우저가 실제 디코딩하고 재생 시각이 증가하며 다운로드 바이트가 일치함을 검증했다. 이는 **AI가 실제 원본에서 쇼츠를 생성한 검증이 아니다**. 실제 YouTube·Gemini 키와 로컬 LLM이 없고 무거운 ML 의존성도 없어 전체 다운로드→AI→자막→FFmpeg의 실영상 검증은 미실행이다. 키와 이용 권한이 확보된 원본으로 별도 확인해야 한다.

기존 GitHub CI가 Python 전체, 프런트 빌드, Node, Playwright를 자동 수집하므로 워크플로 변경은 필요하지 않다. 로컬 검증 결과가 원격 CI 성공을 뜻하지 않는다.

## 재현 명령

```bash
.venv/bin/python -m pytest tests/studio/test_production.py -q
.venv/bin/python -m pytest tests/ -q
cd dashboard
npm ci
npm run test:unit
npx playwright install chromium
npm run test:discovery
VITE_DISCOVERY_ENABLED=1 npm run build
npx eslint src/features/discovery src/App.jsx tests --max-warnings 0
```

이 클라우드 환경에서는 설치된 Chromium을 사용해 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium을 지정했다. 기본 CI는 Playwright 관리 브라우저를 설치한다.

P4 후보는 영구 프로젝트·제작 이력, 장기 보관 정책, 서버 idempotency/응답 유실 조정이다. 이번 변경에서 구현하지 않았다.
