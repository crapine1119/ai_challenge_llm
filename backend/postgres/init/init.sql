-- init.sql (FULL)

-- DROP for dev reset (원하면 주석 처리)
DROP TABLE IF EXISTS generated_jd_templates CASCADE;
DROP TABLE IF EXISTS jd_styles CASCADE;
DROP TABLE IF EXISTS generated_skills CASCADE;
DROP TABLE IF EXISTS generated_insights CASCADE;
DROP TABLE IF EXISTS raw_job_descriptions CASCADE;
DROP TABLE IF EXISTS job_code_map CASCADE;

-- 1) 직무 코드 매핑
CREATE TABLE job_code_map (
    job_code VARCHAR(10) PRIMARY KEY,
    job_name TEXT NOT NULL
);

INSERT INTO job_code_map (job_code, job_name) VALUES
    ('1000201', '인사담당자'),
    ('1000242', 'AI/ML엔지니어'),
    ('1000229', '백엔드개발자'),
    ('1000230', '프론트엔드개발자'),
    ('1000187', '마케팅기획'),
    ('1000210', '재무담당자');

-- 2) 원시 JD 저장 (크롤링 결과)
CREATE TABLE raw_job_descriptions (
    id SERIAL PRIMARY KEY,
    source VARCHAR(32) NOT NULL DEFAULT 'jobkorea',
    company_code VARCHAR(50) NOT NULL,
    job_code VARCHAR(10) REFERENCES job_code_map(job_code) ON UPDATE CASCADE ON DELETE SET NULL,

    job_id VARCHAR(64) NOT NULL,          -- 잡코리아 GI_Read/{job_id}
    url TEXT NOT NULL,
    title TEXT,

    jd_text TEXT NOT NULL,                -- 본문 텍스트(정제)
    end_date DATE NOT NULL DEFAULT CURRENT_DATE,

    CONSTRAINT uq_raw_source_jobid UNIQUE (source, job_id)
);

CREATE INDEX idx_raw_job_code ON raw_job_descriptions(job_code);
CREATE INDEX idx_raw_company_code ON raw_job_descriptions(company_code);
CREATE INDEX idx_raw_end_date ON raw_job_descriptions(end_date);

-- 3) 분석/생성 결과 저장
CREATE TABLE generated_insights (
    id SERIAL PRIMARY KEY,
    company_code VARCHAR(50) NOT NULL,
    job_code VARCHAR(10) REFERENCES job_code_map(job_code) ON UPDATE CASCADE ON DELETE SET NULL,
    jd_id INTEGER REFERENCES raw_job_descriptions(id) ON UPDATE CASCADE ON DELETE CASCADE,

    analysis_json JSONB,          -- 구조화 분석 결과(옵션)
    llm_text TEXT,                -- LLM 생성 결과(별도 컬럼)

    generated_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_insights_job_code ON generated_insights(job_code);
CREATE INDEX idx_insights_jd_id ON generated_insights(jd_id);

-- 4) 기본 기술(주기 업데이트)
CREATE TABLE generated_skills (
    job_code VARCHAR(10) PRIMARY KEY REFERENCES job_code_map(job_code),
    skills_json JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5) JD 스타일 정의
CREATE TABLE jd_styles (
    style_id SERIAL PRIMARY KEY,
    style_name TEXT NOT NULL UNIQUE
);

INSERT INTO jd_styles (style_name) VALUES
    ('정형적'),
    ('notion 스타일'),
    ('기술 상세히'),
    ('사용자 커스텀');

-- 6) 스타일별 JD 생성 결과
CREATE TABLE generated_jd_templates (
    id SERIAL PRIMARY KEY,
    company_code VARCHAR(50) NOT NULL,
    job_code VARCHAR(10) REFERENCES job_code_map(job_code) ON UPDATE CASCADE ON DELETE SET NULL,
    style_id INTEGER REFERENCES jd_styles(style_id) ON UPDATE CASCADE ON DELETE SET NULL,
    jd_text TEXT NOT NULL,
    generated_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
