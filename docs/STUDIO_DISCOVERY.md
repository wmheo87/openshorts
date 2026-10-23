# AI Shorts Studio P1 — 영상 탐색 백엔드

P1은 **YouTube 메타데이터 검색만** 제공한다. 프런트엔드, 영상 다운로드, 제작 엔진 연결, 프로젝트 관리, 자동 게시, TTS, 결제는 추가하지 않는다. P0의 독립 모듈 설계를 유지하되 이번 지시에 따라 API를 `/api/studio/*` 대신 충돌 없는 `/api/discovery/*`로 구현했다.

## 실행

### 기존 OpenShorts에 통합

기존 백엔드를 실행하는 환경에서 다음 값을 설정하고 프로세스를 재시작한다. `.env`는 Git에 넣지 않는다. `app.py`는 기존 방식으로 `.env`를 읽는다.

```dotenv
DISCOVERY_ENABLED=1
YOUTUBE_API_KEY=
DISCOVERY_DB_PATH=.studio-data/discovery.sqlite3
```

`YOUTUBE_API_KEY`에는 본인의 키를 로컬 환경에서 입력한다. 코드·DB·브라우저·API 요청 body에 저장하지 않는다. `DISCOVERY_ENABLED` 기본값은 `0`이다. 비활성 상태에서는 새 API만 503 `discovery_disabled`를 반환하고 SQLite 생성이나 외부 호출은 하지 않는다. 기능을 켜고 키를 설정하지 않으면 검색은 503 `provider_not_configured`다. 이력 조회는 키가 없어도 로컬 DB를 읽을 수 있다. 환경 설정은 프로세스별로 지연 로드되므로 변경 후 재시작한다.

### 독립 경량 Docker 서비스

Docker Desktop의 **Linux containers** 모드(Windows) 또는 Linux Docker Engine/Compose v2에서 저장소 루트 기준으로 실행한다. GPU·Node·전체 ML 의존성을 설치하지 않으며 별도 데이터 볼륨을 사용한다.

```bash
docker compose -f docker-compose.discovery.yml up --build -d
docker compose -f docker-compose.discovery.yml logs discovery
docker compose -f docker-compose.discovery.yml down
```

Compose는 셸 또는 로컬 `.env`의 `YOUTUBE_API_KEY`를 주입한다. `down`은 데이터를 보존하고 `down -v`는 **검색 이력과 캐시 볼륨을 삭제**한다. 일반 개발에 `-v`는 필요하지 않다. 기본 포트는 호스트 루프백 8002다. `/health`는 프로세스 생존만 확인하며 API 키·외부 접근·SQLite 준비를 보장하지 않는다.

SQLite는 `/data/discovery.sqlite3`에 저장한다. 서비스는 비-root UID 10001로 실행하고 named volume을 쓰므로 Windows 호스트의 bind mount 권한·드라이브 경로 문제를 줄인다. DB 파일을 NFS/SMB에 올리거나 여러 서버가 공유하는 배포는 지원 범위가 아니다. Windows 네이티브 Python 실행과 Windows Docker Desktop 실제 실행은 아직 검증하지 않았다.

기업/클라우드 빌드 네트워크에서 HTTPS 프록시와 별도 CA가 필요한 경우 Docker의 표준 proxy build arguments와 선택적 BuildKit secret `pip_ca`를 사용할 수 있다. 예를 들어 `--build-arg HTTPS_PROXY --build-arg HTTP_PROXY --secret id=pip_ca,src=<로컬 CA bundle>`을 `docker build`에 전달한다. 인증서 검증은 끄지 않는다. 프록시 이름의 빌드 네트워크 DNS도 별도로 정상 동작해야 한다. 프록시 주소·CA·자격증명은 Dockerfile이나 저장소에 고정하지 않는다.

독립 Python 실행은 `requirements-discovery.txt`를 별도 가상환경에 설치하고 `uvicorn studio.discovery.app:app --host 127.0.0.1 --port 8002`로 시작한다. 이 진입점은 `.env`를 자동 로드하지 않으므로 셸에서 환경을 설정한다. Python 3.11을 기준으로 한다.

이 API에는 신규 사용자 인증이 없다. 초기 단일 운영자 self-host용이며 공유 이력·공유 API 예산을 사용한다. 인터넷에 공개할 때는 접근 제어 프록시와 TLS가 선행되어야 한다. 기존 cloud 사용자/인증/결제를 가져오지 않는다.

## API

### `POST /api/discovery/search`

