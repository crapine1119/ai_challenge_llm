from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel

# Pydantic v2 / v1 호환 extra 처리
try:
    from pydantic import ConfigDict, model_validator

    _V2 = True
except Exception:  # v1
    from pydantic import root_validator as model_validator  # type: ignore

    _V2 = False


class PromptFile(BaseModel):
    """
    DB/파일 기반 프롬프트 정의.
    - prompt_type: 'chat' | 'string'
    - chat: messages = [{"role": "...", "content": "..."}]
    - string: template = "...{{ var }}..."
    """

    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

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

    if _V2:

        @model_validator(mode="after")  # pydantic v2
        def _fill_defaults(self):
            if self.params is None:
                self.params = {}
            if self.required_vars is None:
                self.required_vars = []
            return self

    else:

        @model_validator(pre=False)  # pydantic v1
        def _fill_defaults(cls, values):  # type: ignore
            if values.get("params") is None:
                values["params"] = {}
            if values.get("required_vars") is None:
                values["required_vars"] = []
            return values
