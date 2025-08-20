-- postgres/init/init.sql
-- =========================================
-- 기본 확장
-- =========================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =========================================
-- 테이블: raw_job_descriptions (크롤링 원본)
-- =========================================
CREATE TABLE IF NOT EXISTS raw_job_descriptions (
  id            BIGSERIAL PRIMARY KEY,
  source        TEXT NOT NULL,                            -- "jobkorea"
  company_code  TEXT NOT NULL,
  job_code      TEXT NOT NULL,
  job_id        TEXT NOT NULL,                            -- 사이트 내 공고 식별자
  url           TEXT NOT NULL,
  title         TEXT,
  jd_text       TEXT,
  crawled_date  DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_rawjd_source_jobid
  ON raw_job_descriptions (source, job_id);

-- =========================================
-- 테이블: generated_insights (LLM 결과 저장)
--  - 회사/직무 레벨 결과 저장을 위해 jd_id NULL 허용
-- =========================================
CREATE TABLE IF NOT EXISTS generated_insights (
  id            BIGSERIAL PRIMARY KEY,
  jd_id         BIGINT REFERENCES raw_job_descriptions(id) ON DELETE SET NULL,
  company_code  TEXT NOT NULL,
  job_code      TEXT NOT NULL,
  analysis_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  llm_text      TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================
-- 테이블: jd_styles (스타일 매핑)
-- =========================================
CREATE TABLE IF NOT EXISTS jd_styles (
  style_id       SERIAL PRIMARY KEY,
  style_name     TEXT UNIQUE NOT NULL,
  prompt_key     TEXT,
  prompt_version TEXT,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================
-- 테이블: prompts (DB 기반 프롬프트 관리)
-- =========================================
CREATE TABLE IF NOT EXISTS prompts (
  id              SERIAL PRIMARY KEY,
  prompt_key      TEXT NOT NULL,
  prompt_version  TEXT NOT NULL,
  language        TEXT,
  prompt_type     TEXT NOT NULL,              -- 'chat' | 'string'
  messages        JSONB,
  template        TEXT,
  params          JSONB NOT NULL DEFAULT '{}'::jsonb,
  json_schema_key TEXT,
  required_vars   JSONB NOT NULL DEFAULT '[]'::jsonb,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_prompt UNIQUE (prompt_key, prompt_version, COALESCE(language, ''))
);

-- =========================================
-- 코드 맵핑(선택): 직무코드 시드
-- =========================================
CREATE TABLE IF NOT EXISTS job_codes (
  code  TEXT PRIMARY KEY,
  name  TEXT NOT NULL
);
INSERT INTO job_codes (code, name) VALUES
('1000201', '인사담당자'),
('1000242', 'AI/ML엔지니어'),
('1000229', '백엔드개발자'),
('1000230', '프론트엔드개발자'),
('1000187', '마케팅기획'),
('1000210', '재무담당자')
ON CONFLICT (code) DO NOTHING;

-- =========================================
-- 프롬프트 시드 (키/버전/언어)
--  * 필요 시 내용만 변경해서 사용
-- =========================================
INSERT INTO prompts (prompt_key, prompt_version, language, prompt_type, messages, params, json_schema_key, required_vars)
VALUES
(
  'company.analysis.knowledge', 'v1', 'ko', 'chat',
  '[
     {"role":"system","content":"너는 채용공고를 구조화하는 전문가다. 출력은 JSON 스키마를 반드시 준수한다."},
     {"role":"user","content":"회사: {{ company_name }}\\n직무: {{ job_name }}\\n아래는 최근 JD 일부다. 핵심만 추려 JSON으로 정리해라.\\n---\\n{{ concatenated_jds }}"}
   ]'::jsonb,
  '{"temperature":0.1}'::jsonb,
  'company_knowledge_v1',
  '["company_name","job_name","concatenated_jds"]'::jsonb
),
(
  'company.analysis.job_competency_zero_shot', 'v1', 'ko', 'chat',
  '[
     {"role":"system","content":"너는 한국 채용시장 기준으로 직무 역량/기술을 도출하는 전문가다."},
     {"role":"user","content":"회사: {{ company_name }}\\n직무: {{ job_name }}\\n사전 자료 없이도 일반적인 JD 기준으로 JSON을 생성해라."}
   ]'::jsonb,
  '{"temperature":0.3}'::jsonb,
  'company_knowledge_v1',
  '["company_name","job_name"]'::jsonb
),
(
  'company.analysis.jd_style', 'v1', 'ko', 'chat',
  '[
     {"role":"system","content":"너는 JD 문체/섹션/톤을 추출해 템플릿으로 만드는 컨설턴트다."},
     {"role":"user","content":"회사: {{ company_name }}\\n직무: {{ job_name }}\\n아래 JD 샘플들의 공통 스타일을 요약하고 해당 스타일의 예시 JD(Markdown)를 생성해라.\\n---\\n{{ concatenated_jds }}"}
   ]'::jsonb,
  '{"temperature":0.2}'::jsonb,
  'company_jd_style_v1',
  '["company_name","job_name","concatenated_jds"]'::jsonb
)
ON CONFLICT DO NOTHING;
