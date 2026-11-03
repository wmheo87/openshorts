# 제품 영상형과 선택형 영상 공급자

## 기준과 범위

기준 main: `af7ef8338c042ddd07ae385d7bb4d1d7162e4119` (한국어 지원 PR #5 병합).
실제 확인 결과 이 main에는 Gemini TTS 후속 커밋 ee73f44가 없었다. 기존 브랜치는 변경하지 않고, main에서 만든 `feature/product-video-provider`에 해당 커밋을 cherry-pick(c35d0c9)해 보존한 뒤 제품형을 추가했다. 따라서 main 대상 PR에는 미병합 Gemini TTS 변경도 포함된다. main 자동 병합은 하지 않는다.

이번 기본 제작 경로는 **사용자가 권리를 확인한 제품 영상·사진 + 한국어 Gemini 대본/TTS + 로컬 FFmpeg**다. AI 배우나 fal.ai/ElevenLabs 키를 요구하지 않는다. 기존 영어·스페인어, 한국어 ElevenLabs/Gemini TTS, fal.ai Low Cost/Premium은 AI 배우형에서 유지한다. Discovery/Clip Generator의 알고리즘과 cloud/·배포·과금 코드는 수정하지 않았다.

## 구조와 파일

```text
SaaShortsTab: 제품 영상형(기본) / AI 배우형
  ├─ ProductVideoStudio → product/assets → 승인·비공개 원본
  │   → product/analyze → 사용자 확인 → product/generate
  │   → VideoProvider[ffmpeg-product]
  │   → Gemini TTS → 실제 음성 Whisper/ASS → 승인 원본 FFmpeg 합성
  │   → product/requests/{id} → 인증된 MP4 blob 미리보기·다운로드
  └─ 기존 배우 UI → 기존 analyze/generate/actor-options
      → VideoProvider[fal-actor] → 기존 generate_full_video
```

- `studio/product_video/providers.py`: VideoProvider 인터페이스, 기능별 capability와 레지스트리, 기존 fal.ai 어댑터
- `storage.py`: 비공개 업로드·소유자·유효기간·SQLite 요청 ID/내용 hash/상태
- `scripts.py`: 승인 원본 장면에 대응하는 가변 구간 상품 대본. actor_talking 고정 5구간·생성 b-roll 요구 없음
- `render.py`: 구간 선택, 사진 줌/팬, 9:16 크롭, 전환, ASS·음성·배경음·MP4
- `api.py`: 기존 auth/entitlement/concurrency를 사용하는 독립 router
- `dashboard/src/features/product-video/ProductVideoStudio.jsx`: 기본 제품형 UI. 기존 배우 UI는 기존 파일에서 보존
- `tests/test_product_video.py`, `dashboard/tests/discovery/product-video.spec.js`: 신규 회귀/실제 FFmpeg 검증
- `.github/workflows/ci.yml`: 기존 검사 유지, FFmpeg·한글 폰트를 추가해 실제 합성 테스트가 CI에서도 실행되도록 구성

새 공급자는 VideoProvider.render와 개별 capabilities를 구현해 명시적으로 등록한다. 실패한 공급자 대신 다른 공급자를 선택하는 코드는 없다. `fal-actor` 어댑터는 기존 함수를 호출하며 알고리즘을 복제하지 않는다.

## 제작 기능

1. 원본/음원 이용·편집 권리를 확인하고 최대 10개 장면을 업로드한다. 영상은 실제 구간 시작/끝을 선택한다. 사진은 시간 비중과 움직임(없음/확대/팬)을 선택한다. 장면 순서를 변경·제외할 수 있다.
2. 사진/영상마다 실제 보이는 내용을 설명하고 확인된 상품 사양·원화 가격만 입력한다. 이 정보는 모델에 참고 데이터로 전달하며 명령으로 취급하지 않도록 지시한다. 효과·후기·할인율·사용 경험·상품 외형을 새로 만들어내지 않도록 지시한다.
3. 비용 확인 후 Gemini 대본을 요청한다. 원본 순서대로 가변 개수의 장면에 대응하도록 하며, actor/avatar/lipsync나 새 시각 자료를 요구하지 않는다. 반환된 장면 ID가 승인한 목록/순서와 다르면 실패 처리한다.
4. 한국어 내레이션을 직접 검토/수정한다. 원본과 대본의 실제 내용·광고/제휴 고지를 확인하고 비용에 다시 동의한 뒤 제작한다. 대본의 사실성은 모델 지시만으로 보장되지 않으므로 사용자 검토가 필수다.
5. 구성된 Gemini 모델로 TTS를 만들고 기존 Whisper의 실제 오디오 단어 시각으로 한국어 ASS를 만든다. 로컬 FFmpeg/ffprobe와 faster-whisper 설치가 없으면 유료 TTS 전에 실패한다. 모델 가중치·폰트·GPU/CPU 환경까지 모두 사전 보장하는 것은 아니므로 실제 환경 검증은 남는다.
6. 승인된 원본만 720×1280, 30fps, H.264/AAC MP4로 합성한다. 사진은 선택한 Ken Burns 움직임을 적용하고 원본 영상은 선택 구간만 사용한다. 음성이 더 길면 선택 구간의 마지막 프레임을 정지 표시한다. 원본 영상의 소리는 제거한다. 컷/페이드 전환, 선택한 별도 권리 확인 음원의 음량(0~0.4) 혼합을 지원한다.
7. 실제 출력 스트림·크기·길이를 검사한 파일만 완료로 처리하고 MP4를 내려받는다. 결과 미리보기는 인증한 다운로드 응답의 blob을 사용한다.

크롭·줌·팬은 사용자가 선택하는 편집 효과이며 제품 성능이나 실제 사용 장면을 생성하는 기능이 아니다. 실제 결과의 상품 가독성·가격·후기·효능·고지를 게시 전에 확인해야 한다.

## API

| 경로 | 역할 |
|---|---|
| GET `/api/saasshorts/product/providers` | 공급자별 사용 가능 여부, 개별 기능, 필수 키, 비용 안내 |
| POST `/api/saasshorts/product/assets` | multipart file + kind(video/image/music) + rights_confirmed |
| GET `/api/saasshorts/product/assets/{id}` | 소유자 검사 후 비공개 원본 응답 |
| POST `/api/saasshorts/product/analyze` | 명시적으로 승인한 대본 요청 ID 접수 |
| POST `/api/saasshorts/product/generate` | 승인한 대본·원본으로 제품형 제작 접수 |
| GET `/api/saasshorts/product/requests/{id}` | 요청 접수/대기/처리/완료/실패/중단/만료 조회 |
| GET `/api/saasshorts/product/download/{id}` | 소유자 확인 및 실제 완료 파일 검사 후 MP4 |
| GET `/api/saasshorts/paid-request/{id}` | 기존 배우형의 선택적 요청 ID 상태 조회(유료 재전송 없음) |

제품 요청 예시:

```json
{
  "request_id": "유효한 UUID",
  "scenes": [{"asset_id":"업로드 UUID", "start":0, "end":3, "duration":3, "crop":"center", "motion":"zoom", "note":"실제 상품 정면"}],
  "description":"확인된 상품 정보",
  "rights_confirmed":true,
  "paid_confirmed":true,
  "content_confirmed":true,
  "script":{"production_mode":"product", "language":"ko", "full_narration":"검토한 내레이션", "segments":[{"asset_id":"업로드 UUID"}]},
  "voice":"Kore",
  "transition":"fade",
  "music_id":null,
  "music_volume":0.12
}
```

`analyze`에는 script를 생략한다. 장면 최대 10개, 메모 400자/장면, 상품 정보 4,000자, 내레이션 1,200자, 실제 TTS 길이는 최대 120초로 제한한다. Gemini 대본이 더 길거나 실제 음성이 범위를 넘으면 자동 유료 재요청 없이 실패한다.

## 필수 키·비용·Gemini 검증 한계

- 제품형: Gemini 사용자 키만 필요하다. 기존 Settings의 키를 X-Gemini-Key로 보내며 self-host는 GEMINI_API_KEY도 사용할 수 있다. 호스팅에서도 사용자 키를 사용하고 기존 managed 과금 키를 새 경로에 임의 사용하지 않는다.
- 배우형: 기존 fal.ai 키와 선택한 TTS 키가 필요하다. 한국어 Gemini 경로는 ElevenLabs 키 없이 유지한다.
- 제품형 fal.ai 호출 비용은 $0이며 fal.ai를 호출하지 않는다. 그러나 Gemini 대본/TTS와 로컬 컴퓨팅은 무료라고 보장하지 않는다. 모델 요금표 미확인으로 예상 금액은 null/요금 미확인으로 표시하고 사용자에게 실행 전 확인을 요구한다. 실패도 과금될 수 있다.
- **보존한 기본 TTS 모델 `gemini-3.8-flash-lite-tts`의 실제 존재/계정 지원/가격은 여전히 미확인이다.** 공식 문서 프록시 403, 실제 API 키 없음으로 실서비스 검증을 수행하지 못했다. 기본 모델이 정상 작동한다고 단정하지 않는다. 실제 계정에서 검증한 모델이 있으면 GEMINI_TTS_MODEL로 명시적으로 설정해야 한다. 조회 실패 시 TTS를 호출하지 않고, AUDIO 출력·음성 품질은 조회만으로 증명되지 않는다.
- 기존 고정 SDK 1.75.0 호환성은 HTTP MockTransport를 통한 실제 SDK 직렬화/파싱으로 검증했다. 자세한 한계는 GEMINI_TTS_PROVIDER.md도 참고한다.

## 권한·실패·중복 요청 보호

원본·결과·요청 DB는 `UPLOAD_DIR/product_studio`에 저장하며 공개 `/videos`에 올리지 않는다. 기존 entitlement/소유자 검사를 사용하고 업로드 ID는 UUID만 허용한다. self-host는 기존 프로그램처럼 단일 신뢰 사용자 경계이며 다중 사용자 인증을 새로 추가하지 않았다.

파일당 100 MB, 원본 영상/음원 10분 이하, 영상 4K 이하, 사진 PNG/JPEG/WebP 24 MP 이하를 검사한다. 파일 확장자만 믿지 않고 실제 파싱한다. FFprobe/FFmpeg의 프로토콜과 입력 demuxer를 제한해 업로드를 위장한 외부 플레이리스트/URL 접근을 차단한다. 외부 원본 URL 다운로드 기능은 추가하지 않는다.

작업 파일 유효기간은 24시간이고 새 업로드 시 만료 파일을 정리한다. 작업 파일 총량이 2 GB를 초과하면 추가 업로드를 거절한다. 이 정리는 장기 보관/정기 스케줄러가 아니다. 사용하지 않는 동안 만료 파일이 즉시 물리 삭제되는 것은 아니며 운영 디스크 모니터링이 필요하다. 기존 계정 삭제 hook에서 해당 소유자의 비공개 원본·결과도 제거한다. request ID tombstone은 남겨 같은 유료 작업을 재실행하지 않는다.

SQLite는 BEGIN IMMEDIATE로 요청 ID와 내용 hash를 원자적으로 예약한다. 동일 ID/동일 내용은 기존 상태만 반환하며 다른 내용으로 재사용하면 409다. 유료 실패·서버 재시작·만료 후에도 같은 ID를 다시 실행하지 않는다. 키를 DB·manifest·sessionStorage에 저장하지 않는다. 승인 원본 참조와 권리/내용/비용 확인 시각은 비공개 작업 manifest에 기록한다.

브라우저는 동기 제출 잠금과 sessionStorage 요청 ID를 사용하고 응답 유실/새로고침 후 GET 조회만 재개한다. 접수 여부가 불명확하거나 작업 중단이면 관리자 확인 후에만 잠금을 명시적으로 해제한다. 정상적인 새 ID의 명시적 재시도는 별도 과금될 수 있다. 서로 다른 ID로 사용자가 새로 확인한 요청을 하나의 요청으로 deduplicate하는 것은 아니다.

배우형의 analyze/generate/actor-options도 새 UI에서는 비용 확인과 요청 ID를 보낸다. 선택 필드 없는 기존 API 클라이언트는 기존 호환 동작을 유지하므로 해당 클라이언트 자체의 재시도 정책은 별도 책임이다. 새 공급자 경로에서 자동 유료 fallback은 없다.

현재 실행 태스크는 기존 앱과 같이 프로세스 내부이다. 같은 SQLite 경로를 쓰면 중복 유료 접수는 막지만, 여러 프로세스의 작업 소유/실행 상태를 조정하는 분산 큐는 아니다. 다른 프로세스가 실행 중인지 알 수 없으면 중단/확인 필요로 표시하고 자동 재실행하지 않는다. 재시작한 미완료 유료 작업을 자동 복구하지 않는다.

## 공식 Kling/LTX 타당성 조사

접근 시도: https://klingai.com/global/dev/document-api 및 https://docs.ltx.video/ 는 모두 환경 프록시의 403 Forbidden이었다. 따라서 현재 공식 API의 인증 방식, 계약·상업 이용/원본 보관 조건, 지원 모델·출력/오디오·한국어 립싱크, 요금, 계정 개방 상태를 확인하지 못했다. fal.ai에서 Kling 모델을 쓸 수 있다는 사실은 Kling 공식 API 계약·권한과 같지 않다. 공개 LTX 모델 코드가 존재한다는 사실도 공식 호스팅 API 계약을 의미하지 않는다.

UI의 Kling/LTX 항목은 미구현·미확인이고 선택할 수 없다. 기능별 capabilities는 null(미확인)이며 지원한다고 추정하지 않는다. 후속 구현 전 확인할 조건:

1. 공식 문서/계정으로 인증·모델·이미지 생성/이미지→영상/아바타/립싱크 각각의 지원과 상업 이용·출처 보존 조건 확인
2. 업로드 URL/파일 크기·길이·해상도·출력 코덱·음성 입력 지원 확인
3. idempotency 키, 접수 job ID, 상태/취소/웹훅, 오류·타임아웃 후 비용/중복 청구 규칙 확인
4. 실제 견적과 소량 승인 테스트 후 capability를 활성화. 접수 여부 불명 시 새 유료 요청 대신 기존 작업 조회

제품형은 이들 공식 API 없이 동작하는 로컬 합성 경로이므로 후속 조사에 막히지 않는다. 단, 실제 Gemini TTS 모델 이용 가능 여부는 별도 선행 조건이다.

## 테스트와 남은 검증

외부 유료 API는 모두 mock이다. 실제 원본 상품·유료 TTS/영상 API를 호출하지 않았다.

| 검사 | 결과 |
|---|---|
| 신규 제품·공급자·권한·요청 ID·실제 FFmpeg 백엔드 | 19 통과 |
| 전체 Python | 1377 통과, 29 skip, 기존 DNS/URL 보안 관련 8 실패 |
| 전체 데스크톱·모바일 Playwright | 98 통과 |
| 최종 사진 움직임 변경 관련 브라우저 | 4 통과 |
| Node 유틸리티·프록시 | 12 통과 |
| 고정 Google GenAI SDK 1.75.0 TTS/제품 관련 검사 | 34 통과 |
| production build·변경 영역 ESLint | 통과 |

실제 FFmpeg 테스트는 직접 생성한 영상·사진·음원/합성 오디오와 mock ASR 단어를 사용한다. 승인 원본 업로드/파싱, 구간 선택, 줌·팬, 좌/우 9:16 크롭, 페이드/컷, 배경음 혼합, 기존 한글 ASS 작성/렌더, H.264/AAC 출력, 전체 MP4 디코딩을 확인했다. 브라우저 테스트는 실제 합성 MP4 바이트를 미리보기/다운로드하고 바이트 일치를 확인한다. 실물 상품 영상에서 실제 한국어 발화가 정확했다는 검증은 아니다.

기존 전체 Python 실패 8개는 test_partial_processing 2개, test_process_handover 1개, test_short_source_gate 4개, test_yt_clients 1개로 기존 환경의 DNS/URL 검사 실패와 동일하다. 테스트/보안 검사를 비활성화하지 않았다. CI는 실제 FFmpeg 검증용 도구·폰트 설치를 추가했으나 원격 CI 성공은 미확인이다.

```bash
.venv/bin/python -m pytest tests/test_product_video.py -q
.venv/bin/python -m pytest tests/ -q
cd dashboard
npm run test:unit
npm run test:discovery
VITE_DISCOVERY_ENABLED=1 npm run build
npx eslint src/features/product-video src/components/SaaShortsTab.jsx src/components/AdvancedBanner.jsx src/App.jsx tests/discovery/product-video.spec.js tests/discovery/korean-shorts.spec.js --max-warnings 0
```

실제 운영 전에는 Gemini 모델·요금/계정·키, faster-whisper와 모델 가중치, 한국어 발음·브랜드/원화 읽기·자막 싱크, 사진/영상 회전·크롭·음원 밸런스, Docker 전체 빌드·Windows 실행·동시 사용자 권한, 디스크/만료 운영을 확인해야 한다. 한국어 립싱크의 실제 품질은 기존 배우형에서 별도 검수한다. 제품형은 립싱크를 요구하거나 수행하지 않는다.
