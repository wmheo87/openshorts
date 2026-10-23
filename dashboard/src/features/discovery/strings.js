export const text = {
  title: 'Video Discovery',
  intro: '키워드로 영상을 찾고, 원본 정보와 추천 근거를 비교하세요.',
  scoreNotice: '추천 점수는 조회수·경과일·일평균 조회수·키워드 관련성을 이용한 자체 휴리스틱입니다. 바이럴 성공 확률이나 YouTube 공식 지표가 아닙니다.',
  rightsNotice: 'CC BY 표시만으로 음악, 인물, 삽입 콘텐츠 등 모든 이용 권리가 보장되지는 않습니다. 원본 출처, 적용 라이선스와 표시 의무를 직접 확인하세요.',
  selectionNotice: '선택과 체크만으로 제작하지 않습니다. 제작 버튼을 누르면 확인한 원본 정보가 해당 작업에 기록됩니다. 영구 프로젝트 보관은 제공하지 않습니다.',
  historyNotice: '검색 조건과 실행 이력입니다. 과거 영상 결과 전체를 영구 보관한 목록은 아닙니다. 다시 검색하면 서버 캐시 또는 최신 API 결과를 조회합니다.',
};

export const errorMessages = {
  discovery_disabled: '서버의 영상 탐색 기능이 꺼져 있습니다. 관리자가 DISCOVERY_ENABLED=1로 활성화해야 합니다.',
  provider_not_configured: '서버에 YouTube API 키가 설정되지 않았습니다. 관리자에게 YOUTUBE_API_KEY 설정을 요청하세요. 키를 이 화면에 입력하지 마세요.',
  discovery_configuration_error: '탐색 서버 설정 또는 SQLite 저장 경로를 확인해 주세요.',
  discovery_storage_unavailable: '검색 이력 저장소를 사용할 수 없습니다. 잠시 후 상태를 확인해 주세요.',
  rate_limited: '검색 요청 제한에 도달했습니다. 잠시 후 직접 다시 검색해 주세요.',
  discovery_busy: '서버가 다른 검색을 처리하고 있습니다. 잠시 후 다시 검색해 주세요.',
  local_quota_exceeded: '탐색 서버의 일별 API 호출 예산을 모두 사용했습니다. 관리자에게 확인해 주세요.',
  youtube_quota_exceeded: 'YouTube API 할당량을 모두 사용했습니다. 관리자에게 할당량을 확인해 주세요.',
  provider_rate_limited: 'YouTube API 요청이 제한되었습니다. 잠시 후 직접 다시 시도해 주세요.',
  provider_access_denied: 'YouTube API 접근이 거부됐습니다. 관리자가 키 제한과 API 활성화 설정을 확인해야 합니다.',
  invalid_provider_response: 'YouTube에서 올바르지 않은 응답을 받았습니다. 잠시 후 다시 시도해 주세요.',
  provider_unavailable: 'YouTube API에 연결할 수 없습니다. 서버의 네트워크 상태를 확인해 주세요.',
  provider_timeout: 'YouTube API 응답이 지연되어 서버가 검색을 중단했습니다.',
  client_timeout: '서버 응답 대기 시간이 초과됐습니다. 서버에서는 검색이 계속될 수 있으니 이력을 확인한 뒤 다시 시도해 주세요.',
  cancelled: '화면에서 응답 대기를 중단했습니다. 서버에서는 검색이 계속될 수 있습니다.',
  network_error: '서버에 연결할 수 없습니다. 인터넷 연결과 API 프록시 설정을 확인해 주세요.',
  invalid_response: '탐색 서버의 응답 형식이 올바르지 않습니다. 연결 대상을 확인해 주세요.',
};

export function errorMessage(code, status) {
  if (errorMessages[code]) return errorMessages[code];
  return ({
    422: '검색 조건이 올바르지 않습니다. 검색어, 숫자 범위와 날짜를 확인해 주세요.',
    429: '요청 또는 할당량 제한에 도달했습니다. 잠시 후 직접 다시 시도해 주세요.',
    502: '외부 API 또는 프록시 연결에 문제가 있습니다.',
    503: '영상 탐색 서비스를 사용할 수 없습니다. 서버 설정을 확인해 주세요.',
    504: '서버 응답 시간이 초과됐습니다. 잠시 후 다시 확인해 주세요.',
  })[status] || '요청을 완료하지 못했습니다. 잠시 후 직접 다시 시도해 주세요.';
}