```json
{
  "keyword": "한국 요리",
  "relevance_language": "ko",
  "published_after": "2026-01-01T00:00:00Z",
  "published_before": "2026-10-24T00:00:00+09:00",
  "min_duration_seconds": 120,
  "max_duration_seconds": 1200,
  "min_views": 10000,
  "max_results": 50
}
```

`keyword`만 필수다. 키워드는 NFC/공백 정규화 후 최대 200자이며 한국어·영어·일본어 Unicode를 그대로 전송한다. `relevance_language`는 선택적 `en|ko|ja` 검색 힌트이며 영상 언어를 보증하는 필터는 아니다. 임의 URL/키 필드는 받지 않는다. 날짜는 시간대가 포함된 ISO 8601이며 내부 UTC로 변환한다. 시작은 inclusive, 종료는 exclusive로 상세 메타데이터에 다시 적용한다. 조회수·길이도 서버에서 정확한 경계값을 검사한다. 기본 길이는 1~86,400초, 기본 최소 조회수는 0, 반환 상한은 50건이다. 잘못된 범위·미지원 필드·51건 요청은 422다.

다음은 실제 영상이 아닌 mock 응답의 **형태 예시**다.

```json
{
  "search_id": "00000000-0000-4000-8000-000000000001",
  "items": [{
    "video_id": "abcdefghijk",
    "url": "https://www.youtube.com/watch?v=abcdefghijk",
    "title": "한국 요리 수업",
    "description": "Mock example",
    "channel_id": "example-channel",
    "channel_title": "Example Kitchen",
    "thumbnail_url": "https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg",
    "published_at": "2026-10-20T00:00:00Z",
    "view_count": 10000,
    "duration_seconds": 600,
    "license": "creativeCommon",
    "metadata_fetched_at": "2026-10-23T00:00:00Z",
    "recommendation_score": 77.79,
    "score_components": {
      "age_days": 3.0,
      "average_daily_views": 3333.33,
      "keyword_relevance": 1.0
    }
  }],
  "total": 1,
  "cache_hit": false,
  "fetched_at": "2026-10-23T00:00:00Z",
  "expires_at": "2026-10-23T01:00:00Z",
  "scanned_count": 1,
  "pages_fetched": 1,
  "limited": false,
  "score_version": "heuristic-v1",
  "score_notice": "Independent heuristic, not a viral success probability or a YouTube metric.",
  "rights_notice": "Creative Commons metadata is not proof of all usage rights."
}
```

`scanned_count`는 상세 조회 대상인 유효한 고유 ID 수다. `limited`가 true이면 다음 페이지 또는 일부 후보가 예산/결과 상한 때문에 제외되었다. 검색 범위는 최대 3개 API 페이지(각 50 후보)이며 전체 YouTube를 전수 검색하거나 최고 인기 영상을 보장하지 않는다. 결과가 부족하면 다음 페이지를 조회하지만 최대 50건만 반환하며 P1은 외부 페이지 토큰을 공개하지 않는다. `search.list`는 CC 필터·단일 영상 타입으로 호출하고, `videos.list`로 상태·라이선스·길이·조회수를 보강한다. 누락/비공개/미처리/라이브·예약/미래 게시/불명 라이선스·조회수·길이는 제외한다. 제목·설명은 텍스트 데이터이며 HTML로 실행해서는 안 된다.

### `GET /api/discovery/history?limit=20&before_id=123`

최근 검색부터 반환한다. `limit`은 1~100, 다음 페이지에는 반환된 `next_before_id`를 그대로 전달한다. 캐시 사용과 실패 검색도 기록한다. 실제 API 키가 없는 요청, 기능 비활성 요청, 입력 검증/분당 제한에서 거부된 요청은 이력에 추가하지 않는다.

```json
{
  "items": [{
    "search_id": "00000000-0000-4000-8000-000000000001",
    "requested_at": "2026-10-23T00:00:00Z",
    "request": {
      "keyword": "한국 요리",
      "published_after": null,
      "published_before": null,
      "min_duration_seconds": 1,
      "max_duration_seconds": 86400,
      "min_views": 0,
      "max_results": 50,
      "relevance_language": "ko"
    },
    "result_count": 1,
    "cache_hit": false,
    "status": "success",
    "error_code": null
  }],
  "next_before_id": null
}
```

프로세스가 강제 종료되면 실행 중 이력은 `pending`으로 남을 수 있다. P1은 제작 작업 복구 시스템이 아니다. 검색 이력은 최대 1,000건/30일이며 검색 시 정리하고 조회에서도 30일을 넘는 항목을 숨긴다. 사용하지 않는 DB의 물리적 자동 파기나 사용자별 이력은 P1 범위가 아니다.

