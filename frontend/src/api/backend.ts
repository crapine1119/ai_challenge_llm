// src/api/backend.ts
import { http } from './http'
import type {
  ApiResponse,
  CrawlRequest,
  CrawlResponse,
  GuardrailCheckRequest,
  GuardrailCheckResponse,
  JDGenerateRequest,
  JDGenerateStreamEnd,
  JDGenerateStreamStart,
  JDItem,
  JDListQuery,
  JDListResponse,
  JDPreviewProgress,
  GeneratedStyle,
  StylePreset,
  TaskStatusResponse
} from './types'
import type { JDTemplate, GeneratedStyle, StylePreset, SearchResponse } from './types'


/** Health */
export const getHealth = async () => (await http.get<string>('/healthz')).data

/** 크롤링 */
export const postCollectJobKorea = async (data: CrawlRequest) =>
  (await http.post<CrawlResponse>('/api/collect/jobkorea', data)).data

/** 스타일 */
export const getStylePresets = async () =>
  (await http.get<StylePreset[]>('/api/styles/presets')).data

export const getStylePresetByName = async (name: string) =>
  (await http.get<StylePreset>(`/api/styles/presets/${encodeURIComponent(name)}`)).data

export const getGeneratedStyleLatest = async (company_code: string, job_code: string) =>
  (await http.get<GeneratedStyle>('/api/styles/generated/latest', { params: { company_code, job_code } })).data

export const getGeneratedStyleList = async (params: { company_code: string; job_code: string; limit?: number; offset?: number }) =>
  (await http.get<GeneratedStyle[]>('/api/styles/generated', { params })).data

/** Company Analysis */
export const postZeroShotKnowledge = async (payload: any) =>
  (await http.post('/api/company-analysis/knowledge/zero-shot', payload)).data

export const postAnalyzeAll = async (payload: any) =>
  (await http.post('/api/company-analysis/analyze-all', payload)).data

export const postFewShotKnowledge = async (payload: any) =>
  (await http.post('/api/company-analysis/knowledge/few-shot', payload)).data

export const postStyleAnalysis = async (payload: any) =>
  (await http.post('/api/company-analysis/style', payload)).data

/** JD 생성 (non-stream) */
export const postGenerateJD = async (payload: JDGenerateRequest) =>
  (await http.post('/api/jd/generate', payload)).data

/** SSE는 fetch로 처리하므로 endpoints 문자열만 export */
export const ENDPOINTS = {
  GENERATE_STREAM: '/api/jd/generate/stream',
  DASH_PREVIEW: '/api/dash/jd/preview',
  QUEUE_SIM_THEN_GENERATE: '/api/llm/queue/sim-then-generate',
  TASK_STATUS: (taskId: string) => `/api/llm/queue/tasks/${taskId}/status`,
  TASK_RESULT: (taskId: string) => `/api/llm/queue/tasks/${taskId}/result`,
  TASK_EVENT: (taskId: string) => `/api/llm/queue/tasks/${taskId}/event`,
  GUARDRAIL_CHECK: '/api/guardrail/check',
  JD_LATEST: '/api/jd/latest',
  JD_BY_ID: (id: string) => `/api/jd/${id}`,
  JD_LIST: '/api/jd'
}

/** 목록/조회 */
export const getLatestJD = async (company_code: string, job_code: string) =>
  (await http.get(ENDPOINTS.JD_LATEST, { params: { company_code, job_code } })).data

export const getJDById = async (id: string) =>
  (await http.get(ENDPOINTS.JD_BY_ID(id))).data

export const getJDList = async (params: JDListQuery) =>
  (await http.get<JDListResponse | ApiResponse<JDListResponse>>(ENDPOINTS.JD_LIST, { params })).data

/** Queue/Sim */
export const postSimThenGenerate = async (payload: any) =>
  (await http.post(ENDPOINTS.QUEUE_SIM_THEN_GENERATE, payload)).data

export const getTaskStatus = async (taskId: string) =>
  (await http.get<TaskStatusResponse>(ENDPOINTS.TASK_STATUS(taskId))).data

export const getTaskResult = async (taskId: string) =>
  (await http.get(ENDPOINTS.TASK_RESULT(taskId))).data

export const getTaskEvent = async (taskId: string) =>
  (await http.get(ENDPOINTS.TASK_EVENT(taskId))).data

/** Guardrail */
export const postGuardrailCheck = async (data: GuardrailCheckRequest) =>
  (await http.post<GuardrailCheckResponse>(ENDPOINTS.GUARDRAIL_CHECK, data)).data

import type { CompanyBrief, JobBrief, SearchResponse } from './types'

// [가정] 카탈로그 엔드포인트 (백엔드 준비되면 바로 연동)
//   GET /api/catalog/companies?query=잡코&limit=10
//   GET /api/catalog/jobs?query=백엔드&limit=10
export const searchCompanies = async (query: string, limit = 10) => {
  try {
    const res = await http.get<SearchResponse<CompanyBrief>>('/api/catalog/companies', { params: { query, limit } })
    // 백엔드가 배열만 주는 경우 호환
    const data = Array.isArray(res.data) ? { items: res.data } : res.data
    return data.items || []
  } catch {
    return []
  }
}

