from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, model_validator


def _norm_str(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    t = s.strip()
    return t if t else None


def _norm_list(xs: Optional[List[str]]) -> List[str]:
    if not xs:
        return []
    out, seen = [], set()
    for x in xs:
        if not x:
            continue
        v = x.strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


class SectionBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    content_md: str


class JDGeneration(BaseModel):
    """
    JD 생성 결과(최종 산출물). 추가 키 불가.
    """

    model_config = ConfigDict(extra="forbid")
    title: str
    jd_markdown: str
    sections: Optional[List[SectionBlock]] = Field(default=None)
    meta: Optional[Dict[str, Any]] = Field(default=None)

    @model_validator(mode="after")
    def _clean(self) -> "JDGeneration":
        self.title = _norm_str(self.title) or ""
        self.jd_markdown = (self.jd_markdown or "").strip()
        # meta 정리(알려진 필드만 간단 정리)
        if self.meta:
            m = dict(self.meta)
            m["style_label"] = _norm_str(m.get("style_label"))
            m["tone_keywords"] = _norm_list(m.get("tone_keywords"))
            m["section_outline"] = _norm_list(m.get("section_outline"))
            self.meta = m
        return self
