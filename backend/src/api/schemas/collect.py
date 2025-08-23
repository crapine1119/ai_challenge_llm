from typing import Optional, Dict

from pydantic import BaseModel, Field


class CollectRequest(BaseModel):
    company_id: int = Field(..., description="JobKorea의 회사 ID (크롤링용)")
    company_code: str = Field(..., description="내부 회사 코드 (DB 저장용)")
    job_code: str = Field(..., description="내부 직무 코드 (DB 저장용)")
    list_params: Optional[Dict[str, str]] = Field(
        default=None, description="크롤링 리스트 페이지에 들어갈 쿼리 파라미터"
    )
    max_details: int = Field(default=5, description="수집할 최대 공고 수")
    save_meta: bool = Field(default=True, description="generated_insights.analysis_json에 메타데이터 저장 여부")


class CollectResponse(BaseModel):
    saved_raw: int = Field(..., description="raw_job_descriptions 테이블에 저장된 건수")
    saved_meta: int = Field(..., description="generated_insights 테이블에 저장된 메타데이터 건수")