export const searchJobs = async (query: string, limit = 10) => {
  try {
    const res = await http.get<SearchResponse<JobBrief>>('/api/catalog/jobs', { params: { query, limit } })
    const data = Array.isArray(res.data) ? { items: res.data } : res.data
    return data.items || []
  } catch {
    return []
  }
}

/** 선택값 검증(선택): 조합이 유효한지 간단 체크.
 * 1순위: /api/styles/generated/latest (존재하면 OK)
 * 2순위: /api/jd/latest (존재하면 OK)
 */
export const validateCompanyJob = async (company_code: string, job_code: string) => {
  try {
    await http.get(ENDPOINTS.JD_LATEST, { params: { company_code, job_code } })
    return true
  } catch {
    try {
      await http.get('/api/styles/generated/latest', { params: { company_code, job_code } })
      return true
    } catch {
      return false
    }
  }
}

// backend.ts — 수집 목록 API 업데이트
import type { CompanyBrief, JobBrief, SearchResponse } from './types'


// 내부 타입 가드
const hasCompanies = (d: any): d is { companies: string[] } =>
  d && Array.isArray(d.companies)

const hasJobs = (d: any): d is { company_code?: string; jobs: { code: string; name: string }[] } =>
  d && Array.isArray(d.jobs)

/** 수집된 회사 목록 */
export const getCollectedCompanies = async (limit = 500): Promise<CompanyBrief[]> => {
  // 1) 실제 운영 엔드포인트: {"companies": ["jobkorea", ...]}
  try {
    const r = await http.get('/api/catalog/companies/collected', { params: { limit } })
    const data = r.data
    if (hasCompanies(data)) {
      return data.companies.map((code: string) => ({
        company_code: code,
        name: code // 사람이 읽을 이름이 없으므로 일단 code로 대체(추후 매핑 가능)
      }))
    }
  } catch (_) {
    // noop
  }

  // 2) 폴백: 통합 companies 엔드포인트 (SearchResponse<CompanyBrief> | CompanyBrief[])
  try {
    const r = await http.get<SearchResponse<CompanyBrief> | CompanyBrief[]>('/api/catalog/companies', { params: { limit } })
    const data = r.data as any
    if (Array.isArray(data)) {
      return data
    }
    if (data && Array.isArray(data.items)) {
      return data.items
    }
  } catch {
    // noop
  }

  return []
}

/** 수집된 직무 목록(회사 선택 시 해당 회사 기준) */
export const getCollectedJobsForCompany = async (company_code?: string, limit = 500): Promise<JobBrief[]> => {
  // 1) 실제 운영 엔드포인트: {"company_code":"jobkorea","jobs":[{"code":"1000242","name":"AI/ML 엔지니어"}]}
  try {
    const r = await http.get('/api/catalog/jobs/collected', { params: { company_code, limit } })
    const data = r.data
    if (hasJobs(data)) {
      return data.jobs.map(j => ({
        job_code: j.code,
        name: j.name
      }))
    }
  } catch (_) {
    // noop
  }

  // 2) 폴백: 통합 jobs 엔드포인트 (SearchResponse<JobBrief> | JobBrief[])
  try {
    const r = await http.get<SearchResponse<JobBrief> | JobBrief[]>('/api/catalog/jobs', { params: { company_code, limit } })
    const data = r.data as any
    if (Array.isArray(data)) {
      return data
    }
    if (data && Array.isArray(data.items)) {
      return data.items
    }
  } catch {
    // noop
  }

  return []
}


export const getJDTemplates = async (params: { company_code?: string; job_code?: string; limit?: number }) => {
  // 1) 권장: 전용 템플릿 엔드포인트가 있으면 사용
  try {
    const r = await http.get<SearchResponse<JDTemplate> | JDTemplate[]>('/api/jd/templates', { params })
    const data = Array.isArray(r.data) ? { items: r.data } : r.data
    const list = (data as any)?.items as JDTemplate[] | undefined
    if (list && list.length) return list.map(t => ({ ...t, source: 'db' as const }))
  } catch {/* noop */}

  // 2) 대안: generated style → 템플릿 1개 합성
  let fromGenerated: JDTemplate[] = []
  try {
    const g: GeneratedStyle = await (await http.get('/api/styles/generated/latest', { params })).data
    if (g?.templates) {
      const sections = Object.keys(g.templates)
      const body = sections.map(k => g.templates[k]).join('\n')
      const summary = (body || '').replace(/\n+/g, ' ').slice(0, 160) + '…'
      fromGenerated = [{
        id: `gen:${params.company_code || ''}:${params.job_code || ''}`,
        name: g.style_label || 'Generated Style',
        summary,
        sections,
        source: 'generated',
        style_label: g.style_label
      }]
    }
  } catch {/* noop */}

  // 3) 대안: preset 상위 2~3개 → 템플릿 합성
  let fromPreset: JDTemplate[] = []
  try {
    const presets: StylePreset[] = await (await http.get('/api/styles/presets')).data
    fromPreset = (presets || []).slice(0, 3).map(p => ({
      id: `preset:${p.name}`,
      name: p.name,
      summary: (p.templates?.[p.section_outline?.[0] || 'About'] || '').replace(/\n+/g, ' ').slice(0, 140) + '…',
      sections: p.section_outline || Object.keys(p.templates || {}),
      source: 'preset'
    }))
  } catch {/* noop */}

  const merged = [...fromGenerated, ...fromPreset]
  return merged
}


