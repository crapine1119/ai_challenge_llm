from typing import Literal, Optional

from pydantic import BaseModel, Field

from api.schemas.common import LLMOptions
from domain.company_analysis.models import CompanyKnowledge, CompanyJDStyle

StyleSource = Literal["generated", "default"]


class JDGenerateRequest(LLMOptions):
    company_code: str
    job_code: str
    language: Optional[str] = "ko"

    # 어떤 스타일을 쓸지 선택
    style_source: StyleSource = Field(default="generated", description='"generated"=생성 스냅샷, "default"=프리셋')
    default_style_name: Optional[str] = Field(
        default=None, description='style_source="default"일 때 사용할 프리셋 이름'
    )

    # 직접 주입(옵션) — 있으면 DB 조회 대신 사용
    knowledge_override: Optional[CompanyKnowledge] = None
    style_override: Optional[CompanyJDStyle] = None


class JDGenerateResponse(BaseModel):
    company_code: str
    job_code: str
    markdown: str
