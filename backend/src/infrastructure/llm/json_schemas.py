from typing import Any, Dict
from typing import Type, Optional

from pydantic import BaseModel

# --- 도메인 모델에서 스키마 생성 ---
from domain.company_analysis.models import CompanyKnowledge, CompanyJDStyle
from domain.jd_generation.models import JDGeneration


def _to_json_schema(model_cls: Type[BaseModel]) -> Dict[str, Any]:
    return model_cls.model_json_schema()


def _enforce_no_additional_props(schema: Dict[str, Any]) -> Dict[str, Any]:
    def recurse(node: Any):
        if isinstance(node, dict):
            if node.get("type") == "object":
                # ✅ 이미 명시된 경우( True / False / dict 스키마 )는 덮어쓰지 않음
                if "additionalProperties" not in node:
                    node["additionalProperties"] = False

                # properties
                props = node.get("properties")
                if isinstance(props, dict):
                    for v in props.values():
                        recurse(v)

                # items (배열)
                if "items" in node:
                    recurse(node["items"])

                # anyOf / oneOf / allOf
                for key in ("anyOf", "oneOf", "allOf"):
                    vs = node.get(key)
                    if isinstance(vs, list):
                        for v in vs:
                            recurse(v)

            elif "items" in node:
                recurse(node["items"])

        elif isinstance(node, list):
            for v in node:
                recurse(v)

    recurse(schema)
    return schema


# ... 기존 _to_json_schema, _enforce_no_additional_props 유지

JD_GENERATION_JSON_SCHEMA: Dict[str, Any] = _enforce_no_additional_props(_to_json_schema(JDGeneration))
COMPANY_KNOWLEDGE_JSON_SCHEMA: Dict[str, Any] = _enforce_no_additional_props(_to_json_schema(CompanyKnowledge))
COMPANY_JD_STYLE_JSON_SCHEMA: Dict[str, Any] = _enforce_no_additional_props(_to_json_schema(CompanyJDStyle))

# ✅ 중앙 레지스트리
SCHEMA_REGISTRY: Dict[str, Dict[str, Any]] = {
    "company_knowledge_v1": COMPANY_KNOWLEDGE_JSON_SCHEMA,
    "company_jd_style_v1": COMPANY_JD_STYLE_JSON_SCHEMA,
    "jd_generation_v1": JD_GENERATION_JSON_SCHEMA,
}


def resolve_json_schema(key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not key:
        return None
    return SCHEMA_REGISTRY.get(key)
