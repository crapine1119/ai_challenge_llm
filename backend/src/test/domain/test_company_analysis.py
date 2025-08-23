# tests/domain/test_company_analysis.py

import pytest
from pydantic import ValidationError

from domain.company_analysis.models import (
    CompanyKnowledge,
    CompanyJDStyle,
    RequirementsBlock,
    ExtrasBlock,
)


def test_requirements_block_defaults():
    block = RequirementsBlock()
    assert block.competencies == []
    assert block.skills == []
    assert block.project_experience == []


def test_extras_block_defaults():
    block = ExtrasBlock()
    assert block.benefits == []
    assert block.locations == []
    assert block.hiring_process == []


def test_company_knowledge_minimal():
    ck = CompanyKnowledge()
    assert isinstance(ck.requirements, RequirementsBlock)
    assert isinstance(ck.preferred, RequirementsBlock)
    assert isinstance(ck.extras, ExtrasBlock)


def test_company_knowledge_with_data():
    ck = CompanyKnowledge(
        introduction="우리는 혁신적인 기술을 추구합니다.",
        culture="자유로운 소통과 협업을 중시합니다.",
        values=["고객 중심", "기술 우수성"],
        ideal_traits=["문제 해결력", "팀워크"],
        requirements=RequirementsBlock(competencies=["책임감"], skills=["Python"]),
        preferred=RequirementsBlock(skills=["Docker"]),
        extras=ExtrasBlock(benefits=["유연근무제"]),
    )
    assert ck.requirements.skills == ["Python"]
    assert ck.preferred.skills == ["Docker"]
    assert ck.extras.benefits == ["유연근무제"]


def test_company_jd_style_required_fields():
    jd_style = CompanyJDStyle(
        style_label="회사-공식적-간결",
        tone_keywords=["정중한", "간결한"],
        section_outline=["회사 소개", "주요 업무", "자격 요건"],
        example_jd_markdown="### 회사 소개\n혁신적인 기업입니다.",
        templates={"회사 소개": "우리 회사는 ..."},
    )
    assert jd_style.style_label == "회사-공식적-간결"


def test_company_jd_style_validation_error():
    with pytest.raises(ValidationError):
        # style_label 누락
        CompanyJDStyle(
            tone_keywords=["정중한"],
            section_outline=[],
            example_jd_markdown="## 예시 JD",
        )


def test_company_knowledge_json_schema_enforced():
    schema = CompanyKnowledge.model_json_schema()
    assert schema["type"] == "object"
    assert "introduction" in schema["properties"]
