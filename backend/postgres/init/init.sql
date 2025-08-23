-- postgres/init/init.sql
-- =========================================
-- 기본 확장
-- =========================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =========================================
-- 테이블: prompts (DB 기반 프롬프트 관리)  ✅ 먼저 생성 (FK 참조용)
--  - language: NOT NULL + DEFAULT '' 로 정규화
--  - 유니크 제약: (prompt_key, prompt_version, language)
-- =========================================
CREATE TABLE IF NOT EXISTS prompts (
  id              SERIAL PRIMARY KEY,
  prompt_key      TEXT NOT NULL,
  prompt_version  TEXT NOT NULL,
  language        TEXT NOT NULL DEFAULT '',
  prompt_type     TEXT NOT NULL,              -- 'chat' | 'string'
  messages        JSONB,
  template        TEXT,
  params          JSONB NOT NULL DEFAULT '{}'::jsonb,
  json_schema_key TEXT,
  required_vars   JSONB NOT NULL DEFAULT '[]'::jsonb,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  content_hash    TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 과거 스키마 정규화 (기존 DB 호환): language NULL -> '' 및 NOT NULL
UPDATE prompts SET language = '' WHERE language IS NULL;

ALTER TABLE prompts
  ALTER COLUMN language SET DEFAULT '',
  ALTER COLUMN language SET NOT NULL;

-- 과거 잘못된/중복 제약/인덱스 정리
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE t.relname = 'prompts' AND c.conname = 'uq_prompt_key_ver_lang'
  ) THEN
    ALTER TABLE prompts DROP CONSTRAINT uq_prompt_key_ver_lang;
  END IF;
EXCEPTION WHEN undefined_table THEN
  -- 테이블이 없다면 무시 (초기 설치 케이스)
  NULL;
END $$;

DROP INDEX IF EXISTS ux_prompts_key_ver_lang_null;
DROP INDEX IF EXISTS ux_prompts_key_ver_lang_nn;
DROP INDEX IF EXISTS ix_prompts_key_ver_lang;

-- 표준 유니크 제약 재생성 (이름 고정)
ALTER TABLE prompts
  ADD CONSTRAINT uq_prompt_key_ver_lang UNIQUE (prompt_key, prompt_version, language);

-- 조회용 보조 인덱스
CREATE INDEX IF NOT EXISTS ix_prompts_key_ver_lang
  ON prompts (prompt_key, prompt_version, language);

-- =========================================
-- (과거 테이블 정리) job_codes → job_code_map로 통일
-- =========================================
DROP TABLE IF EXISTS job_codes CASCADE;

-- =========================================
-- 코드 맵핑: 직무코드 (ORM: infrastructure.db.models.JobCode → "job_code_map")
-- =========================================
CREATE TABLE IF NOT EXISTS job_code_map (
  job_code TEXT PRIMARY KEY,
  job_name TEXT NOT NULL
);

-- 시드
INSERT INTO job_code_map (job_code, job_name) VALUES
('1000201', '인사담당자'),
('1000242', 'AI/ML 엔지니어'),
('1000229', '백엔드개발자'),
('1000230', '프론트엔드개발자'),
('1000187', '마케팅기획'),
('1000210', '재무담당자')
ON CONFLICT (job_code) DO NOTHING;