### 오류

```json
{
  "detail": {
    "code": "provider_not_configured",
    "message": "Set YOUTUBE_API_KEY on the server to enable YouTube discovery.",
    "retryable": false
  }
}
```

| 상태 | 코드 | 대응 |
|---|---|---|
| 503 | `discovery_disabled`, `provider_not_configured` | 기능/서버 키 설정 후 재시작 |
| 503 | `discovery_configuration_error`, `discovery_storage_unavailable` | 설정·DB 경로·쓰기 권한 확인 |
| 422 | FastAPI 입력 검증 오류 | 입력 범위/시간대/필드 수정 |
| 429 | `rate_limited`, `discovery_busy` | 분당 요청 또는 동시 검색 제한; 잠시 후 재시도 |
| 429 | `local_quota_exceeded`, `youtube_quota_exceeded` | 로컬 UTC 예산/Google 콘솔 할당량 확인 |
| 429 | `provider_rate_limited` | 제공자 요청 제한 확인 |
| 502 | `provider_access_denied` | API 활성화·키 제한·권한 확인 |
| 502/504 | `invalid_provider_response`, `provider_unavailable`, `provider_timeout` | 제공자/네트워크 상태 확인 |

외부 오류 본문·예외 URL·키는 반환하지 않는다. YouTube 키는 `X-Goog-Api-Key` 헤더로만 전송하며 query string이나 HTTPX URL 로그에 넣지 않는다. 실제 키로 헤더 인증과 프로젝트의 키 제한 구성이 동작하는지 배포 전 확인해야 한다.

## 추천 점수

`heuristic-v1`은 `0~100` 범위에서 다음 고정 가중치를 적용한다.

```text
age = max(게시 후 경과일, 1)
daily = 누적 조회수 / age
volume = min(log1p(조회수) / log1p(10,000,000), 1)
velocity = min(log1p(daily) / log1p(100,000), 1)
recency = exp(-age / 90)
relevance = 키워드 토큰의 제목 일치 1, 설명에만 일치 0.5, 미일치 0의 평균
score = round(100 * (0.30*volume + 0.30*velocity + 0.15*recency + 0.25*relevance), 2)
```

동점은 video ID 순으로 결정한다. 관련성은 NFKC·대소문자 정규화 후 문자열 포함 여부를 쓰는 단순 휴리스틱이며 한국어/일본어 형태소 분석·의미 검색은 아니다. `daily`는 실제 최근 일별 증가량이 아니다. 점수는 수집한 후보 비교용이며 바이럴 확률·성공 보증·YouTube 공식 지표가 아니다. 캐시 응답은 만료 전 동일 점수를 유지하며 새 검색에서만 다시 계산한다.

## 캐시와 요청 예산

SQLite의 `discovery_videos`는 video ID PK로 중복을 제거하고, 다른 키워드 검색에서도 최신 상세 정보를 재사용한다. `discovery_search_cache`는 정규화된 전체 필터·상한·점수 버전·페이지 상한의 해시를 키로 써 검색 응답 전체를 캐시한다. 빈 결과도 캐시한다. 만료 시 재조회하며 **기존 영상 캐시를 재사용해 검색 캐시의 수명을 늘리지 않는다**. 실패는 성공 캐시에 저장하지 않는다.

| 환경변수 | 기본값 | 의미 |
|---|---|---|
| `DISCOVERY_CACHE_TTL_SECONDS` | 3600 | 캐시 수명, 1~86400초 |
| `DISCOVERY_REQUESTS_PER_MINUTE` | 30 | 캐시 조회 포함, 전역 검색 요청 제한 |
| `DISCOVERY_API_CALLS_PER_DAY` | 100 | search/details 합계 일별 외부 HTTP 요청 상한 |
| `DISCOVERY_QUOTA_UNITS_PER_DAY` | 9000 | search=100/details=1로 계산하는 보수적 로컬 비용 상한 |
| `DISCOVERY_MAX_PAGES` | 3 | 한 검색에서 1~3개 search 페이지 |
| `DISCOVERY_DB_PATH` | `.studio-data/discovery.sqlite3` | 쓰기 가능한 로컬 SQLite 경로 |

