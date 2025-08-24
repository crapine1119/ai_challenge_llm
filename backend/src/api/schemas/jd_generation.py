from datetime import datetime
from typing import Optional, Literal, List, Dict, Any

from pydantic import BaseModel, Field

from api.schemas.common import LLMOptions

StyleSource = Literal["generated", "default"]


class JDGenerateRequest(LLMOptions):
    company_code: str
    job_code: str
    language: Optional[str] = "ko"
    style_source: StyleSource = Field(default="default")
    default_style_name: Optional[str] = None

    # 직접 주입도 유지(있으면 DB 조회 생략)
    knowledge_override: Optional[Dict[str, Any]] = None
    style_override: Optional[Dict[str, Any]] = None


# schemas/jd_generation.py
class JDItem(BaseModel):
    id: int
    company_code: str
    job_code: str
    title: Optional[str]
    markdown: str  # <- alias 제거
    created_at: datetime


class JDGenerateResponse(BaseModel):
    company_code: str
    job_code: str
    markdown: str
    saved_id: int


class JDGetResponse(JDItem):
    pass


class JDListResponse(BaseModel):
    total: int
    items: List[JDItem]