import type {
  CompanyAnalysisRequest,
  CompanyAnalyzeAllRequest,
  GeneratedStyleLatestResponse,
  JDGenerateAPIRequest,
  JDGenerateParsed,
  StylePresetItem,
  StylePresetsResponse
} from './types'

/* ------------------------------ 회사 분석 ------------------------------ */

export const postCompanyZeroShot = async (payload: CompanyAnalysisRequest) => {
  const { data } = await http.post('/api/company-analysis/knowledge/zero-shot', payload)
  return data
}

export const postCompanyAnalyzeAll = async (payload: CompanyAnalyzeAllRequest) => {
  const { data } = await http.post('/api/company-analysis/analyze-all', payload)
  return data
}

/* -------------------------------- 스타일 -------------------------------- */

export const getStylePresetsFull = async (): Promise<StylePresetItem[]> => {
  const { data } = await http.get<StylePresetsResponse | any>('/api/styles/presets')
  if (Array.isArray(data?.items)) return data.items as StylePresetItem[]
  // 혹시 배열만 오면
  if (Array.isArray(data)) return data as StylePresetItem[]
  return []
}

export const getLatestGeneratedStyle = async (company_code: string, job_code: string) => {
  const { data } = await http.get<GeneratedStyleLatestResponse>('/api/styles/generated/latest', {
    params: { company_code, job_code }
  })
  return data?.latest // 없을 수도 있음
}

/* ------------------------------- JD 생성기 ------------------------------- */

// FastAPI가 repr 문자열(JDGenerateResponse(...))을 내보내도 파싱되도록 보강
function parseJDGenerateResponse(raw: any): JDGenerateParsed {
  if (!raw) return { markdown: '' }

  // 1) JSON인 경우
  if (typeof raw === 'object') {
    // backend가 { markdown, saved_id, title? } 형태로 주는 경우
    if (typeof raw.markdown === 'string') {
      return { markdown: raw.markdown, saved_id: raw.saved_id, title: raw.title }
    }
    // 혹은 data 래핑
    if (raw.data && typeof raw.data.markdown === 'string') {
      return { markdown: raw.data.markdown, saved_id: raw.data.saved_id, title: raw.data.title }
    }
  }

  // 2) repr 문자열인 경우: JDGenerateResponse(..., markdown='...', saved_id=29)
  if (typeof raw === 'string') {
    // markdown 추출
    const mdMatch = raw.match(/markdown='([\s\S]*?)'\)/) || raw.match(/markdown='([\s\S]*?)',/)
    const markdown = mdMatch ? mdMatch[1].replace(/\\n/g, '\n') : ''
    // saved_id 추출
    const idMatch = raw.match(/saved_id=(\d+)/)
    const saved_id = idMatch ? Number(idMatch[1]) : undefined
    // title 추출(있으면)
    const titleMatch = raw.match(/title='([^']+)'/)
    const title = titleMatch ? titleMatch[1] : undefined
    return { markdown, saved_id, title }
  }

  return { markdown: '' }
}

export const generateJDWithDefault = async (payload: JDGenerateAPIRequest): Promise<JDGenerateParsed> => {
  const { data } = await http.post('/api/jd/generate', payload)
  return parseJDGenerateResponse(data)
}

export const generateJDWithGenerated = async (payload: JDGenerateAPIRequest): Promise<JDGenerateParsed> => {
  const { data } = await http.post('/api/jd/generate', {
    ...payload,
    style_source: 'generated',
    default_style_name: undefined
  })
  return parseJDGenerateResponse(data)
}

import type { JDListItem, JDListResponse } from './types'

// 최신 JD 3개 조회
export async function getLatestJDs(params: {
  company_code: string
  job_code: string
  limit?: number
}): Promise<JDListItem[]> {
  const { company_code, job_code, limit = 3 } = params
  const { data } = await http.get<JDListResponse>('/api/jd', {
    params: { company_code, job_code, limit }
  })
  // 방어코드: items가 배열인지 확인
  if (data && Array.isArray(data.items)) return data.items
  return []
}

// 회사/직무 수집 (JobKorea)
export const collectJobkorea = async (payload: {
  company_id: number
  job_code: string
  company_code?: string
   // max_details?: number  // ✦ 옵션 제거(있어도 무시)
}) => {
  const body = {
    company_code: 'jobkorea', // 고정
    max_details: 3,
    ...payload
  }
  const r = await http.post('/api/collect/jobkorea', body)
  return r.data
}
