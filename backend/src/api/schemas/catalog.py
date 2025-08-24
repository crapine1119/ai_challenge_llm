# src/api/schemas/catalog.py
from typing import List

from pydantic import BaseModel, Field


class CompanyListResponse(BaseModel):
    companies: List[str] = Field(default_factory=list, description="수집된 회사 코드 목록")


class JobItem(BaseModel):
    code: str
    name: str


class JobListResponse(BaseModel):
    company_code: str
    jobs: List[JobItem] = Field(default_factory=list)
