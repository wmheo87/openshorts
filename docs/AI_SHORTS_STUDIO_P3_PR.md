# Video Discovery에서 기존 AI Clip Generator로 제작 연결

선택 영상의 이용 권리와 다운로드 허용을 각각 확인한 후 기존 handleProcess와 /api/process로 제작한다. 목표 수·길이·후킹 옵션을 기존 엔진에 전달하고 기존 큐, 폴링, 결과 플레이어 및 MP4 다운로드를 재사용한다. 접수 전 fresh videos.list 재확인과 P1 예산을 적용하며 기존 URL 보안·길이·품질 게이트를 유지한다.

- 전송 중 중복 클릭 방지, 응답 유실·시간초과 후 자동 재제출 차단, 명시적 재시도
- 작업 출처 보존과 기존 복구 연결, 누락/만료 결과 파일 감지
- 단일 백엔드 Docker overlay 및 named SQLite volume
- P0~P2를 포함한 main 562ce9b 위에 P3만 추가; cloud/·AI 알고리즘·P4 변경 없음

검증: P3 Python 21 통과, Node 12 통과, 데스크톱·모바일 Playwright 80 통과, build/변경 영역 ESLint/Compose 설정 검사 통과. 전체 Python은 1312 통과·29 skip·변경 전과 동일한 DNS 관련 8 실패이며 전체 린트는 기존 10 오류가 남는다.

합성 9:16 MP4의 브라우저 디코딩·재생·다운로드는 확인했다. 실제 API 키·로컬 모델이 없어 전체 AI 제작 실영상 검증과 Windows Docker 실행은 미검증이다. 서버 idempotency가 없으므로 탭/클라이언트 간 중복 방지는 보장하지 않는다.

실행·API·한계·테스트 상세: docs/STUDIO_DISCOVERY_ENGINE.md