한 검색은 최대로 search 3회와 details 3회(최대 6 HTTP 요청)다. 다음 페이지나 상세 조회가 불필요하면 호출하지 않는다. 모든 외부 시도는 전송 **전** SQLite 트랜잭션으로 예산을 예약하며 오류 시도도 계산한다. 일별 카운터는 재시작 후 유지되고 UTC 날짜에 리셋된다. 제공자가 quota 초과를 반환하면 당일 새 외부 호출을 차단한다. 아직 유효한 캐시는 사용할 수 있다. 자동 재시도로 호출량을 늘리지 않는다. HTTP timeout은 요청별 10초이며 프로세스별 검색 1개만 수행한다. 다중 프로세스의 중복 cache miss까지 분산 잠금으로 합치지는 않지만 예산 예약은 SQLite에서 원자적으로 제한한다.

로컬 단위 계산은 Google의 실제 청구·할당량 계량기가 아니다. 현재 공식 규정과 콘솔 할당량을 우선 확인한다. 제한을 피하기 위한 키 회전이나 스크래핑은 구현하지 않는다. WAL/연결별 foreign_keys/5초 busy timeout/짧은 트랜잭션을 사용하며 DB·HTTP 처리는 FastAPI threadpool에서 실행한다. DB 버전은 v1이며 알 수 없는 이후 버전은 거부한다. 파일 백업은 SQLite backup API 또는 서비스 종료 후 수행한다.

## 권리·라이선스 및 실 API 검증

CC BY 메타데이터만으로 음악·삽입 영상·인물 등 모든 사용 권한이 확인되는 것은 아니다. P1은 라이선스 버전을 임의로 CC BY 4.0으로 지정하지 않으며 영상 이용/다운로드 권한 확인이나 법적 귀속 검증을 수행하지 않는다. 소스·적용 라이선스·표시 의무·플랫폼 약관을 실제 이용 전에 확인한다.

루트 코어는 MIT이며 저작권·허가문 보존이 필요하다. `cloud/`는 별도 Commercial License로 제3자 hosted/managed/paid 제공 등에 제한이 있다. 신규 `studio/`는 그 코드를 복사/import하지 않고, 독립 이미지는 `cloud/`를 포함하지 않는다. 기존 전체 OpenShorts 배포물의 의존성·모델·별도 렌더러 조건까지 신규 코드가 MIT라고 일괄 허가되는 것은 아니다.

배포 전 실제 키로 확인할 항목:

1. YouTube Data API 활성화, 키 제한 및 `X-Goog-Api-Key` 인증.
2. `search.list(videoLicense=creativeCommon,type=video)`와 `videos.list`의 실제 라이선스/status/statistics 응답, 삭제/통계 누락 처리.
3. 한·영·일 검색어와 언어 힌트, 날짜 범위, 실제 검색 할당량/오류 이유·페이지 토큰.
4. YouTube API 데이터 보존/갱신·추천 파생 지표 제공 정책과 실제 제품 사용 흐름의 적합성. 휴리스틱 구현이 정책 준수 인증을 뜻하지 않는다.
5. HTTPS 외부 연결·TLS·프록시와 실제 제공자 오류. 현재 개발 네트워크의 Google 공식 문서 조회는 403으로 차단됐으며 실 키 호출은 미실행이다.

공식 확인 자료: [search.list](https://developers.google.com/youtube/v3/docs/search/list), [videos.list](https://developers.google.com/youtube/v3/docs/videos/list), [할당량](https://developers.google.com/youtube/v3/determine_quota_cost), [개발자 정책](https://developers.google.com/youtube/terms/developer-policies).

## 테스트와 변경 범위

```bash
python -m pytest tests/studio/ -q
python -m pytest tests/ -q
docker compose -f docker-compose.discovery.yml config --quiet
```

테스트는 `httpx.MockTransport`, 임시 SQLite, 주입된 시각을 사용하고 실제 키·외부 네트워크·ML 모델을 필요로 하지 않는다. 기존 CI가 `tests/`를 수집하므로 신규 테스트도 자동 실행된다. `app.py`에는 router 등록만 추가했고 `main.py`/영상 편집·자막·프런트엔드는 수정하지 않았다. 기존 테스트의 직접 DNS 의존 실패 8건은 P0 기준선과 비교해 별도로 보고한다.

P2 화면 개발 또는 P3 엔진 연결은 수행하지 않았다. PR 설명 초안은 [AI_SHORTS_STUDIO_P1_PR.md](AI_SHORTS_STUDIO_P1_PR.md)를 참고한다.

## P3 제작 서버 재확인

Discovery 선택을 실제 제작으로 연결하는 경우 처리 서버에도 Discovery 설정과 YouTube 키가 필요하다. 단일 백엔드 Compose 구성, fresh 재확인 예산 및 한계는 [P3 제작 연결](STUDIO_DISCOVERY_ENGINE.md)을 참고한다.
