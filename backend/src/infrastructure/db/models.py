from sqlalchemy import Boolean
from sqlalchemy import Column, Integer, String, Text, Date, ForeignKey, JSON, TIMESTAMP, text, UniqueConstraint
from sqlalchemy.orm import relationship

from infrastructure.db.database import Base


class JobCode(Base):
    __tablename__ = "job_code_map"
    job_code = Column(String(10), primary_key=True)
    job_name = Column(String, nullable=False)


class RawJobDescription(Base):
    __tablename__ = "raw_job_descriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(32), nullable=False, default="jobkorea")
    company_code = Column(String(50), nullable=False)
    job_code = Column(String(10), ForeignKey("job_code_map.job_code"))

    job_id = Column(String(64), nullable=False)
    url = Column(Text, nullable=False)
    title = Column(Text)

    jd_text = Column(Text, nullable=False)
    end_date = Column(Date, server_default=text("CURRENT_DATE"), nullable=False)

    job = relationship("JobCode")

    __table_args__ = (UniqueConstraint("source", "job_id", name="uq_raw_source_jobid"),)


class GeneratedInsight(Base):
    __tablename__ = "generated_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_code = Column(String(50), nullable=False)
    job_code = Column(String(10), ForeignKey("job_code_map.job_code"))
    jd_id = Column(Integer, ForeignKey("raw_job_descriptions.id"))

    analysis_json = Column(JSON)  # 구조화 분석
    llm_text = Column(Text)  # LLM 생성결과

    generated_date = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    job = relationship("JobCode")
    raw = relationship("RawJobDescription")


class Prompt(Base):
    __tablename__ = "prompts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    prompt_key = Column(Text, nullable=False)
    prompt_version = Column(Text, nullable=False)
    language = Column(Text, nullable=True)
    prompt_type = Column(Text, nullable=False)  # 'chat' | 'string'
    messages = Column(JSON, nullable=True)  # list[{"role","content"}]
    template = Column(Text, nullable=True)  # string 템플릿
    params = Column(JSON, nullable=False, server_default=text("'{}'::jsonb"))
    json_schema_key = Column(Text, nullable=True)
    required_vars = Column(JSON, nullable=False, server_default=text("'[]'::jsonb"))
    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))

    __table_args__ = (
        UniqueConstraint("prompt_key", "prompt_version", text("COALESCE(language, '')"), name="uq_prompt_key_ver_lang"),
    )


class JDStyle(Base):
    __tablename__ = "jd_styles"
    style_id = Column(Integer, primary_key=True, autoincrement=True)
    style_name = Column(Text, unique=True, nullable=False)
    prompt_key = Column(Text)
    prompt_version = Column(Text)
    is_active = Column(Boolean, server_default=text("TRUE"))
