# PR 제목

feat: add opt-in YouTube discovery backend with SQLite caching

## 변경 내용

기존 OpenShorts에는 단일 영상 URL/업로드만 있어 키워드로 CC 영상을 찾고 비교할 수 없었다. 독립적인 `studio/discovery/` 모듈과 `POST /api/discovery/search`, `GET /api/discovery/history`를 추가한다. 검색은 YouTube Data API v3의 search.list와 videos.list를 사용하고 영상 다운로드나 편집 엔진 변경은 포함하지 않는다.

CC 메타데이터·공개/라이브 상태를 검증하고 날짜·조회수·정확한 길이를 필터링한다. 최대 50개 결과에 원본 정보와 설명 가능한 0~100 휴리스틱 점수를 제공한다. CC 표시가 모든 권리 확인을 뜻하지 않으며 점수는 바이럴 성공 확률이 아니다.

SQLite는 검색 이력, 고유 video ID별 상세 메타데이터, 질의 캐시, 분당 요청 및 일별 외부 API 예산을 보관한다. 캐시/상세 재사용과 빈 결과 캐싱, TTL, 원자적 예산 예약, 제공자 quota 초과 시 차단을 포함한다. 키는 서버 환경변수에서만 읽고 URL/이력/외부 오류 응답에 넣지 않는다. 기능 기본값은 비활성이며 기존 백엔드에는 router 등록만 추가한다.

## 파일

| 구분 | 파일 |
|---|---|
| 신규 Python | `studio/__init__.py`, `studio/discovery/__init__.py`, `config.py`, `errors.py`, `schemas.py`, `ranking.py`, `repository.py`, `youtube.py`, `service.py`, `router.py`, `app.py` (나머지는 모두 `studio/discovery/` 아래) |
| 신규 테스트 | `tests/studio/test_discovery.py` |
| 신규 실행 설정 | `requirements-discovery.txt`, `deploy/discovery/Dockerfile`, `docker-compose.discovery.yml` |
| 신규 설명 | `docs/STUDIO_DISCOVERY.md`, 이 PR 설명 초안 |
| 기존 파일 수정 | `app.py`, `.env.example`, `.gitignore`, `.dockerignore`, `README.md` |
| 이전 P0 산출물 | `docs/AI_SHORTS_STUDIO_PLAN.md`는 앞선 분석 단계에서 작성되어 작업 디렉터리에 있던 파일이며 P1에서 변경하지 않음 |

독립 Docker 이미지는 전체 ML 스택·Node·cloud/ 없이 실행되며 비-root 사용자, 영속 named volume, 선택적 기업 CA secret을 사용한다. 기존 코어 MIT와 `cloud/` Commercial License를 구분했고 신규 코드에서 상용 모듈을 복사/import하지 않았다.

## 검증

- 신규 mock 테스트 **64개 통과**: 한·영·일 키워드, 빈 결과, 필터 경계, CC/누락/비공개/라이브 제외, 점수 신호·범위, 중복, 페이지 상한, 캐시/만료/재시작, quota/timeout/잘못된 응답, 키 비노출, SQLite 동시 예산 예약, 기존 라우트 보존.
- 전체 `pytest tests/ -q`: **1,291 passed / 29 skipped / 8 failed**, 31.09초. 신규 실패는 없으며 아래 P0 기준선의 동일 8건이 남는다. 전체 suite가 green인 것은 아니다.
- Docker Compose configuration 검증 통과. Linux Docker 이미지 빌드, 비-root 컨테이너 HTTP health/키 미설정 오류, 고정 의존성 환경의 mock 검색/캐시/이력, 재시작 후 SQLite 보존 확인.
- `git diff --check` 통과. 프런트엔드 파일/의존성·영상 엔진·기존 테스트는 변경하지 않아 프런트 빌드는 이번 P1에서 재실행하지 않았다.

기존 실패: `test_partial_processing.py` 2건, `test_process_handover.py` 1건, `test_short_source_gate.py` 4건, `test_yt_clients.py` 1건. `security_utils.assert_public_url`의 직접 DNS 조회가 현재 환경에서 실패한다. 제공자/예약을 stub한 기존 테스트가 DNS에는 의존하기 때문에 400/예외가 먼저 발생하며 P0에서도 동일하게 실패했다. 보안 검사나 기존 테스트를 변경/비활성화해 숨기지 않았다.

## 제한 및 배포 전 확인

- 실제 YouTube 키 호출은 미실행. API 활성화·키 제한·헤더 인증, 실제 CC/status/statistics 응답·다국어 검색·페이지·할당량을 확인해야 한다.
- Google 공식 문서 조회가 개발 네트워크에서 403으로 차단되었다. 최신 할당량, 메타데이터 보존 및 파생 지표 제공 정책은 실제 배포 전에 확인한다. 로컬 quota 단위는 실제 Google 계량기가 아니다.
- Windows Docker Desktop/Linux containers에서의 실행·볼륨 동작은 미검증이며 Linux Docker에서 검증했다. Docker는 호스트 아키텍처/프록시/인증서 설정이 필요할 수 있다.
- 단일 운영자용 opt-in API다. 인터넷 공개 시 인증 프록시/TLS가 필요하며 사용자별 이력 분리나 다중 서버 SQLite는 제공하지 않는다.
- P2 UI·P3 제작 연결·P4 프로젝트 관리는 포함하지 않는다.

설치·설정·요청/응답 예시: [STUDIO_DISCOVERY.md](STUDIO_DISCOVERY.md).
