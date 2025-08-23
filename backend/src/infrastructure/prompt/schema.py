# src/infrastructure/prompt/schema.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, ConfigDict, model_validator


class PromptFile(BaseModel):
    """
    DB/파일 기반 프롬프트 정의.
    - prompt_type: 'chat' | 'string'
    - chat: messages = [{"role": "...", "content": "..."}]
    - string: template = "...{{ var }}..."
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    version: str
    language: Optional[str] = None

    prompt_type: Literal["chat", "string"]

    # chat 전용
    messages: Optional[List[Dict[str, Any]]] = None

    # string 전용
    template: Optional[str] = None

    # 공통 메타 (가변 기본값은 None → validator에서 치환)
    params: Optional[Dict[str, Any]] = None
    json_schema_key: Optional[str] = None
    required_vars: Optional[List[str]] = None

    @model_validator(mode="after")  # pydantic v2
    def _fill_defaults(self):
        if self.params is None:
            self.params = {}
        if self.required_vars is None:
            self.required_vars = []
        return self


class PromptTemplateInput(BaseModel):
    """
    서비스 레이어에서 PromptManager.render_chat(...) 호출 시 사용하는 입력 모델.
    - style_name이 주어지면 스타일 매핑을 우선 적용하고, 없으면 (prompt_key, prompt_version)을 직접 사용.
    - variables에는 템플릿에서 참조하는 모든 변수를 넣는다.
    """

    model_config = ConfigDict(extra="forbid")
    prompt_key: str
    prompt_version: str
    language: Optional[str] = None
    style_name: Optional[str] = None
    variables: Dict[str, Any] = {}
