# src/domain/company_analysis/models.py
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

# Pydantic v2 / v1 호환 처리
try:
    from pydantic import ConfigDict, model_validator

    _V2 = True
except Exception:  # pydantic v1
    from pydantic import root_validator as model_validator  # type: ignore

    _V2 = False


__all__ = [
    "RequirementsBlock",
    "ExtrasBlock",
    "CompanyKnowledge",
    "CompanyJDStyle",
]


def _normalize_str_list(xs: Optional[List[str]]) -> List[str]:
    """공백 제거, 빈 항목 제거, 중복 제거(순서 보존). None -> []."""
    if not xs:
        return []
    out: List[str] = []
    seen = set()
    for x in xs:
        if x is None:
            continue
        s = x.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _normalize_str(s: Optional[str]) -> Optional[str]:
    """문자열 공백 트리밍. None 또는 빈 문자열은 None으로 통일."""
    if s is None:
        return None
    t = s.strip()
    return t if t else None


class RequirementsBlock(BaseModel):
    """
    필수/우대 역량 블록 공통 모델.
    """

    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    competencies: List[str] = Field(default_factory=list, description="핵심 역량")
    skills: List[str] = Field(default_factory=list, description="필수/우대 기술 스택")
    project_experience: List[str] = Field(default_factory=list, description="요구/우대 프로젝트 경험")

    if _V2:

        @model_validator(mode="after")
        def _clean(self) -> "RequirementsBlock":
            self.competencies = _normalize_str_list(self.competencies)
            self.skills = _normalize_str_list(self.skills)
            self.project_experience = _normalize_str_list(self.project_experience)
            return self

    else:

        @model_validator(pre=False)  # type: ignore[misc]
        def _clean_v1(cls, values: Dict[str, Any]) -> Dict[str, Any]:  # noqa: N805
            values["competencies"] = _normalize_str_list(values.get("competencies"))
            values["skills"] = _normalize_str_list(values.get("skills"))
            values["project_experience"] = _normalize_str_list(values.get("project_experience"))
            return values


class ExtrasBlock(BaseModel):
    """
    복리후생, 근무지, 채용 프로세스 등 부가 정보.
    """

    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    benefits: List[str] = Field(default_factory=list, description="복리후생 목록")
    locations: List[str] = Field(default_factory=list, description="근무지/근무 형태")
    hiring_process: List[str] = Field(default_factory=list, description="채용 전형 단계")

    if _V2:

        @model_validator(mode="after")
        def _clean(self) -> "ExtrasBlock":
            self.benefits = _normalize_str_list(self.benefits)
            self.locations = _normalize_str_list(self.locations)
            self.hiring_process = _normalize_str_list(self.hiring_process)
            return self

    else:

        @model_validator(pre=False)  # type: ignore[misc]
        def _clean_v1(cls, values: Dict[str, Any]) -> Dict[str, Any]:  # noqa: N805
            values["benefits"] = _normalize_str_list(values.get("benefits"))
            values["locations"] = _normalize_str_list(values.get("locations"))
            values["hiring_process"] = _normalize_str_list(values.get("hiring_process"))
            return values


class CompanyKnowledge(BaseModel):
    """
    회사 소개/문화/가치/인재상 + (필수/우대) 요구사항 + 부가정보로 구성된 회사 지식 그래프의 요약 형태.
    LLM의 구조화 출력(JSON)과 1:1 매핑되며, 추가 필드는 허용하지 않습니다.
    """

    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    # 개요/문화/가치/인재상
    introduction: Optional[str] = Field(default=None, description="회사/조직 소개 요약")
    culture: Optional[str] = Field(default=None, description="조직 문화 요약")
    values: Optional[List[str]] = Field(default=None, description="핵심 가치(리스트, 없으면 null 허용)")
    ideal_traits: Optional[List[str]] = Field(default=None, description="선호하는 인재상(리스트, 없으면 null 허용)")

    # 요구/우대, 부가 정보
    requirements: RequirementsBlock = Field(default_factory=RequirementsBlock, description="필수 요건")
    preferred: RequirementsBlock = Field(default_factory=RequirementsBlock, description="우대 요건")
    extras: ExtrasBlock = Field(default_factory=ExtrasBlock, description="부가 정보")

    if _V2:

        @model_validator(mode="after")
        def _clean(self) -> "CompanyKnowledge":
            self.introduction = _normalize_str(self.introduction)
            self.culture = _normalize_str(self.culture)

            # Optional[List[str]]: 비거나 정규화 결과가 []이면 None 유지
            _values = _normalize_str_list(self.values or [])
            self.values = _values if _values else None

            _traits = _normalize_str_list(self.ideal_traits or [])
            self.ideal_traits = _traits if _traits else None
            return self

    else:

        @model_validator(pre=False)  # type: ignore[misc]
        def _clean_v1(cls, values: Dict[str, Any]) -> Dict[str, Any]:  # noqa: N805
            values["introduction"] = _normalize_str(values.get("introduction"))
            values["culture"] = _normalize_str(values.get("culture"))

            _values = _normalize_str_list(values.get("values") or [])
            values["values"] = _values if _values else None

            _traits = _normalize_str_list(values.get("ideal_traits") or [])
            values["ideal_traits"] = _traits if _traits else None
            return values


class CompanyJDStyle(BaseModel):
    """
    회사 JD 스타일(톤 키워드, 섹션 구조, 예시/템플릿)을 캡처하는 모델.
    LLM 구조화 출력(JSON)과 1:1 매핑되며, 추가 필드는 허용하지 않습니다.
    """

    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    style_label: str = Field(..., description='예: "회사-공식적-간결"')
    tone_keywords: List[str] = Field(default_factory=list, description="톤/스타일 키워드")
    section_outline: List[str] = Field(default_factory=list, description="JD 섹션 순서")
    example_jd_markdown: str = Field(..., description="예시 JD (Markdown)")
    templates: Dict[str, str] = Field(default_factory=dict, description="섹션별 템플릿 문구 (키: 섹션명)")

    if _V2:

        @model_validator(mode="after")
        def _clean(self) -> "CompanyJDStyle":
            self.style_label = _normalize_str(self.style_label) or ""  # required
            self.example_jd_markdown = _normalize_str(self.example_jd_markdown) or ""  # required

            self.tone_keywords = _normalize_str_list(self.tone_keywords)
            self.section_outline = _normalize_str_list(self.section_outline)

            # 템플릿 키/값 트리밍 + 빈 값 제거
            if self.templates:
                cleaned: Dict[str, str] = {}
                for k, v in self.templates.items():
                    kk = (k or "").strip()
                    vv = (v or "").strip()
                    if kk and vv:
                        cleaned[kk] = vv
                self.templates = cleaned
            return self

    else:

        @model_validator(pre=False)  # type: ignore[misc]
        def _clean_v1(cls, values: Dict[str, Any]) -> Dict[str, Any]:  # noqa: N805
            values["style_label"] = _normalize_str(values.get("style_label")) or ""
            values["example_jd_markdown"] = _normalize_str(values.get("example_jd_markdown")) or ""

            values["tone_keywords"] = _normalize_str_list(values.get("tone_keywords"))
            values["section_outline"] = _normalize_str_list(values.get("section_outline"))

            templates = values.get("templates") or {}
            cleaned: Dict[str, str] = {}
            for k, v in templates.items():
                kk = (k or "").strip()
                vv = (v or "").strip()
                if kk and vv:
                    cleaned[kk] = vv
            values["templates"] = cleaned
            return values
