from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Date,
    ForeignKey,
    JSON,
    TIMESTAMP,
    text,
    UniqueConstraint,
)
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
    job_code = Column(String(10), ForeignKey("job_code_map.job_code"), nullable=True)

    job_id = Column(String(64), nullable=False)
    url = Column(Text, nullable=False)
    title = Column(Text)

    jd_text = Column(Text, nullable=False)
    end_date = Column(Date, server_default=text("CURRENT_DATE"), nullable=False)

    # ✅ 수집 메타를 원본 테이블에 저장
    meta_json = Column(JSON, nullable=False, server_default=text("'{}'::jsonb"))
    content_hash = Column(Text, nullable=True)  # 또는 String(length), depending on schema

    job = relationship("JobCode")

    __table_args__ = (UniqueConstraint("source", "job_id", name="uq_raw_source_jobid"),)


class GeneratedInsight(Base):
    __tablename__ = "generated_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jd_id = Column(Integer, ForeignKey("raw_job_descriptions.id"), nullable=True)
    company_code = Column(String(50), nullable=False)
    job_code = Column(String(10), ForeignKey("job_code_map.job_code"), nullable=True)

    analysis_json = Column(JSON)  # 구조화 분석
    llm_text = Column(Text)  # LLM 생성결과

    # ✅ 프롬프트 참조/비정규화 컬럼
    prompt_id = Column(Integer, ForeignKey("prompts.id", ondelete="SET NULL"), nullable=True)
    prompt_key = Column(Text, nullable=True)
    prompt_version = Column(Text, nullable=True)
    prompt_language = Column(Text, nullable=True)

    generated_date = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    job = relationship("JobCode")
    raw = relationship("RawJobDescription")
    prompt = relationship("Prompt", lazy="joined")


class JDStyle(Base):
    __tablename__ = "jd_styles"
    style_id = Column(Integer, primary_key=True, autoincrement=True)
    style_name = Column(Text, unique=True, nullable=False)
    payload_json = Column(JSON, nullable=False, server_default=text("'{}'::jsonb"))  # ← 변경
    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))


class GeneratedStyle(Base):
    __tablename__ = "generated_styles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_code = Column(Text, nullable=False)
    job_code = Column(Text, nullable=True)

    style_label = Column(Text, nullable=False, server_default=text("''"))
    tone_keywords = Column(JSON, nullable=False, server_default=text("'[]'::jsonb"))
    section_outline = Column(JSON, nullable=False, server_default=text("'[]'::jsonb"))
    templates = Column(JSON, nullable=False, server_default=text("'{}'::jsonb"))
    digest_md = Column(Text, nullable=True)

    prompt_id = Column(Integer, ForeignKey("prompts.id"), nullable=True)
    prompt_key = Column(Text, nullable=True)
    prompt_version = Column(Text, nullable=True)
    prompt_language = Column(Text, nullable=False, server_default=text("''"))

    provider = Column(Text, nullable=True)
    model = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))


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
    content_hash = Column(Text, nullable=True)

    # ⚠️ 주의: SQLAlchemy의 UniqueConstraint는 함수표현을 허용하지 않습니다.
    # init.sql에서 이미 COALESCE 기반 고유 제약/인덱스를 생성하므로 ORM에선 별도 정의하지 않습니다.
    __table_args__ = ()


class GeneratedJD(Base):
    __tablename__ = "generated_jds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_code = Column(Text, nullable=False)
    job_code = Column(Text, ForeignKey("job_code_map.job_code", ondelete="SET NULL"), nullable=True)
    title = Column(Text)
    jd_markdown = Column(Text, nullable=False)
    sections = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=False, server_default=text("'{}'::jsonb"))
    provider = Column(Text, nullable=True)
    model_name = Column(Text, nullable=True)
    prompt_key = Column(Text, nullable=True)
    prompt_version = Column(Text, nullable=True)
    prompt_language = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))

    style_source = Column(Text)  # 'generated' | 'default' | 'override'
    style_preset_name = Column(Text)  # default 프리셋명
    style_snapshot_id = Column(BigInteger, ForeignKey("generated_styles.id", ondelete="SET NULL"))
    # ✅ 단방향 relationship (반대편 속성 필요 없음)
    job_code_ref = relationship("JobCode", lazy="joined")
