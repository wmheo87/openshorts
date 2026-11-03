# 상품 URL → 제품 쇼핑 쇼츠

## 지원 범위

1차 구현은 인증 없이 접근 가능한 공개 HTML의 표준 상품 메타데이터만 처리한다. JavaScript 실행·헤드리스 로그인·비공개 API 추측·쿠키 전달·차단 우회는 하지 않는다.

- JSON-LD `Product`의 상품명, 브랜드, 설명, `Offer.price/priceCurrency`, `additionalProperty`, 이미지 및 `VideoObject.contentUrl`.
- `@graph` 및 문서 내 `@id` 참조. JSON-LD가 없으면 `og:type=product` 페이지의 Open Graph 상품명·설명·가격·이미지/영상.
- 공개 HTML `img`, `video/source`. 첫 이미지에 대표 이미지 구분을 제공한다. 다른 이미지·영상 후보도 구분한다.
- 같은 URL(프래그먼트 제외)을 제거한다. 로고·아이콘·배너·광고 등 URL/alt 패턴과 알려진 작은 크기를 제외한다. 의미적으로 모든 광고·관련 없는 이미지를 식별한다고 보장하지 않는다. 사용자가 원본을 직접 확인하고 선택해야 한다.
- 상충하는 여러 가격, 만료된 가격, `AggregateOffer.lowPrice`처럼 현재 단일 판매가로 확정할 수 없는 값은 가격으로 만들지 않는다. 리뷰·할인율·효능을 생성하거나 외화 가격을 원화로 환산하지 않는다. 표시 가격은 판매 페이지 메타데이터이며 현재 가격의 진실성을 보증하지 않는다.
- UTF-8 공개 HTML 기준. 표준 상품 메타데이터가 없거나 동적/차단 페이지이면 수집 불가와 업로드 대안을 안내한다. 자료가 없으면 후보 0개를 반환한다.

**검증된 쇼핑몰 목록은 없다.** 추출기·네트워크 방어·제작 연결은 mock/소유 테스트 자료로 검증했다. 특정 상점을 지원한다고 표시하지 않는다.

쿠팡·네이버 계열은 URL 단계에서 차단한다(`coupang.com`, `coupang.net`, `naver.com`, `naver.me`, `pstatic.net` 및 하위 도메인). 사이트별 공식 API의 인증 범위·접근 정책·요금/할당량·이미지/영상 재사용 조건·실제 상품 접근을 확인한 다음 별도 어댑터를 추가해야 한다. 공식 API 접근 가능성만으로 편집·재게시 권리가 생기는 것은 아니다. 이번 버전에는 검증되지 않은 공식 API 어댑터를 구현된 것처럼 등록하지 않는다.

## 사용자 흐름

