# src/infrastructure/db/seed/schema.py
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class JobCodeSeed(BaseModel):
    job_code: str
    job_name: str


class PromptSeed(BaseModel):
    prompt_key: str
    prompt_version: str
    language: Optional[str] = None
    prompt_type: str  # 'chat' | 'string'
    messages: Optional[List[Dict[str, Any]]] = None
    template: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    json_schema_key: Optional[str] = None
    required_vars: List[str] = Field(default_factory=list)
    is_active: bool = True


class JDStyleSeed(BaseModel):
    style_name: str
    prompt_key: Optional[str] = None
    prompt_version: Optional[str] = None
    is_active: bool = True


class SeedBundle(BaseModel):
    bundle: str = "core"
    version: str = "v1"
    job_codes: List[JobCodeSeed] = Field(default_factory=list)
    prompts: List[PromptSeed] = Field(default_factory=list)
    jd_styles: List[JDStyleSeed] = Field(default_factory=list)
