from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from domain.company_analysis.models import CompanyJDStyle


class StylePresetItem(BaseModel):
    style_name: str
    is_active: bool = True
    style: CompanyJDStyle


class StylePresetListResponse(BaseModel):
    items: List[StylePresetItem]


class StylePresetResponse(BaseModel):
    style_name: str
    is_active: bool = True
    style: CompanyJDStyle


class GeneratedStyleItem(BaseModel):
    id: int
    company_code: str
    job_code: str
    created_at: datetime
    style: CompanyJDStyle


class GeneratedStyleLatestResponse(BaseModel):
    company_code: str
    job_code: str
    latest: Optional[GeneratedStyleItem] = Field(default=None)


class GeneratedStyleListResponse(BaseModel):
    total: int
    items: List[GeneratedStyleItem]