1. AI 쇼츠 제작 → 제품 영상형에서 상품 URL을 입력하고 **상품 분석**을 누른다. Gemini/fal.ai/ElevenLabs는 호출하지 않는다.
2. 판매 페이지 정보와 후보의 출처·원본 링크·타입·이미지 크기·원문 영상 길이 메타데이터·권리 상태를 확인한다. 미확인 값은 미확인으로 표시한다.
3. 원본 링크에서 자료를 확인하고 후보별 선택 및 사용·편집 권리 확인을 수행한다. 사용 허락을 수집 성공으로 추정하지 않는다. 권리 확인 전에는 서버 제작 자산으로 다운로드/등록하지 않는다. 원격 미디어를 브라우저에서 자동 로드하지도 않는다.
4. 선택 자료를 가져오면 서버가 파일 크기·형식·이미지 품질/실제 영상 길이를 검증하고 기존 비공개 자산 저장소에 등록한다. **원본 미리보기 불러오기**로 인증된 로컬 미리보기를 제공한다. 따라서 권리 확인 전 미리보기는 원본 링크이며, 앱 내 이미지/영상 플레이어는 승인 후 제공한다.
5. 상품 정보를 검토한 후 제작 입력에 적용한다. 기존 직접 업로드와 혼합할 수 있다. 장면은 최대 10개이며 순서·구간·사진 줌/팬·크롭·페이드·장면 비중을 수정할 수 있다. 영상의 검증된 원본 길이도 표시한다.
6. 원본 전체 권리와 이번 Gemini 비용을 확인하고 **제품 대본 생성**을 명시적으로 실행한다. 대본은 기본 20~30초 목표의 자연스러운 한국어 후킹/상품 특징/CTA를 지시한다. 장면 수와 순서는 승인 자산에 맞추며 가짜 배우/사용 장면을 요구하지 않는다. 최종 내레이션의 실측 길이는 음성 생성 결과에 따르며 20~30초를 강제로 잘라내지 않는다.
7. 대본 내용과 비용을 다시 확인한 후 **제품 MP4 제작**을 누른다. 기존 Gemini TTS → Whisper 타임스탬프 → 한글 ASS → FFmpeg 9:16 → MP4 다운로드를 그대로 사용한다. 영상이 없어도 승인된 사진의 줌/팬/페이드로 제작한다. fal.ai/ElevenLabs 키는 필수가 아니다.

생성 대본은 모델의 사실 검증 결과가 아니다. 판매자 설명 자체의 진실성, 권리, 최종 대본은 사용자가 확인해야 한다. 외부 유료 API의 자동 재시도·공급자 자동 전환은 추가하지 않았다.

## 모듈과 API

- `studio/product_video/public_fetch.py`: 익명 공개 HTTP(S), IP 고정·TLS 검증·리다이렉트/robots 정책·응답 제한.
- `product_page.py`: 결정적 HTML/JSON-LD/Open Graph 추출, 후보 정리·공개 DNS 확인.
- `url_api.py`: 기존 entitlement/owner 검사, 분석 기록, 권리 확인, 가져오기 중복 방지, 기존 저장소 연동.
- `api.py`: URL 라우터만 추가한다. 기존 제작 엔드포인트/유료 키/보안 검사는 유지한다.
- `scripts.py`: 기존 제품형 한국어 대본의 목표 길이를 20~30초로 조정한다.
- `ProductUrlInput.jsx`: 독립 URL 분석/권리 확인 UI. `ProductVideoStudio.jsx`의 기존 장면/입력 상태에 승인 자산을 연결한다.
- `product-url-messages.js`: 신규 UI 및 안전한 오류의 ko-KR/en-US 리소스. UI 로케일과 제작 언어를 분리한다.

```http
POST /api/saasshorts/product/url/analyze
Content-Type: application/json

{"url":"https://shop.example/products/item"}
```

응답: `analysis_id`, `adapter=public-standard-v1`, `source_url/source_site`, `name`, `brand`, `description`, `price`(없으면 null), `features`, `candidates`, `notice`.
후보: `id`, `url`, `source_site`, `kind`, `role`, `origin`, `width/height`, `duration_hint`, `rights_status=unconfirmed`. 후보의 크기·길이 힌트는 원문 값이며 가져올 때 실제 파일로 확인한다.

```http
POST /api/saasshorts/product/url/import
Content-Type: application/json

{"analysis_id":"<서버에서 받은 UUID>","candidate_ids":["0","1"],"rights_confirmed":true}
```

클라이언트가 가져올 URL을 직접 지정할 수 없다. 서버가 해당 소유자의 분석 목록에서만 선택한다. `assets`, `imported_candidate_ids`, `errors`를 반환한다. 일부 실패 시 성공 자산은 보존하고 실패한 후보만 안내한다. URL·내용 SHA-256 중복을 제거하고 완료된 후보의 재요청은 같은 자산을 반환한다. 처리 중/결과 불명 상태는 자동 중복 다운로드하지 않는다. 가져오기는 무료 네트워크 작업이며 실패 시 명시적 사용자 요청만 허용한다.

