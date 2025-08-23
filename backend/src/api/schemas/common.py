# src/api/schemas/common.py
from typing import Literal, Optional

from pydantic import BaseModel, Field

Provider = Literal["openai", "gemini"]


class LLMOptions(BaseModel):
    provider: Optional[Provider] = Field(default=None, description="LLM 공급자 (없으면 .env 기본값)")
    model: Optional[str] = Field(default=None, description="모델명 (없으면 .env 기본값)")
    json_format: bool = Field(default=False, description="JSON 강제 포맷 사용 여부")
