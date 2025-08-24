export const ENDPOINTS = {
  // JD 생성 (SSE)
  GENERATE_STREAM: '/generate/stream',
  // 대시/프리뷰 (큐/ETA/품질 등)
  DASH_PREVIEW: '/dash/jd/preview',
  // 인기 공고/댓글
  POPULAR_POSTS: '/posts/popular',
  POST_COMMENTS: (id: string) => `/posts/${id}/comments`,
  // 실시간 채용시장
  INSIGHT_MARKET: '/insight/market',
  // 리플레이/레이더
  REPLAY: '/replay/performance',
  RADAR: '/radar/competitors',
  // 크롤링
  COLLECT: '/collect/jobkorea'
}