등록된 자산은 기존 `/assets/{id}`, `/analyze`, `/generate`, `/requests/{id}`, `/download/{id}` 경로를 사용한다. Gemini 키는 기존 제작 요청 헤더에서만 받으며 URL 분석·수집에 필요하거나 전달되지 않는다. 자산 경로/소유자 ID를 API 응답에 노출하지 않는다.

## 보안과 보관

- HTTP/HTTPS 기본 포트만 허용한다. userinfo, 제어 문자, 역슬래시, 로컬/내부/링크로컬/예약·변환 IPv6 주소, 인증성 쿼리(api_key/token/signature 등)는 거부한다.
- 모든 A/AAAA 주소를 검사하고 하나라도 비공개이면 거부한다. 선택한 검증 IP에 TCP 연결을 고정하고 peer IP도 확인한다. HTTPS는 원래 호스트의 SNI/인증서를 검증한다. 연결 시 호스트를 다시 해석하지 않으므로 DNS rebinding으로 내부 주소에 연결하지 않는다.
- 최대 3회 리다이렉트이며 매 홉 URL·전체 DNS·IP·robots 정책을 새로 검사한다. 환경변수 프록시·쿠키·Authorization을 사용하지 않는다. 외부 인증/보호조치를 우회하지 않는다.
- `OpenShortsProductBot/1.0` robots 규칙을 확인한다. 정책 접근 실패/Disallow/별도 crawl-delay 또는 request-rate 요구 시 보수적으로 수집을 거부한다. robots 허용을 법적 이용 허락으로 해석하지 않는다.
- HTML 2 MiB, robots 64 KiB, 원본 파일 100 MiB. Content-Length/실제 읽은 바이트 제한과 일치 여부를 검사하고 압축 응답을 거부한다. MIME allowlist 및 실제 이미지/영상 매직과 기존 Pillow/ffprobe 검증을 함께 사용한다.
- 이미지: PNG/JPEG/WebP, 양 변 300px 이상, 24 MP 이하, 종횡비 4:1 이내. 영상: MP4/MOV/WebM, 실제 영상 트랙/길이 10분 이하/4K 이하. HLS/플레이리스트/임베드 URL을 직접 원본처럼 처리하지 않는다.
- DNS 대기 5초, 소켓 작업 8초, HTML 읽기 경과 제한 25초, 파일 60초. robots 확인 및 개별 DNS/소켓 작업은 해당 제한으로 별도 보호되므로 전체 API wall time이 정확히 25/60초라는 의미는 아니다.
- 후보 최대 30개 및 후보 호스트 최대 6개. 프로세스별 수집 동시성 2, 소유자(자체 호스팅은 클라이언트 IP)별 분당 요청 10회. 다중 인스턴스 전체 할당량이 필요하면 별도 공유 제한을 구성해야 한다.
- 기존 `UPLOAD_DIR/product_studio` 비공개 저장·소유자 검사·24시간 TTL·계정 삭제 훅을 재사용한다. 분석 메타데이터도 소유자와 TTL을 갖는다. 수입 자산에는 출처 URL·확인 시각·SHA-256을 비공개로 보관한다.
- SQLite의 `product_url_imports`에는 분석/후보별 상태·자산 ID를 저장해 재요청을 중복 다운로드하지 않게 한다. 오래된 항목은 다음 사용 시 정리한다. 이 테이블은 기존 유료 제작 요청 원장과 별도다.

## 검증과 실제 접근 결과

유료 API를 호출하지 않았다. mock TTS/Whisper로 실제 24초 FFmpeg 720×1280 MP4, 한글 ASS, 승인 자산 가져오기부터 비공개 결과 다운로드까지 검증했다. 테스트 이미지는 자체 생성 자료이며 실제 상품 사용 장면을 생성하지 않는다.

2026-11-03 실제 접근 시도:

