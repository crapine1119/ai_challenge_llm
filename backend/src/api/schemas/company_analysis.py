# src/api/schemas/company_analysis.py
from typing import Optional, Dict, Any

from pydantic import BaseModel

from api.schemas.common import LLMOptions
from domain.company_analysis.models import CompanyKnowledge, CompanyJDStyle


# ---------- Zero-shot ----------
class KnowledgeZeroShotRequest(LLMOptions):
    job_code: str
    language: Optional[str] = "ko"
    save: bool = True


class KnowledgeZeroShotResponse(BaseModel):
    job_code: str
    company_code: str = "__global__"
    knowledge: CompanyKnowledge


# ---------- Few-shot ----------
class KnowledgeFewShotRequest(LLMOptions):
    company_code: str
    job_code: str
    language: Optional[str] = "ko"
    top_k: int = 3
    within_days: Optional[int] = None
    min_chars_per_doc: int = 200
    save: bool = True


class KnowledgeFewShotResponse(BaseModel):
    company_code: str
    job_code: str
    knowledge: CompanyKnowledge


# ---------- Style only ----------
class StyleOnlyRequest(LLMOptions):
    company_code: str
    job_code: str
    language: Optional[str] = "ko"
    top_k: int = 3
    within_days: Optional[int] = None
    min_chars_per_doc: int = 200
    save: bool = True


class StyleOnlyResponse(BaseModel):
    company_code: str
    job_code: str
    style: CompanyJDStyle


# ---------- Analyze All (few-shot + style) ----------
class AnalyzeAllRequest(LLMOptions):
    company_code: str
    job_code: str
    language: Optional[str] = "ko"
    save: bool = True


class AnalyzeAllResponse(BaseModel):
    company_code: str
    job_code: str
    knowledge: Dict[str, Any]  # CompanyKnowledge.model_dump()
    style: Dict[str, Any]  # CompanyJDStyle.model_dump()


class StyleOnlyResponse(BaseModel):
    company_code: str
    job_code: str
    style: CompanyJDStyle