-- =========================================
-- 테이블: raw_job_descriptions (크롤링 원본)
--  - end_date 컬럼 사용, job_code NULL 허용
--  - meta_json JSONB 추가 (크롤 메타 저장)
-- =========================================
CREATE TABLE IF NOT EXISTS raw_job_descriptions (
  id            BIGSERIAL PRIMARY KEY,
  source        TEXT NOT NULL,                            -- "jobkorea"
  company_code  TEXT NOT NULL,
  job_code      TEXT,                                     -- NULL 허용 (수집 시 미지정 가능)
  job_id        TEXT NOT NULL,                            -- 사이트 내 공고 식별자
  url           TEXT NOT NULL,
  title         TEXT,
  jd_text       TEXT NOT NULL,
  end_date      DATE NOT NULL DEFAULT CURRENT_DATE,       -- ORM에서 사용
  crawled_date  DATE NOT NULL DEFAULT CURRENT_DATE,       -- 크롤 시점(참고)
  meta_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 고유 제약 표준화: (source, job_id)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE c.conname = 'uq_raw_source_jobid'
      AND t.relname = 'raw_job_descriptions'
  ) THEN
    ALTER TABLE raw_job_descriptions
      ADD CONSTRAINT uq_raw_source_jobid UNIQUE (source, job_id);
  END IF;
END $$;

-- FK: job_code_map(job_code)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE c.conname = 'fk_rawjd_jobcode'
      AND t.relname = 'raw_job_descriptions'
  ) THEN
    ALTER TABLE raw_job_descriptions
      ADD CONSTRAINT fk_rawjd_jobcode
      FOREIGN KEY (job_code) REFERENCES job_code_map(job_code)
      ON DELETE SET NULL;
  END IF;
END $$;

-- 조회 최적화 인덱스
CREATE INDEX IF NOT EXISTS ix_rawjd_company_job ON raw_job_descriptions (company_code, job_code);
CREATE INDEX IF NOT EXISTS ix_rawjd_end_date    ON raw_job_descriptions (end_date DESC);
CREATE INDEX IF NOT EXISTS ix_rawjd_created_at  ON raw_job_descriptions (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_rawjd_meta_json_gin
  ON raw_job_descriptions USING gin (meta_json);

-- =========================================
-- 테이블: generated_insights (LLM 결과 저장)
--  - company/job 레벨 및 개별 JD 레벨 결과 저장
--  - prompts 테이블을 FK로 참조 (prompt_id)
-- =========================================
CREATE TABLE IF NOT EXISTS generated_insights (
  id             BIGSERIAL PRIMARY KEY,
  jd_id          BIGINT REFERENCES raw_job_descriptions(id) ON DELETE SET NULL,
  company_code   TEXT NOT NULL,
  job_code       TEXT,  -- NULL 허용
  analysis_json  JSONB NOT NULL DEFAULT '{}'::jsonb,
  llm_text       TEXT,
  -- 프롬프트 추적(정규화 + 비정규화)
  prompt_id      INTEGER REFERENCES prompts(id) ON DELETE SET NULL,
  prompt_key     TEXT,
  prompt_version TEXT,
  prompt_language TEXT NOT NULL DEFAULT '',
  generated_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- FK: job_code_map(job_code)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE c.conname = 'fk_gi_jobcode'
      AND t.relname = 'generated_insights'
  ) THEN
    ALTER TABLE generated_insights
      ADD CONSTRAINT fk_gi_jobcode
      FOREIGN KEY (job_code) REFERENCES job_code_map(job_code)
      ON DELETE SET NULL;
  END IF;
END $$;

-- 조회 인덱스
CREATE INDEX IF NOT EXISTS ix_gi_company_job ON generated_insights (company_code, job_code);
CREATE INDEX IF NOT EXISTS ix_gi_created     ON generated_insights (generated_date DESC);
CREATE INDEX IF NOT EXISTS ix_gi_prompt_id   ON generated_insights (prompt_id);
CREATE INDEX IF NOT EXISTS ix_gi_prompt_kvl  ON generated_insights (prompt_key, prompt_version, prompt_language);

-- =========================================
-- 테이블: jd_styles (스타일 매핑)
-- =========================================
-- === jd_styles: 프롬프트 매핑 제거, payload_json 추가 ===
CREATE TABLE IF NOT EXISTS jd_styles (
  style_id       SERIAL PRIMARY KEY,
  style_name     TEXT UNIQUE NOT NULL,
  payload_json   JSONB NOT NULL DEFAULT '{}'::jsonb,  -- ← 프리셋 스타일 본문
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 기존 컬럼 정리 (있다면 제거)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='jd_styles' AND column_name='prompt_key') THEN
    ALTER TABLE jd_styles DROP COLUMN prompt_key;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='jd_styles' AND column_name='prompt_version') THEN
    ALTER TABLE jd_styles DROP COLUMN prompt_version;
  END IF;
