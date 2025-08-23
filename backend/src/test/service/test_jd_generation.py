# tests/service/test_jd_generation.py

from unittest.mock import AsyncMock

import pytest

from domain.company_analysis.models import CompanyKnowledge, CompanyJDStyle
from service.jd_generation import analyze_company_knowledge, analyze_company_jd_style


@pytest.mark.asyncio
async def test_analyze_company_knowledge_valid():
    mock_llm = AsyncMock()
    mock_llm.invoke.return_value = {
        "introduction": "우리는 혁신적인 기업입니다.",
        "culture": "열린 커뮤니케이션을 지향합니다.",
        "requirements": {
            "competencies": ["책임감", "적극성"],
            "skills": ["Python", "SQL"],
        },
    }

    company_code = "comp123"
    job_code = "1000229"
    jds = ["[JD 1]", "[JD 2]"]

    result = await analyze_company_knowledge(
        company_code=company_code,
        job_code=job_code,
        jds=jds,
        llm=mock_llm,
    )

    assert isinstance(result, CompanyKnowledge)
    assert result.introduction == "우리는 혁신적인 기업입니다."
    assert result.requirements.skills == ["Python", "SQL"]
    mock_llm.invoke.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_company_jd_style_valid():
    mock_llm = AsyncMock()
    mock_llm.invoke.return_value = {
        "style_label": "스타트업-친근한",
        "tone_keywords": ["자유로운", "도전적인"],
        "section_outline": ["About Us", "Responsibilities", "Qualifications"],
        "example_jd_markdown": "### About Us\nWe are a startup...",
        "templates": {"About Us": "We are..."},
    }

    company_code = "comp999"
    job_code = "1000242"
    jds = ["[JD Sample]"]

    result = await analyze_company_jd_style(
        company_code=company_code,
        job_code=job_code,
        jds=jds,
        llm=mock_llm,
    )

    assert isinstance(result, CompanyJDStyle)
    assert result.style_label == "스타트업-친근한"
    assert result.templates["About Us"].startswith("We are")
    mock_llm.invoke.assert_called_once()
