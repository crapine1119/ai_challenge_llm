# src/service/jd_generation.py

from typing import Optional, Literal

from domain.company_analysis.models import CompanyKnowledge, CompanyJDStyle
from infrastructure.db.database import get_session
from infrastructure.db.repository import DefaultStyleRepository, StyleSnapshotRepository
from infrastructure.llm.interface import LLMClient
from infrastructure.prompt.manager import PromptManager
from infrastructure.prompt.schema import PromptTemplateInput


class JDGenerationService:
    def __init__(self, llm: LLMClient, prompt_manager: PromptManager):
        self.llm = llm
        self.prompt_manager = prompt_manager

    async def _resolve_style(
        self,
        *,
        company: str,
        job: str,
        source: Literal["generated", "default"] = "generated",
        default_style_name: Optional[str] = None,
    ) -> CompanyJDStyle:
        async for session in get_session():
            if source == "generated":
                snap = await StyleSnapshotRepository(session).latest_for(company_code=company, job_code=job)
                if snap:
                    payload = {
                        "style_label": snap.style_label or "",
                        "tone_keywords": snap.tone_keywords or [],
                        "section_outline": snap.section_outline or [],
                        "templates": snap.templates or {},
                        "example_jd_markdown": "",  # 유지 필드 (빈 문자열)
                    }
                    return CompanyJDStyle.model_validate(payload)
                # 없으면 default로 폴백
            # default
            name = default_style_name or "일반적"
            preset = await DefaultStyleRepository(session).get_preset(style_name=name)
            if not preset:
                # 마지막 폴백: 빈 스타일
                return CompanyJDStyle(
                    style_label=name,
                    tone_keywords=[],
                    section_outline=[],
                    example_jd_markdown="",
                    templates={},
                )
            # preset에 example_jd_markdown이 없어도 모델이 기본값 처리
            return preset

    async def generate_jd_markdown(
        self,
        *,
        company: str,
        job: str,
        knowledge: CompanyKnowledge,
        jd_style: Optional[CompanyJDStyle] = None,
        # ↓ 선택 정책: 생성 스냅샷/기본 프리셋
        style_source: Literal["generated", "default"] = "generated",
        default_style_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        CompanyKnowledge + (기본/생성 스타일) 기반 최종 JD 생성 (markdown)
        """
        style = jd_style or await self._resolve_style(
            company=company, job=job, source=style_source, default_style_name=default_style_name
        )

        prompt_input = PromptTemplateInput(
            prompt_key="jd.authoring.full",
            prompt_version="v1",
            language="ko",
            variables={
                "company_name": company,
                "job_name": job,
                "company_knowledge": knowledge.model_dump(mode="json"),
                "jd_style": style.model_dump(mode="json"),
            },
        )
        rendered = await self.prompt_manager.render_chat(prompt_input)
        response = await self.llm.invoke(
            prompt=rendered["prompt"],
            system=rendered.get("system_prompt"),
            model=model,
        )
        if not isinstance(response, str):
            raise ValueError("JD 생성 응답이 문자열이 아닙니다.")
        return response.strip()