END $$;

-- 기본 프리셋 3종 시드 (idempotent)
INSERT INTO jd_styles (style_name, payload_json, is_active)
VALUES
  ('일반적', jsonb_build_object(
    'style_label', '일반적',
    'tone_keywords', jsonb_build_array('명료한','공손한','간결한'),
    'section_outline', jsonb_build_array('About Us','Responsibilities','Qualifications','Preferred Qualifications','Hiring Process'),
    'templates', jsonb_build_object(
      'About Us', '우리 팀과 회사의 미션을 간략히 소개합니다.',
      'Responsibilities', '- 핵심 업무를 불릿으로 정리합니다.',
      'Qualifications', '- 필수 요건을 불릿으로 정리합니다.',
      'Preferred Qualifications', '- 우대 사항을 불릿으로 정리합니다.',
      'Hiring Process', '서류 > 인터뷰 > 과제(선택) > 최종합격'
    )
  ), TRUE),
  ('기술 상세', jsonb_build_object(
    'style_label', '기술 상세',
    'tone_keywords', jsonb_build_array('기술중심','정확성','구체성'),
    'section_outline', jsonb_build_array('About Us','Tech Stack','Responsibilities','Qualifications','Preferred Qualifications','Hiring Process'),
    'templates', jsonb_build_object(
      'Tech Stack', 'Python, FastAPI, PostgreSQL, Kafka, Redis, Docker, Kubernetes, AWS',
      'Responsibilities', '- 설계/구현/운영 단계를 구체적으로 기술합니다.',
      'Qualifications', '- 버전/툴/프로토콜 등 구체적인 스펙을 명시합니다.'
    )
  ), TRUE),
  ('Notion', jsonb_build_object(
    'style_label', 'Notion',
    'tone_keywords', jsonb_build_array('트렌디','친화적','심플'),
    'section_outline', jsonb_build_array('About Us','Team','What you will do','What we look for','Nice to have','Process'),
    'templates', jsonb_build_object(
      'About Us', '우리는 사용자에게 최고의 경험을 제공합니다.',
      'What you will do', '• 이렇게 일해요\n• 이렇게 협업해요',
      'What we look for', '• 이런 분을 찾아요'
    )
  ), TRUE)
ON CONFLICT (style_name) DO NOTHING;

-- =========================================
-- 테이블: generated_styles (회사×직무 스타일 스냅샷)
-- =========================================
CREATE TABLE IF NOT EXISTS generated_styles (
  id              BIGSERIAL PRIMARY KEY,
  company_code    TEXT NOT NULL,
  job_code        TEXT,                                -- NULL 허용
  style_label     TEXT NOT NULL DEFAULT '',
  tone_keywords   JSONB NOT NULL DEFAULT '[]'::jsonb,  -- ["혁신적","협업" ...]
  section_outline JSONB NOT NULL DEFAULT '[]'::jsonb,  -- ["About Us","Responsibilities",...]
  templates       JSONB NOT NULL DEFAULT '{}'::jsonb,  -- { "About Us": "...", ... }
  digest_md       TEXT,                                -- 리뷰/검색용 요약 markdown
  -- 프롬프트 추적
  prompt_id       INTEGER REFERENCES prompts(id) ON DELETE SET NULL,
  prompt_key      TEXT,
  prompt_version  TEXT,
  prompt_language TEXT NOT NULL DEFAULT '',
  -- 호출 추적(옵션)
  provider        TEXT,
  model           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_gstyles_company_job
  ON generated_styles (company_code, job_code, created_at DESC);