| URL | 실제 결과 |
| --- | --- |
| `https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html` (수집 테스트 상점) | 공개 DNS 확인 실패. 페이지/자료 수집 성공 여부 미검증 |
| `https://store.google.com/product/pixel_10?hl=ko` | 공개 DNS 확인 실패. 상품 존재/표준 메타데이터/정책/자료 접근 미검증 |
| 쿠팡·네이버 | 미지원으로 URL 단계에서 거부. 인증/정책 우회 시도 없음 |

DNS 실패를 실제 사이트의 차단/robots 정책으로 단정하지 않는다. 이 환경에서 검증할 수 없었다는 결과다. 정상 외부 DNS/직접 HTTPS egress 환경에서 허용된 실제 상품 URL을 다시 확인해야 한다. 기존 전체 테스트의 DNS 의존 실패도 별도로 보고한다.

남은 수동 검증: 실제 쇼핑몰의 정책·HTML 구조·파일 접근, 사이트별 정식 API 계약/할당량/재사용 권리, 실제 Gemini TTS 모델 계정 이용 가능성/비용·한국어 음성/Whisper 타이밍·상품 내용의 사실성, Windows/macOS/iOS 실제 장치. `gemini-3.8-flash-lite-tts`의 실계정 제공 여부를 검증했다고 주장하지 않는다. 기존 모델 확인 실패 차단을 유지한다.

### 실행한 테스트

| 검사 | 결과 |
| --- | --- |
| 신규 백엔드 추출·보안·권리·가져오기·FFmpeg 테스트 | 38개 통과 |
| 관련 백엔드(위 신규 + 기존 제품형/Gemini TTS/한국어/Discovery) | 188개 통과 (전체 실행에 포함) |
| 전체 백엔드 | 1415개 통과, 29개 건너뜀, 기존 DNS 의존 8개 실패 |
| 전체 Playwright(1440×1000 및 Pixel 7) | 116개 통과 |
| 자체 생성 실크기 이미지/줄바꿈을 적용한 신규 URL 화면 재검증 | 6개 통과 |
| 프런트 단위 테스트 | 16개 통과 |
| Vite build | 통과 (기존 청크 크기/선택적 OpenPanel 설정 경고) |
| 변경 프런트·신규 테스트 범위 ESLint | 통과 |
| 전체 ESLint | 기존 오류 10개: public/op1.js 5개, Legal/PricingPage 2개, lib/consent.js 3개 |
| git diff --check | 통과 |

전체 백엔드의 8개 실패는 공개 YouTube URL DNS 검증에 의존하는 `test_partial_processing.py`, `test_process_handover.py`, `test_short_source_gate.py`, `test_yt_clients.py`다. 원래 main `88cf143`의 독립 작업 사본에서도 같은 8개 실패(30 통과/2 건너뜀)를 재현했다. 보안 검사를 우회하거나 테스트를 숨기지 않았다. robots는 Allow 예외보다 일치하는 Disallow를 보수적으로 우선하며, 와일드카드·인코딩·점 경로도 검사한다.

```bash
.venv/bin/python -m pytest tests/test_product_url.py tests/test_product_video.py tests/test_gemini_tts.py tests/test_saasshorts_korean.py tests/studio -q
.venv/bin/python -m pytest -q
cd dashboard
npm run test:unit
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:discovery -- --workers=3
npm run build
npm run lint
npx eslint src/features/product-video src/i18n/product-url-messages.js src/i18n/messages.js tests/discovery/product-url.spec.js
```

추가 외부 소스코드 복사나 런타임 의존성 추가는 없다. 기존 라이브러리·자산 저장·렌더러를 재사용한다. `cloud/`, 워크플로, 과금 구조, AI 배우/Discovery/Clip Generator 엔진을 수정하지 않는다. 기존 `ubuntu-latest` CI 러너 고정 작업은 별도 브랜치이며 이 기능 PR에 섞지 않는다. main에 직접 커밋하거나 자동 병합하지 않는다.
