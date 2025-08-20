from typing import Any, Dict, Type

from pydantic import BaseModel

# pydantic v2 / v1 호환
try:
    _V2 = True

    def _to_json_schema(model_cls: Type[BaseModel]) -> Dict[str, Any]:
        return model_cls.model_json_schema()

except Exception:
    _V2 = False

    def _to_json_schema(model_cls: Type[BaseModel]) -> Dict[str, Any]:
        return model_cls.schema()  # v1


def _enforce_no_additional_props(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    객체 타입에 대해 additionalProperties:false를 재귀적으로 보정합니다.
    (도메인 모델에 extra='forbid'가 설정되어 있어도 안전망 차원에서 적용)
    """

    def recurse(node: Any):
        if isinstance(node, dict):
            if node.get("type") == "object":
                node.setdefault("additionalProperties", False)
                props = node.get("properties", {})
                for v in props.values():
                    recurse(v)
            elif "anyOf" in node:
                for v in node["anyOf"]:
                    recurse(v)
            elif "oneOf" in node:
                for v in node["oneOf"]:
                    recurse(v)
            elif "allOf" in node:
                for v in node["allOf"]:
                    recurse(v)
            elif "items" in node:
                recurse(node["items"])
        elif isinstance(node, list):
            for v in node:
                recurse(v)

    recurse(schema)
    return schema


# --- 도메인 모델에서 스키마 생성 ---
from domain.company_analysis.models import CompanyKnowledge, CompanyJDStyle

COMPANY_KNOWLEDGE_JSON_SCHEMA: Dict[str, Any] = _enforce_no_additional_props(_to_json_schema(CompanyKnowledge))
COMPANY_JD_STYLE_JSON_SCHEMA: Dict[str, Any] = _enforce_no_additional_props(_to_json_schema(CompanyJDStyle))
