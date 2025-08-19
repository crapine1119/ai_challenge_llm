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
