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
    'tone_keywords', jsonb_build_array('트렌디','친화적','이모티콘'),
    'section_outline', jsonb_build_array('About Us','Team','What you will do','What we look for','Nice to have','Process'),
    'templates', jsonb_build_object(
      'About Us', '우리는 사용자에게 최고의 경험을 제공합니다!',
      'What you will do', '💻 이렇게 일해요\n🤝 이렇게 협업해요',
      'What we look for', '🧐 이런 분을 찾아요'
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


-- =========================================
-- 테이블: generated_jds (최종 JD 저장소)
-- =========================================
CREATE TABLE IF NOT EXISTS generated_jds (
  id            BIGSERIAL PRIMARY KEY,
  company_code  TEXT NOT NULL,
  job_code      TEXT NOT NULL,
  title         TEXT,
  jd_markdown   TEXT NOT NULL,
  sections      JSONB,
  meta          JSONB NOT NULL DEFAULT '{}'::jsonb, -- style_label, tone_keywords 등 요약
  provider      TEXT,                                -- openai / gemini ...
  model_name    TEXT,
  prompt_key    TEXT,                                -- 사용 프롬프트(denorm)
  prompt_version TEXT,
  prompt_language TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- FK: generated_jds.job_code -> job_code_map(job_code)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM pg_constraint c
      JOIN pg_class t ON t.oid = c.conrelid
     WHERE c.conname = 'fk_gjd_jobcode'
       AND t.relname = 'generated_jds'
  ) THEN
    ALTER TABLE generated_jds
      ADD CONSTRAINT fk_gjd_jobcode
      FOREIGN KEY (job_code) REFERENCES job_code_map(job_code)
      ON DELETE SET NULL;
  END IF;
END $$;

-- generated_jds : 스타일 선택 정보 보강
ALTER TABLE generated_jds
  ADD COLUMN IF NOT EXISTS style_source TEXT,              -- 'generated' | 'default' | 'override'
  ADD COLUMN IF NOT EXISTS style_preset_name TEXT,         -- default 프리셋명 (style_source='default'일 때)
  ADD COLUMN IF NOT EXISTS style_snapshot_id BIGINT        -- 생성 스냅샷 ID (style_source='generated'일 때)
    REFERENCES generated_styles(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_gjd_style_snapshot_id ON generated_jds (style_snapshot_id);
CREATE INDEX IF NOT EXISTS ix_gjd_company_job ON generated_jds (company_code, job_code, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_gjd_created ON generated_jds (created_at DESC);



BEGIN;
COPY raw_job_descriptions (
  id, source, company_code, job_code, job_id, url, title, jd_text,
  end_date, crawled_date, meta_json, created_at
)
FROM stdin;
1	jobkorea	잡코리아(유)	1000242	47480987	https://www.jobkorea.co.kr/Recruit/GI_Read/47480987?Oem_Code=C1	잡코리아 채용 - [잡코리아] Data Engineer (5년 이상) | 잡코리아	잡코리아는 대한민국 대표 HR Tech 플랫폼으로 모든 사업 모델 내 M/S 1위 달성을 목표로 혁신을 이뤄 내고 있습니다. AI 기반 고도화된 매칭을 통해 구직자와 구인 기업을 연결하고, Total 인재 채용 솔루션을 제공함으로써 데이터와 AI 기술을 결합해 글로벌 수준의 IT 기술력을 갖춘 Tech 플랫폼으로 도약하고 있습니다. 함께 변화를 이끌어 나갈 당신을 기다립\n니다.\n데이터신뢰성엔지니어링\n팀을 소개해요!\n데이터플랫폼팀은 잡코리아/알바몬에서 발생하는 데이터를 수집하고 가공하여, 비즈니스 데이터 및 LLM기반의 GenAI와 추천 애플리케이션 운영에 중심이 되는 데이터를 유관 부서에 안정적으로 제공하고 있습니다.\nAWS 및 On-Premise GPU를 활용해 데이터 수집 및 ML을 포함한 서비스 파이프라인에 개발 및 운영을 담당 합니다.\nGenAI 추론 서비스를 AWS 상에 개발 하고, 운영 하고 있습니다.\n이런 업무를 하시게 돼요!\n다양한 데이터 소스(RDBMS, GA4, 웹 로그 등)에서 발생하는 정형/비정형 데이터를 수집하고 ETL 처리 합니다.\nAWS 의 다양한 서비스를 활용하여 ETL 처리 및 Workflow 를 관리합니다.\n실시간 혹은 정기적 스케쥴에 따라 데이터를 제공, 운영합니다.\n지속적 모니터링을 통해 ETL 처리 로직을 최적화하여 효율성을 높이는 작업을 진행합니다.\n서비스에 필요한 형태로 데이터를 가공하여 Elastic Search, Vector DB, RDB 등에 제공합니다.\nML 훈련 및 분석을 위한 데이터 파이프 라인을 구축합니다.\n지속적 데이터 정합성을 확인하고 데이터의 거버넌스를 관리합니다.\n이런 기술을 활용하고 있어요!\nSpark, Airflow, Kafka 등을 활용하여 데이터 처리 및 워크플로우를 개발합니다.\nEMR on EKS를 기반의 환경에서 데이터를 처리 합니다.\nPython, JVM 계열 언어 및 SQL 을 활용해 데이터 서비스 파이프라인을 개발합니다.\nRAG 구축 및 운영을 위해 Elastic Search 및 VectorDB 등을 활용합니다.\n이런 경험을 가지신 분을 찾고 있어요!\nPython, SQL, Spark 등 데이터 처리 언어 및 도구 숙련자\n데이터 레이크하우스 설계 및 운영 경험을 보유하신 분\nAmazon EKS로 데이터 파이프라인 개발 및 운영 경험이 있으신 분\nEMR, Airflow, Spark 기반 파이프라인 개발/운영 지식을 보유하신 분\n데이터 거버넌스, 검증 및 품질 관리(Data Observability) 경험이 있으신 분\n이런 경험이 있다면 더욱 좋아요!\n대용량 데이터 처리 경험자 분\nAWS 상에 GenAI 서비스 구성 및 운영해 보신 분\nIT 도메인 및 플랫폼 기반의 회사에서 실무 경험이 있는 분 (B2C 위주)\n도메인 지식이 풍부하며, 비즈니스 및 타인의 성장과 개인의 성장을 일치화하는 것을 중요하게 생각하시는 분\n신규 기술에 대해 관심을 가지고 리서치 및 전파하는 것을 즐기는 분\n전형절차\n서류전형 > 1차면접 > 2차면접 > 처우협의 > 입사	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "잡코리아(유)", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47480987&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 6545, "detail_text_len": 1488, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47480987?Oem_Code=C1", "meta": {"D-": "Y", "경력": "Y", "서울": "Y"}, "title": "[잡코리아] Data Engineer (5년 이상)경력서울무관D-20데이터엔지니어,AI/ML엔지니어외1", "job_id": "47480987"}}	2025-08-24 19:09:27.923889+00
2	jobkorea	잡코리아(유)	1000242	47480955	https://www.jobkorea.co.kr/Recruit/GI_Read/47480955?Oem_Code=C1	잡코리아 채용 - [잡코리아] LLM Engineer (5년이상) | 잡코리아	잡코리아는 대한민국 대표 HR Tech 플랫폼으로 모든 사업 모델 내 M/S 1위 달성을 목표로 혁신을 이뤄 내고 있습니다. AI 기반 고도화된 매칭을 통해 구직자와 구인 기업을 연결하고, Total 인재 채용 솔루션을 제공함으로써 데이터와 AI 기술을 결합해 글로벌 수준의 IT 기술력을 갖춘 Tech 플랫폼으로 도약하고 있습니다. 함께 변화를 이끌어 나갈 당신을 기다립\n니다.\n데이터신뢰성엔지니어링팀\n을 소개해요!\n데이터신뢰성엔지니어링팀은 잡코리아/알바몬에서 발생하는 다양한 데이터를 수집·가공하여, 분석 데이터 및 LLM 기반의 GenAI와 추천 애플리케이션에 필요한 핵심 데이터를 안정적으로 제공합니다.\nAWS 클라우드 환경에서 데이터 수집 및 ML을 포함한 파이프라인과 GenAI 서비스 등 다양한 데이터 기반 서비스를 개발하고 운영합니다.\nGenAI 서비스는 AWS 클라우드에서 개발·운영하고 있습니다.\n이런 업무를 하시게 돼요!\n다양한 데이터 소스를 활용한 RAG 파이프라인을 개발·운영합니다.\nGenAI 및 Agent 서비스를 설계하고, 최적화를 진행합니다.\nGenAI 및 Agent에서 활용할 DB및 검색 엔진에 데이터를 제공하고 관리합니다.\nGenAI API 신규 기능 개발을 비롯한 다양한 추론 서비스를 개발합니다.\n빠르게 변화하고 발전하는 AI 관련 기술들을 조사하고 개발 합니다.\n이런 기술을 활용하고 있어요!\n다양한 LLM Foundation Model과 Python 계열의 프레임워크를 활용한 추론 API를 개발합니다.\n추론 가속화를 위한 AWS GPU Instance, Sagemaker, Bedrock등 AI 인프라 환경을 폭넓게 사용합니다.\nRetrieval, Prompt Engineering, Guardrails를 활용하여 GenAI 서비스의 추론 성능을 개선합니다.\nRAG 구축을 위한 Embedding VectorStore를 활용합니다.\nGenAI 안정및 효율을 위해 Queue 기반의 비동기/캐싱 구조를 활용합니다.\n협업을 위한 Git, Docker, CI/CD 등 개발·운영 도구도 적극적으로 사용합니다.\n이런 경험을 가지신 분을 찾고 있어요!\nPython 기반 데이터 처리 및 API 서비스 개발 8년 이상\nRAG 시스템 개발 및 운영 경험이 있으신 분\nLLM 기반의 GenAI API 개발 및 운영 경험이 있으신 분\nGenAI API 성능 최적화의 경험이 있으신 분\nGenAI  개선을 위해 등의 경험이 있으신 분\nVectorDB에 대한 개발 및 운영 경험이 있으신 분\n이런 경험이 있다면 더욱 좋아요!\n대량의 트래픽의 경험이 있으신 분\n실시간 스트리밍 및 빅데이터 환경의 경험을 보유하신 분\n머신러닝 및 데이터 엔지니어링 관련 지식을 보유하신 분\nIT 도메인 및 플랫폼 기반의 회사에서 실무 경험이 있으신 분(B2C 서비스 경험 우대)\n데이터와 비즈니스, 그리고 팀과 개인의 동반 성장을 중요하게 생각하시는 분\n새로운 기술에 대한 관심이 많고, 리서치 및 지식 전파를 즐기시는 분\n다양한 팀과의 협업 및 커뮤니케이션에 능숙하신 분\n전형절차\n서류전형 > 1차면접 > 2차면접 > 처우협의 > 입사	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "잡코리아(유)", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47480955&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 6617, "detail_text_len": 1535, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47480955?Oem_Code=C1", "meta": {"D-": "Y", "경력": "Y", "서울": "Y"}, "title": "[잡코리아] LLM Engineer (5년이상)경력서울무관D-20데이터엔지니어,AI/ML엔지니어외1", "job_id": "47480955"}}	2025-08-24 19:09:27.930431+00
3	jobkorea	잡코리아(유)	1000242	47480932	https://www.jobkorea.co.kr/Recruit/GI_Read/47480932?Oem_Code=C1	잡코리아 채용 - [잡코리아] ML Engineer (5년이상) | 잡코리아	잡코리아는 대한민국 대표 HR Tech 플랫폼으로 모든 사업 모델 내 M/S 1위 달성을 목표로 혁신을 이뤄 내고 있습니다. AI 기반 고도화된 매칭을 통해 구직자와 구인 기업을 연결하고, Total 인재 채용 솔루션을 제공함으로써 데이터와 AI 기술을 결합해 글로벌 수준의 IT 기술력을 갖춘 Tech 플랫폼으로 도약하고 있습니다. 함께 변화를 이끌어 나갈 당신을 기다립\n니다.\n추천스쿼드를\n소개해요!\n우리는 잡코리아/알바몬 사용자에게 맞춤형 컨텐츠를 제공하는 추천 시스템을 책임지고 있는 팀입니다. 정확도 높은 추천 모델을 만드는 것은 물론, 이를 실시간으로 빠르게 제공할 수 있는 인프라까지 함께 고민합니다. 실험과 개선을 즐기고, 제품과 사용자 경험을 함께 최적화해 나가는 팀이에요.\n이런 업무를 하시게 돼요!\n사용자 행동 데이터를 바탕으로 추천 알고리즘을 설계/개발해요\nONNX 기반 모델을 Triton 에서빙하고, Redis/Kafka 기반으로실시간 추천 파이프라인을 운영해요\nEmbedding 기반의 대용량 sparse 모델을 개발하고 최적화해요\n추천 품질 향상을 위한 A/B 테스트와 오프라인 평가 체계를 구축해요\n모델링부터 서빙까지 ML 파이프라인의 자동화와 운영을 개선해요\n이런 기술을 활용하고 있어요!\nPyTorch, TensorFlow, ONNX\nTriton Inference Server, Redis, Kafka\nFastAPI, gRPC\nAirflow, MLflow, Docker, GitHub Actions\n이런 경험을 가지신 분을 찾고 있어요!\n5년 이상의 ML 개발 경험 또는 그에 준하는 실전 능력을 갖추신 분\n추천 시스템 또는 개인화 모델 운영 경험이 있는 분\n실시간 또는 대용량 트래픽 환경에서 모델 서빙 인프라를 구축/운영해본 분\nSparse 데이터셋 기반 임베딩 모델링 경험이 있는 분\nPython을활용한 전처리/후처리 파이프라인 구현이 능숙한 분\nChatGPT, Copilot 등 최신 생성형 AI 도구를 탐색하고 활용한 경험이 있는 분\n이런 경험이 있다면 더욱 좋아요!\nLightGCN, BERT4Rec, DSSM 등 최신 추천 모델에 익숙하신 분\nTriton + Redis + Kafka 조합의 실시간 아키텍처 설계 경험이 있는 분\n모델 서빙 최적화 (e.g. batching, quantization)에 관심이 있으신 분\nAB 테스트 설계 및 추천 KPI 분석 경험이 있는 분\n팀과의 협업을 중시하고 문제 해결을 즐기시는 분\nAI 도구를 활용해 데이터 분석 및 시각화를 수행한 경험이 있는 분\n전형절차\n서류전형 > 1차면접 > 2차면접 > 처우협의 > 입사	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "잡코리아(유)", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47480932&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 6325, "detail_text_len": 1288, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47480932?Oem_Code=C1", "meta": {"D-": "Y", "경력": "Y", "서울": "Y"}, "title": "[잡코리아] ML Engineer (5년이상)경력서울무관D-20AI/ML엔지니어", "job_id": "47480932"}}	2025-08-24 19:09:27.934277+00
4	jobkorea	잡코리아(유)	1000201	47488532	https://www.jobkorea.co.kr/Recruit/GI_Read/47488532?Oem_Code=C1&PageGbn=ST	잡코리아 채용 - [잡코리아] 인사기획 | 잡코리아	잡코리아는 대한민국 대표 HR Tech 플랫폼으로 모든 사업 모델 내 M/S 1위 달성을 목표로 혁신을 이뤄 내고 있습니다. AI 기반 고도화된 매칭을 통해 구직자와 구인 기업을 연결하고, Total 인재 채용 솔루션을 제공함으로써 데이터와 AI 기술을 결합해 글로벌 수준의 IT 기술력을 갖춘 Tech 플랫폼으로 도약하고 있습니다. 함께 변화를 이끌어 나갈 당신을 기다립\n니다.\n인재\n팀을 소개해요!\n잡코리아 인재팀은 ‘사람’을 중심으로 조직의 성장을 설계하고 실행하는 HR 전문가 조직이에요.\n우리는 채용부터 인사제도 기획, 인력운영, HRBP까지 전반적인 인사 운영을 담당하며, 조직의 목표와 구성원의 성장을 함께 이끌 수 있는 인사 전략을 고민합니다.\n데이터 기반의 인사 판단과 유연한 조직 대응력으로, 실질적인 비즈니스 임팩트를 만드는 팀입니다.\n이런 업무를 하시게 돼요!\n실행력 강화를 위한 인사전략 수립 및 실행\n조직개편, 조직구조 설계 및 변화관리\n인원 계획 수립 및 인력 운영 관리\n평가, 보상, 승진 등 인사제도 기획 및 운영\nHR 데이터 기반 의사결정 및 인사이트 도출\n이런 경험을 가지신 분을 찾고 있어요!\nHR 이슈를 정의하고 주도적으로 해결해본 경험이 있으신 분\nHR Generalist로서 HRM영역에 경험이 있으신 분\n조직 설계와 평가, 보상 정책에 대한 기획 경험이 있으신 분\n인력계획 수립, 인력관리 경험이 있으신 분\n여러 유관부서와 협업하며 유연하게 커뮤니케이션 할 수 있는 분\n적극적인 태도를 갖추신 분\n이런 경험이 있다면 더욱 좋아요!\n비즈니스와 연계를 고려한 인사전략 수립 경험이 있으신 분\n다양한 HRIS로 평가 실무를 운영해 보신 분\n급변하는 조직 내에서 제도 정비 및 문화 개선을 주도한 경험이 있으신 분\n인사 전략 수립 또는 제도 기획 시 AI 기반 분석이나 자동화 도구를 활용한 경험이 있으신 분\n전형절차\n서류전형 > 1차면접 > 2차면접 > 처우협의 > 입사	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "잡코리아(유)", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47488532&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 5291, "detail_text_len": 956, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47488532?Oem_Code=C1&PageGbn=ST", "meta": {"D-": "Y", "경력": "Y", "서울": "Y", "신입": "Y"}, "title": "[잡코리아] 인사기획신입·경력서울무관D-6인사담당자", "job_id": "47488532"}}	2025-08-24 19:13:43.422287+00
5	jobkorea	잡코리아(유)	1000187	47503224	https://www.jobkorea.co.kr/Recruit/GI_Read/47503224?Oem_Code=C1	잡코리아 채용 - [잡코리아] 콘텐츠 PM (3년이상) | 잡코리아	잡코리아는 대한민국 대표 HR Tech 플랫폼으로 모든 사업 모델 내 M/S 1위 달성을 목표로 혁신을 이뤄 내고 있습니다. AI 기반 고도화된 매칭을 통해 구직자와 구인 기업을 연결하고, Total 인재 채용 솔루션을 제공함으로써 데이터와 AI 기술을 결합해 글로벌 수준의 IT 기술력을 갖춘 Tech 플랫폼으로 도약하고 있습니다. 함께 변화를 이끌어 나갈 당신을 기다립\n니다.\n인사이트전략팀\n을 소개해요!\n데이터를 기반으로 인재들의 커리어 여정을 깊이 이해하고 맞춤형 콘텐츠를 제공합니다.\n밋업/웨비나, 커뮤니티 등의 콘텐츠를 기획/운영하면서 핵심 인재 풀을 만들어갑니다.\n채용 플랫폼을 넘어 커리어 플랫폼으로 나아가는 콘텐츠 허브를 만들어갑니다.\n이런 업무를 하시게 돼요!\n웨비나/밋업 기획 & 운영\n직무·커리어·이직 관련 웨비나·밋업 시리즈 기획 및 연간 운영\n연사 섭외, 주제 발굴, 참가자 모집 및 행사 진행\n커뮤니티 운영\n온라인/오프라인 커뮤니티 활성화 전략 수립\n참여 유도 콘텐츠(토론, Q&A, 인터뷰 등) 제작\n브랜드 확장\n잡코리아 커리어 성장 브랜드 포지셔닝 강화\n외부 파트너십 발굴 및 협업\n이런 경험을 가지신 분을 찾고 있어요!\n기획력 & 실행력 : 주제를 발굴하고, 커리어 콘텐츠를 A부터 Z까지 리딩할 수 있으신 분\n콘텐츠 감각 : 직장인들의 관심사를 잘 이해하고 콘텐츠로 풀어낼 수 있으신 분\n관계 구축 능력 : 연사·참가자·파트너와 원활하게 커뮤니케이션이 가능하신 분\n데이터 활용 : 성과 지표를 설정하고 분석해 개선안을 도출할 수 있으신 분\n이런 분이라면 더욱 좋아요!\nB2B/B2C 콘텐츠, 커뮤니티 운영 경험이 있으신 분\n웨비나·밋업·컨퍼런스 기획 및 진행 경험이 있으신 분\n커리어, 직무, HR 분야에 대한 이해도가 높으신 분\n외부 네트워크(전문가, 연사 등)를 보유하신 분\nA/B 테스트 또는 다양한 실험 기반의 의사결정 경험이 있으신 분\nJira, Confluence, Notion, Figma 등 협업 도구 사용에 능숙하신 분\n생성형 AI, 워크플로우 자동화 등 AI 기반 협업 도구 활용이 가능하신 분\n전형절차\n서류전형 > 1차면접 > 2차면접 > 처우협의 > 입사	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "잡코리아(유)", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47503224&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 5591, "detail_text_len": 1069, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47503224?Oem_Code=C1", "meta": {"D-": "Y", "경력": "Y", "서울": "Y"}, "title": "[잡코리아] 콘텐츠 PM (3년이상)경력서울무관D-20마케팅기획,PL·PM·PO", "job_id": "47503224"}}	2025-08-24 19:14:01.169009+00
6	jobkorea	현대오토에버㈜	1000187	47445654	https://www.jobkorea.co.kr/Recruit/GI_Read/47445654?Oem_Code=C1	현대오토에버 채용 - 전사 브랜드/디지털 마케팅 전략 수립 및 실행 | 잡코리아	현대오토에버㈜\n[DX센터집중채용] UX/UI - 기획자/디자이너/리서처\n고객을 선도하는 역량을 보유한 글로벌 IT서비스 전문기업 현대오토에버(주)는 현대자동차 그룹의 \r\nIT서비스를 지원해온 전문성과 경험을 토대로 자동차·부품·철강·금융·물류·건설 등의 다양한 \r\n산업영역에서 최고의 IT서비스를 제공하여 고객의 가치창출을 효율적으로 지원하였고, 나아가 IT 산업의 \r\n경쟁력 제고와 선진화에 기여하였습니다.\r\n현대오토에버(주)는 현대자동차 그룹사의 검증 받은 레퍼런스를 기반으로 고객의 특성과 환경에 \r\n가장 이상적인 솔루션을 제공하며, 고객 비즈니스에 대한 이해와 기술력 및 품질을 바탕으로 고객 \r\n경쟁력의 핵심역할을 수행하고 있습니다.\r\n글로벌 시대, 고객 성공의 무한한 가능성을 실현하는 현대오토에버(주)의 기술은 오늘 그리고 \r\n내일의 성공을 이끌어 갑니다.\n디지털커뮤니케이션팀\n은 AutoEver가 가진\n브랜드,\n서비스/제품,\n기술, 문화, 그리고\n사람의 가치를\n대내외에\n알려 더\n가치 있게\n만들어요.\n우리는 회사가 가진 브랜드와 상품, 기술력, 사람과 문화에 이르는 유무형의 자산을 혁신적이고 효과적인 디지털 플랫폼을 통해 대내외에 알려 그 가치를 더 높이는 일을 해요. 이를 위해 우리는 전사 마케팅 커뮤니케이션 및 브랜드의 전략/아키텍처를 수립하고 실행하며 일관된 메시지를 전달해요. 데이터 기반으로 고객의 기대를 분석하고, CRM 전략을 통해 세그먼트와 채널별로 맞춤형 콘텐츠를 개발해요. 주요 마케팅 행사인 세미나와 컨퍼런스도 계획하여 고객과의 연결을 강화해요. AutoEver와 함께 하는 모든 순간이 더 특별한 경험이 될 수 있도록 최선을 다하고 있어요!\n포지션 및 자격요건\n전사 브랜드/디지털 마케팅 전략 수립 및 실행\n( ○명 )\n담당업무\n현대오토에버가 지향하는 브랜딩 방향성에 맞추어 대내외 고객을 대상으로 우리가 가진 서비스/제품, 솔루션 그리고 기술력과 문화를 효과적이고 일관되게 전달하는 일을 합니다. 이를 위해 전사 사업 영역이 보유한 유무형의 자산을 고객의 관점에서 바라보고, 고객의 니즈와 기대에 부흥할 수 있는 커뮤니케이션 전략을 수립하기 위해 마케팅 거버넌스를 체계화하고, 채널 별 역할을 정의하여 콘텐츠를 기획하고 운영합니다. 온라인 뿐만 아니라, 오프라인에서의 주요 마케팅 행사를 통해서도 일관된 메시지를 전달하여 현대오토에버의 브랜드를 고객에게 명확하게 전달하여 우리의 가치를 경험할 수 있도록 하고자 합니다\n[주요 업무]\n마케팅 관점에서의 통합 커뮤니케이션 전략 수립\n통합디지털 마케팅 전략 구축 및 실행\n마케팅 거버넌스 수립 및 커뮤니케이션 가이드 개발\n홈페이지 개편 및 운영\n브랜드 채널(소셜 미디어 등) 운영 및 채널 별 R&R 정립\n콘텐츠 기획/제작 및 콘텐츠 허브 구축\n전시/컨퍼런스 등 전사 오프라인 행사 기획 및 운영\n브랜드 자산의 마케팅 커뮤니케이션 운영 및 모니터링\n브랜드 관련 자산(CI, 슬로건, 콘텐츠 등)의 운영 거버넌스 수립\n콘텐츠 가이드 수립 및 운영 모니터링\n브랜드 평가에 관련된 정성/정량적 지표 운영\n이런 분과 함께 하고 싶어요\n전사 마케팅 전략 및 마케팅 커뮤니케이션 운영 등 유관 분야 5년 이상 경력\n온/오프라인 마케팅 전략, 운영, 브랜드 전략 수립 프로젝트 경력\n전사 마케팅 전략 수립 및 운영 경력\n디지털 마케팅 채널 운영 및 콘텐츠 기획 경험\n퍼널 별 고객 데이터 분석 및 고객 여정에 대한 분석 경험\n원활한 커뮤니케이션 및 이해관계자 협업 능력\n문제 해결력 및 분석적 사고력\n이런 분이라면 더욱 좋아요\nIT/B2B 업종 근무 경험\n인하우스 마케팅 업무 및 종합광고대행사 재직 경력\n퍼포먼스 마케팅 및 매체 운영 경력\n마케팅 자동화 툴 활용 경험\n비즈니스 영어 가능자\n만나게 될 근무지는 여기예요\n서울 강남\n전형절차\n서류 접수 → 서류 검토 → 직무역량테스트(과제테스트) 및 인성검사 → 1차면접 → 2차면접\n→ 처우협의 및 채용검진 → 최종 합격\n유의사항\n채용 시 마감되는 상시 채용 공고로 운영되며, 채용 절차와 일정은 변동될 수 있어요.\n사회적 배려 대상자(보훈 취업지원대상자, 장애인)는 관계 법령과 내규에 따라 우대해요.\n모집 분야 및 담당 업무에 따라 영어 구술평가, 레퍼런스 체크, 또는 기타 전형이 실시될 수 있어요.\n지원자의 경험과 역량을 고려하여 다른 포지션이 더 적합하다고 판단되는 경우 지원 분야가 변경될 수 있어요.\n배치 부서 및 근무지는 회사 사정에 따라 변경될 수 있어요.\n아래의 경우, 합격이 취소되거나 전형 진행에서 불이익을 받으실 수 있어요.\r\n- 지원서가 사실과 다르거나 증빙이 불가할 경우\r\n- 해외여행 결격 사유가 있는 경우 (남성의 경우, 회사가 지정한 입사일까지 병역 필 또는 면제 필요)\r\n- 최종 합격 후 회사가 지정하는 입사일에 입사 불가한 경우\r\n- 포트폴리오 첨부를 원하시는 경우 이력서 또는 자기소개서란을 이용해서 첨부하실 수 있어요.	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "현대오토에버㈜", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47445654&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 40366, "detail_text_len": 2398, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47445654?Oem_Code=C1", "meta": {"D-": "Y", "경력": "Y", "서울": "Y"}, "title": "전사 브랜드/디지털 마케팅 전략 수립 및 실행경력서울무관D-2마케팅기획", "job_id": "47445654"}}	2025-08-24 19:12:45.105049+00
7	jobkorea	현대오토에버㈜	1000187	47442634	https://www.jobkorea.co.kr/Recruit/GI_Read/47442634?Oem_Code=C1	현대오토에버 채용 - 스마트오피스 SW플랫폼 사업 기획 및 영업 | 잡코리아	모집 분야 상세\n모집 분야 상세 정보\n모집분야\n담당업무\n지원요건\n필요\n경력\n근무지\n스마트오피스\nSW플랫폼\n사업 기획 및 영업\n[스마트라이프추진팀]\n스마트오피스 및 스마트빌딩 시장/기술동향 분석,\n사업기획, 영업\n상품/서비스 고객가치 제안 및 마케팅 전략 수립, 전개\n상품/서비스 별 VoC 수집 및 분석을 통한 서비스\n고도화 기획 및 사업지속성 유지\nMinimum qualifications\n스마트오피스 SW플랫폼 상품 및\n서비스 기획 경험\n수주, 계약, 정산 업무 전반에 대한 사업관리 경험\nPreferred qualifications\n영문 비즈니스 커뮤니케이션 및 문서\n작성 역량\n사업제안 및 프리젠테이션 역량\n3년 이상\n서울\n공통자격요건\n해외여행 및 근무에 결격사유가 없는 분(남자의 경우 병역을 마쳤거나 면제받은 분)\n최종합격 후 회사가 지정하는 입사일에 입사 가능하신 분\n모집기간\n채용 시 마감\n전형절차\n지원서 접수/\n서류전형\n직무역량테스트/인성검사\n1차면접/2차면접\n처우협의/\n채용검진\n최종합격\n* 직무역량테스트(코딩 또는 과제테스트)\n기타사항\n지원서의 내용이 사실과 다르거나 문서로 증빙이 불가할 경우 합격이 취소되거나 전형상의 불이익을 받을 수 있습니다.\n해외여행에 결격 사유가 있는 분(남성의 경우, 회사가 지정한 입사일까지 병역 미필 또는 병역 면제되지 않은 분 포함)은 합격이\n취소되거나 전형상 불이익을 받을 수 있습니다.\n최종합격 후 회사가 지정하는 입사일에 입사 불가할 경우 경우 합격이 취소되거나 전형상의 불이익을 받을 수 있습니다.\n장애인 및 국가 보훈 취업지원 대상자는 관계 법령에 의거하여 우대합니다.\n전형 단계별 합격자 발표는 개별 연락 예정입니다.\n채용 절차 및 일정은 일부 변동될 수 있습니다.\n모집 분야 및 담당 업무에 따라 영어 구술평가, 레퍼런스 체크, 또는 기타 전형이 실시될 수 있습니다.\n지원자의 경험과 역량을 고려하여 다른 포지션이 더 적합하다고 판단되는 경우 지원 분야가 변경될 수 있습니다.\n홈페이지 입사 지원하기	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "현대오토에버㈜", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47442634&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 6620, "detail_text_len": 988, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47442634?Oem_Code=C1", "meta": {"D-": "Y", "경력": "Y", "서울": "Y"}, "title": "스마트오피스 SW플랫폼 사업 기획 및 영업경력서울무관D-2경영·비즈니스기획,웹기획외1", "job_id": "47442634"}}	2025-08-24 19:12:45.112068+00
8	jobkorea	현대오토에버㈜	1000187	47445655	https://www.jobkorea.co.kr/Recruit/GI_Read/47445655?Oem_Code=C1	현대오토에버 채용 - [DX] 브랜드 전략 담당 - 디자인 씽킹 이노베이션 스튜디오 (전문계약직) | 잡코리아	현대오토에버㈜\n[DX센터집중채용] UX/UI - 기획자/디자이너/리서처\n고객을 선도하는 역량을 보유한 글로벌 IT서비스 전문기업 현대오토에버(주)는 현대자동차 그룹의 \r\nIT서비스를 지원해온 전문성과 경험을 토대로 자동차·부품·철강·금융·물류·건설 등의 다양한 \r\n산업영역에서 최고의 IT서비스를 제공하여 고객의 가치창출을 효율적으로 지원하였고, 나아가 IT 산업의 \r\n경쟁력 제고와 선진화에 기여하였습니다.\r\n현대오토에버(주)는 현대자동차 그룹사의 검증 받은 레퍼런스를 기반으로 고객의 특성과 환경에 \r\n가장 이상적인 솔루션을 제공하며, 고객 비즈니스에 대한 이해와 기술력 및 품질을 바탕으로 고객 \r\n경쟁력의 핵심역할을 수행하고 있습니다.\r\n글로벌 시대, 고객 성공의 무한한 가능성을 실현하는 현대오토에버(주)의 기술은 오늘 그리고 \r\n내일의 성공을 이끌어 갑니다.\n합류하실 조직을 소개해요\n(신설)DX\n(Digital eXperience)센터\n는\n디지털 경험 전략을 수립하고 실행을 총괄하기 위해 올해 신설된 조직이에요. 참고로 DX는 ▲CX(Customer eXperience) ▲ UX(User eXperience) ▲ PX(Partner eXperience) ▲ EX(Employee eXperience)를 아우르는 개념입니다. DX센터는 고객, 파트너, 임직원 등 다양한 이해관계자에게 제공하는 상품과 서비스에서 일관성 있고 우수한 품질의 디지털 경험을 제공할 나갈 계획입니다. 이를 통해 `고객만족`을 실현하고 당사 `서비스의 차별성`을 확보하는 것을 목표로 하고 있습니다.\n(신설) InnoX Studio 는\n디자인 씽킹 기반의 이노베이션 조직으로 크로스 기능 팀과 협력하며 고객/현업 참여 기반의 혁신 활동 수행을 통해 고객의 고민/문제를 해결할 수 있는 아이디어를 도출하고 혁신적인 솔루션을 제안하는 역할을 합니다. 또한 자체 리소스 및 DX센터 내외의 팀들과 협업하여 단순한 보고서 수준이 아닌 실제적인 개선방안을 보여줍니다.\n포지션 및 자격요건\n서비스 전략 컨설턴트\n( ○명 )\n담당업무\n직무 목적 : 기업의 정체성과 시장 경쟁력을 강화하기 위해 브랜드 전략의 수립 및 실행을 담당합니다. 브랜드 아이덴티티 확립, 브랜드 아키텍처 관리, 산사업 브랜드 운영 관리하며, 다양한 조직과의 협업을 통해 브랜드 가치가 일관되고 효과적으로 운영되도록 실무를 주도합니다.\n* 브랜드 전략 수립 및 실행\r\n   - 기업 및 제품/서비스(B2B) 브랜드 전략 기획 및 실행\r\n   - 브랜드 포지셔닝 개발 및 리뉴얼 프로젝트 운영\r\n   - 브랜드 리서치 및 경쟁사 분석을 통한 인사이트 도출\r\n\r\n* 브랜드 아이덴티티 관리\r\n   - CI/BI 운영 및 가이드라인 유지보수\n- 브랜드 톤앤매너 및 표현 원칙 수립 및 적용 관리\n- 내/외부 브랜드 표현물 모니터링 및 품질관리\r\n\r\n* 브랜드 아키텍처 기획\r\n   - 제품/서비스 포트폴리오 기반 브랜드 구조 설계\r\n   - 신규 브랜드 네이밍 청책 및 운영 체계 구축\n이런 분과 함께 하고 싶어요\n*\n브랜드 전략, 마케팅, 커뮤니케이션 등 유관 분야 10년 이상 경력\n* 브랜드 컨설팅사 혹은 인하우스 브랜드전략/마케팅 경험자 우대\n* 브랜드 아키텍처 및 아이덴티티 시스템에 대한 높은 이해\n* 기획안, 전략안 제작 능력\n* 커뮤니케이션 및 협업 능력 우수자\n* 데이터 기반 인사이트 도출 능력\n이런 분이라면 더욱 좋아요\n* 브랜드 리뉴얼/CI 프로젝트 수행 경험\n*\n디자인 에이전시 및 광고 대행사 협업 경험\n* 비즈니스 영어 가능자\n만나게 될 근무지는 여기예요\n서울 강남\n전형절차\n서류 접수 → 서류 검토 → 직무역량테스트(과제테스트) 및 인성검사 → 1차면접 → 2차면접\n→ 처우협의 및 채용검진 → 최종 합격\n유의사항\n채용 시 마감되는 상시 채용 공고로 운영되며, 채용 절차와 일정은 변동될 수 있어요.\n사회적 배려 대상자(보훈 취업지원대상자, 장애인)는 관계 법령과 내규에 따라 우대해요.\n모집 분야 및 담당 업무에 따라 영어 구술평가, 레퍼런스 체크, 또는 기타 전형이 실시될 수 있어요.\n지원자의 경험과 역량을 고려하여 다른 포지션이 더 적합하다고 판단되는 경우 지원 분야가 변경될 수 있어요.\n배치 부서 및 근무지는 회사 사정에 따라 변경될 수 있어요.\n아래의 경우, 합격이 취소되거나 전형 진행에서 불이익을 받으실 수 있어요.\r\n- 지원서가 사실과 다르거나 증빙이 불가할 경우\r\n- 해외여행 결격 사유가 있는 경우 (남성의 경우, 회사가 지정한 입사일까지 병역 필 또는 면제 필요)\r\n- 최종 합격 후 회사가 지정하는 입사일에 입사 불가한 경우\r\n- 포트폴리오 첨부를 원하시는 경우 이력서 또는 자기소개서란을 이용해서 첨부하실 수 있어요.	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "현대오토에버㈜", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47445655&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 34378, "detail_text_len": 2304, "employment_type": "계약직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47445655?Oem_Code=C1", "meta": {"경력": "Y", "서울": "Y"}, "title": "[DX] 브랜드 전략 담당 - 디자인 씽킹 이노베이션 스튜디오 (전문계...경력서울무관마감 (~2025.08.21)마케팅기획,AE(광고기획자)외1", "job_id": "47445655"}}	2025-08-24 19:12:45.115716+00
9	jobkorea	한화오션(주)	1000201	47444416	https://www.jobkorea.co.kr/Recruit/GI_Read/47444416?Oem_Code=C1	한화오션 채용 - [해양사업부] GHR 경력사원 채용 - HRM(인사관리) | 잡코리아	한화오션(주)\n[해양사업부] GHR 경력사원 채용\n- HRM(인사관리)\n포지션 및 자격요건\nHRM\n(인사관리)\n주요업무\nㆍ\n사업부 內 글로벌 거점 맞춤형 HR 제도·정책 개선 및 운영\n- 사업부 인력 계획 수립 및 실행\n- 사업부 글로벌 거점 연계 목표설정 및 성과/평가관리 제도 운영\n- 사업부 보상 체계 및 적용 관련 운영·검토\nㆍ\n인사 데이터 및 HR시스템 관리\n- HRIS 운영, 인사 통계 및 데이터 관리, 경영진 보고 자료 작성 등\nㆍ\n사업부 內 글로벌 거점 별 HR 담당자 협업 및 인력운영 관리 등\n자격요건 및 우대사항\nㆍ대학교 학사 이상의 학위를 보유하신 분(필수)\n- 경영학/조선해양공학 등 관련 전공 (우대)\nㆍ\n우수한 비즈니스 영어 활용 역량을 보유하신 분 (필수)\nㆍ\n원활한 OA활용, 문서작성, 커뮤니케이션 역량 및 문제 해결 능력을 보유하신 분 (필수)\nㆍ\n다이렉트 소싱을 통한 채용 경험을 보유하신 분 (필수)\nㆍ\n별도 채용 플랫폼(링크드인, 리멤버 등) 활용 경험을 보유하신 분 (우대)\nㆍ\nGHR 또는 글로벌 네트워크를 활용한 HR 업무 경험을 보유하신 분 (우대)\nㆍ\n제조업, 조선/해양플랜트, 글로벌 기업에서의 경험을 보유하신 분 (우대)\n공통지원자격\nㆍ지원 포지션의 5년 이상의 유관 직무 경력을 보유하신 분\nㆍ\n해외여행에 결격사유가 없는 분 (남성의 경우, 군필 또는 면제)\n* 국가보훈대상자(취업보호대상자 증명서 제출) 및 장애인은 관련 법규에 의거하여 우대합니다.\n기타사항\nㆍ접수기간 :\n2025. 07. 31 - 2025. 08. 24  15:00\nㆍ접수방법 :\n당사 채용 홈페이지 지원\nㆍ자세한 상세요강은 반드시 채용 홈페이지에서 직접 확인해 주시기 바랍니다.\n기업 채용 홈페이지 바로가기 click	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "한화오션(주)", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47444416&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 4105, "detail_text_len": 865, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47444416?Oem_Code=C1", "meta": {"경력": "Y", "서울": "Y"}, "title": "[해양사업부] GHR 경력사원 채용 - HRM(인사관리)경력서울마감 (~2025.08.24)인사담당자,HRD·HRM", "job_id": "47444416"}}	2025-08-24 18:59:41.553671+00
10	jobkorea	한화오션(주)	1000201	47444351	https://www.jobkorea.co.kr/Recruit/GI_Read/47444351?Oem_Code=C1	한화오션 채용 - [해양사업부] GHR 경력사원 채용 | 잡코리아	한화오션(주)\n[해양사업부] GHR 경력사원 채용\n포지션 및 자격요건\nTalent Acquisition\n(인재채용)\n주요업무\nㆍ\n외부 우수인재 채용\n- 다양한 유형(정규직/계약직/외국인 등)의 우수 경력사원 확보 및 영입 실행\n- 전체 채용 프로세스 관리 (후보자 발굴 ~ 처우협의 및 입사)\nㆍ\n사업부 채용 계획 수립 및 채용 전략 기획/실행\n- 한화오션 해양사업부 비즈니스 환경 및 전략, 비전에 기반한 채용 전략 수립\n- 국내/외 우수 인재 확보를 위한 차별화된 채용 전략 기획 및 실행\nㆍ\n채용 데이터 관리 및 분석을 통한 인사이트 도출, 프로세스 개선 등\nHRM\n(인사관리)\n주요업무\nㆍ\n사업부 內 글로벌 거점 맞춤형 HR 제도·정책 개선 및 운영\n- 사업부 인력 계획 수립 및 실행\n- 사업부 글로벌 거점 연계 목표설정 및 성과/평가관리 제도 운영\n- 사업부 보상 체계 및 적용 관련 운영·검토\nㆍ\n인사 데이터 및 HR시스템 관리\n- HRIS 운영, 인사 통계 및 데이터 관리, 경영진 보고 자료 작성 등\nㆍ\n사업부 內 글로벌 거점 별 HR 담당자 협업 및 인력운영 관리 등\n자격요건 및 우대사항\nㆍ대학교 학사 이상의 학위를 보유하신 분(필수)\n- 경영학/조선해양공학 등 관련 전공 (우대)\nㆍ\n우수한 비즈니스 영어 활용 역량을 보유하신 분 (필수)\nㆍ\n원활한 OA활용, 문서작성, 커뮤니케이션 역량 및 문제 해결 능력을 보유하신 분 (필수)\nㆍ\n다이렉트 소싱을 통한 채용 경험을 보유하신 분 (필수)\nㆍ\n별도 채용 플랫폼(링크드인, 리멤버 등) 활용 경험을 보유하신 분 (우대)\nㆍ\nGHR 또는 글로벌 네트워크를 활용한 HR 업무 경험을 보유하신 분 (우대)\nㆍ\n제조업, 조선/해양플랜트, 글로벌 기업에서의 경험을 보유하신 분 (우대)\n공통지원자격\nㆍ지원 포지션의 5년 이상의 유관 직무 경력을 보유하신 분\nㆍ\n해외여행에 결격사유가 없는 분 (남성의 경우, 군필 또는 면제)\n* 국가보훈대상자(취업보호대상자 증명서 제출) 및 장애인은 관련 법규에 의거하여 우대합니다.\n기타사항\nㆍ접수기간 :\n2025. 07. 31 - 2025. 08. 24  15:00\nㆍ접수방법 :\n당사 채용 홈페이지 지원\nㆍ자세한 상세요강은 반드시 채용 홈페이지에서 직접 확인해 주시기 바랍니다.\n기업 채용 홈페이지 바로가기 click	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "한화오션(주)", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47444351&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 4753, "detail_text_len": 1130, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47444351?Oem_Code=C1", "meta": {"경력": "Y", "서울": "Y"}, "title": "[해양사업부] GHR 경력사원 채용경력서울마감 (~2025.08.24)인사담당자,HRD·HRM", "job_id": "47444351"}}	2025-08-24 18:59:41.565567+00
11	jobkorea	한화오션(주)	1000242	47466716	https://www.jobkorea.co.kr/Recruit/GI_Read/47466716?Oem_Code=C1	한화오션 채용 - [IT 대규모 채용] 시스템 개발/운영 경력사원 채용 (설계시스템 개발 및 운영) | 잡코리아	한화오션(주)\n[IT 대규모 채용] 시스템 개발/운영\n경력사원 채용 (설계시스템 개발 및 운영)\n포지션 및 자격요건\n설계시스템 개발 및 운영\n주요업무\nㆍ차세대 조선소 설계환경 구축을 위한 CAD/PLM 시스템 개발\n- DT 추진 및 엔지니어링 분야 AI 기술 적용\n-\n검색 증강 생성(RAG), 디지털 트윈 등 신기술 활용한 스마트 야드 시스템 구축\nㆍ\n설계-구매-생산 업무를 통합하는 정보시스템 구축\nㆍ\n선박 의장설계 자동화 시스템 개발/운영\nㆍ\nBOM, 자재관리 등 조달/구매 시스템 개발/운영\n자격요건\nㆍC/C#, Python, SQL 및 Web 프로그래밍 언어 활용 역량을 보유하신 분\nㆍ\nunity 기반 디지털 트윈 개발 역량을 보유하신 분\nㆍ\n딥러닝 개발 프레임워크 활용 역량을 보유하신 분\nㆍ\n디지털 제조 및 자동화 시스템에 대한 이해도를 보유하신 분\n우대사항\nㆍ설계시스템 (CAD) 자동화 및 PLM 개발 경험을 보유하신 분\nㆍ\nAI, 빅데이터 관련 자격증을 보유하신 분\n※ 부산 근무 포지션의 경우, 일정기간 거제 온보딩 후 부산 근무 예정입니다.\n공통지원자격\nㆍ학사 이상의 학위를 보유하신 분 (컴퓨터공학, 전산학, 통계학, 산업공학, 조선공학 등 관련 전공자 우대)\nㆍ\n지원 포지션의 5년 이상의 유관 직무 경력을 보유하신 분\nㆍ\n해외여행에 결격사유가 없는 분 (남성의 경우, 군필 또는 면제)\n* 국가보훈대상자(취업보호대상자 증명서 제출) 및 장애인은 관련 법규에 의거하여 우대합니다.\n기타사항\nㆍ\n접수기간 :\n2025. 07. 30 ~ 2025. 08. 24  15:00\nㆍ접수방법 :\n당사 채용 홈페이지 지원\nㆍ자세한 상세요강은 반드시 채용 홈페이지에서 직접 확인해 주시기 바랍니다.\n기업 채용 홈페이지 바로가기 click	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "한화오션(주)", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47466716&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 4311, "detail_text_len": 866, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47466716?Oem_Code=C1", "meta": {"경력": "Y", "부산": "Y", "서울": "Y"}, "title": "[IT 대규모 채용] 시스템 개발/운영 경력사원 채용 (설계시스템 개발...경력서울·경남·부산대졸↑마감 (~2025.08.24)시스템엔지니어,데이터엔지니어외1", "job_id": "47466716"}}	2025-08-24 19:00:25.967619+00
12	jobkorea	한화오션(주)	1000242	47466643	https://www.jobkorea.co.kr/Recruit/GI_Read/47466643?Oem_Code=C1	한화오션 채용 - [IT 대규모 채용] 시스템 개발/운영 경력사원 채용 | 잡코리아	한화오션(주)\n[IT 대규모 채용] 시스템 개발/운영\n경력사원 채용\n포지션 및 자격요건\n생산시스템 개발 및 운영\n주요업무\nㆍ생산스마트 시스템 설계 및 개발/운영 (DT, 스마트팩토리 등)\nㆍ\n생산지원 및 품질관리 시스템 개발/운영 (설비, 품질, SAP-QM/PM 등)\nㆍ\nIoT플랫폼 유관 시스템 개발/운영\n자격요건\nㆍ웹프로그램 개발 실무 경력을 보유하신 분\nㆍ\nSQL 개발 역량을 보유하신 분\nㆍ\n시계열 데이터베이스(TSDB) 활용 경험을 보유하신 분\nㆍ\nkubernetes 클러스터 구축 및 운영 경험을 보유하신 분\nㆍ\nERP(SAP PS/PP)/MES 관련 업무 경험을 보유하신 분\n우대사항\nㆍThingWorx 플랫폼 개발 경험을 보유하신 분\nㆍ\nC# 또는 ABAP 언어 활용 역량을 보유하신 분\nㆍ\n비즈니스 영어 활용 역량을 보유하신 분\n설계시스템 개발 및 운영\n주요업무\nㆍ차세대 조선소 설계환경 구축을 위한 CAD/PLM 시스템 개발\n- DT 추진 및 엔지니어링 분야 AI 기술 적용\n-\n검색 증강 생성(RAG), 디지털 트윈 등 신기술 활용한 스마트 야드 시스템 구축\nㆍ\n설계-구매-생산 업무를 통합하는 정보시스템 구축\nㆍ\n선박 의장설계 자동화 시스템 개발/운영\nㆍ\nBOM, 자재관리 등 조달/구매 시스템 개발/운영\n자격요건\nㆍC/C#, Python, SQL 및 Web 프로그래밍 언어 활용 역량을 보유하신 분\nㆍ\nunity 기반 디지털 트윈 개발 역량을 보유하신 분\nㆍ\n딥러닝 개발 프레임워크 활용 역량을 보유하신 분\nㆍ\n디지털 제조 및 자동화 시스템에 대한 이해도를 보유하신 분\n우대사항\nㆍ설계시스템 (CAD) 자동화 및 PLM 개발 경험을 보유하신 분\nㆍ\nAI, 빅데이터 관련 자격증을 보유하신 분\n정보시스템 설계 및 개발\n주요업무\nㆍApplication Architecture 수행\n- 정보시스템 구조 설계 및 기술 스택 선정\n-\n정보시스템 관련 비즈니스/기술 요구사항 수집 및 분석\n-\n정보시스템 성능 모니터링 및 최적화\nㆍ\n정보시스템 개선/구축을 위한 분석 및 설계\n-\n비즈니스 프로세스 설계 및 상세 기능 정의\n-\n테스트 계획 수립 및 문제 해결\nㆍ\n정보시스템 개선/구축 프로젝트 관리 및 업무 수행\n-\n프로젝트 계획·실행·관리 및 품질 관리\n-\n국내외 프로젝트 수행 및 산출물 관리\n자격요건\nㆍ비즈니스 프로세스 분석 및 설계 업무 경험을 보유하신 분\nㆍ\n시스템 아키텍처에 대한 지식 및 DBMS에 대한 이해도를 보유하신 분\nㆍ\n프로젝트 성과 측정 및 손익 관리 역량을 보유하신 분\n우대사항\nㆍ차세대급 SI 프로젝트 수행 경험을 보유하신 분\nㆍ\n최신 IT 기술에 대한 지식 및 경험을 보유하신 분 (클라우드컴퓨팅, AI, 빅데이터 등)\nㆍ\n유관 자격증을 보유하신 분 (PMP, 정보처리기사 등)\nㆍ\n비즈니스 영어 활용 역량을 보유하신 분\n플랜트 IT 시스템 개발 및 운영\n주요업무\nㆍAVEVA Unified Engineering 및 Spectrum 시스템 운영 및 유지관리\nㆍ\nAVEVA E3D CAD(의장 분야) 환경 설정 및 관리자(Admin) 업무 수행\nㆍ\n해양 엔지니어링 분야 자재/구매 관련 솔루션 개발\nㆍ\nOracle Fusion 기반 시스템 개발 및 운영 지원\n자격요건\nㆍ조선 CAD(AM, S3D) Admin 운영 경력 3년 이상 및 해양/\n플랜트 프로젝트 경험을 보유하신 분\nㆍ\nOracle Fusion, OIC(Oracle Integration Cloud), Visual Builder\n운영 및 개발 경험을 보유하신 분\nㆍ\n비즈니스 영어 활용 역량을 보유하신 분 (OPIc IH 이상)\n우대사항\nㆍAVEVA CAD 솔루션 운영 경험을 보유하신 분\nㆍ\nOracle Fusion 관련 자격증을 보유하신 분\n※ 부산 근무 포지션의 경우, 일정기간 거제 온보딩 후 부산 근무 예정입니다.\n공통지원자격\nㆍ학사 이상의 학위를 보유하신 분 (컴퓨터공학, 전산학, 통계학, 산업공학, 조선공학 등 관련 전공자 우대)\nㆍ\n지원 포지션의 5년 이상의 유관 직무 경력을 보유하신 분\nㆍ\n해외여행에 결격사유가 없는 분 (남성의 경우, 군필 또는 면제)\n* 국가보훈대상자(취업보호대상자 증명서 제출) 및 장애인은 관련 법규에 의거하여 우대합니다.\n기타사항\nㆍ\n접수기간 :\n2025. 07. 30 ~ 2025. 08. 24  15:00\nㆍ접수방법 :\n당사 채용 홈페이지 지원\nㆍ자세한 상세요강은 반드시 채용 홈페이지에서 직접 확인해 주시기 바랍니다.\n기업 채용 홈페이지 바로가기 click	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "한화오션(주)", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47466643&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 8215, "detail_text_len": 2187, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47466643?Oem_Code=C1", "meta": {"경력": "Y", "부산": "Y", "서울": "Y"}, "title": "[IT 대규모 채용] 시스템 개발/운영 경력사원 채용경력서울·경남·부산대졸↑마감 (~2025.08.24)웹개발자,시스템엔지니어외2", "job_id": "47466643"}}	2025-08-24 19:00:25.97412+00
13	jobkorea	한화오션(주)	1000242	47466033	https://www.jobkorea.co.kr/Recruit/GI_Read/47466033?Oem_Code=C1	한화오션 채용 - [IT 대규모 채용] ICT 운영 경력사원 채용 (Shared Service 시스템 운영) | 잡코리아	한화오션(주)\n[IT 대규모 채용] ICT 운영 경력사원 채용\n(Shared Service\n시스템 운영)\n포지션 및 자격요건\nShared Service\n시스템 운영\n주요업무\nㆍIT MP 후속에 따른 신규 플랫폼 운영 (AI/IoT/빅데이터/IT거버넌스 등)\nㆍ\nAI/전사 표준 아키텍처 관리 (LCAP, DAO 등)\n자격요건\nㆍJAVA기반 풀스택 개발 경험을 보유하신 분\nㆍ\nSpring 및 전자정부 표준프레임워크 활용 경험을 보유하신 분\nㆍ\nHTML5, CSS3, JavaScript, jQuery, Vue.js를 활용한 웹 개발 경험을 보유하신 분\nㆍ\nDBMS(Oracle, MSSQL) 활용 역량을 보유하신 분\n우대사항\nㆍ웹 표준에 대한 이해와 경험을 보유하신 분 (크로스브라우징, 웹 접근성, 모바일 대응 포함)\nㆍ\n홈페이지 및 경영지원 웹 개발에 대한 경험을 보유하신 분\nㆍ\n포토샵/일러스트 활용 역량을 보유하신 분\n※ 부산 근무 포지션의 경우, 일정기간 거제 온보딩 후 부산 근무 예정입니다.\n공통지원자격\nㆍ학사 이상의 학위를 보유하신 분 (컴퓨터공학, 전산학, 통계학, 산업공학, 조선공학 등 관련 전공자 우대)\nㆍ\n지원 포지션의 5년 이상의 유관 직무 경력을 보유하신 분\nㆍ\n해외여행에 결격사유가 없는 분 (남성의 경우, 군필 또는 면제)\n* 국가보훈대상자(취업보호대상자 증명서 제출) 및 장애인은 관련 법규에 의거하여 우대합니다.\n기타사항\nㆍ\n접수기간 :\n2025. 07. 30 ~ 2025. 08. 24  15:00\nㆍ접수방법 :\n당사 채용 홈페이지 지원\nㆍ자세한 상세요강은 반드시 채용 홈페이지에서 직접 확인해 주시기 바랍니다.\n기업 채용 홈페이지 바로가기 click	2022-11-04	2025-08-24	{"type": "source_meta", "detail": {"career": "경력", "salary": "연봉", "company": "한화오션(주)", "end_date": "2022.11.04", "location": "서울시", "education": "학력", "iframe_url": "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno=47466033&blnKeepInLink=0&rPageCode=", "start_date": "2022.11.04", "detail_html_len": 4131, "detail_text_len": 832, "employment_type": "정규직"}, "source": "jobkorea", "list_item": {"href": "https://www.jobkorea.co.kr/Recruit/GI_Read/47466033?Oem_Code=C1", "meta": {"경력": "Y", "부산": "Y", "서울": "Y"}, "title": "[IT 대규모 채용] ICT 운영 경력사원 채용 (Shared Service 시스템 ...경력서울·경남·부산대졸↑마감 (~2025.08.24)웹개발자,시스템엔지니어외1", "job_id": "47466033"}}	2025-08-24 19:00:25.977654+00
\.

COMMIT;