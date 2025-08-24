# src/service/jd_generation.py
import json
import re
from typing import Literal, AsyncIterator
from typing import Optional

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
        job_code: str,
        source: Literal["generated", "default"] = "default",
        default_style_name: Optional[str] = None,
    ) -> CompanyJDStyle:
        async for session in get_session():
            if source == "generated":
                snap = await StyleSnapshotRepository(session).latest_for(company_code=company, job_code=job_code)
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

    async def _prepare_generation_inputs(
        self, company, default_style_name, jd_style, job, job_code, knowledge, language, style_source
    ):
        style = jd_style or await self._resolve_style(
            company=company,
            job_code=job_code,
            source=style_source,
            default_style_name=default_style_name,
        )
        prompt_input = PromptTemplateInput(
            prompt_key="jd.generation",
            prompt_version="v1",
            language=language,
            variables={
                "company_name": company,
                "job_name": job,
                "company_knowledge": json.dumps(knowledge.model_dump(mode="json"), ensure_ascii=False, indent=2),
                "jd_style": json.dumps(style.model_dump(mode="json"), ensure_ascii=False, indent=2),
            },
        )
        rendered = await self.prompt_manager.render_chat(prompt_input)
        return rendered

    async def generate_jd_markdown(
        self,
        *,
        company: str,
        job: str,
        job_code: str,
        knowledge: CompanyKnowledge,
        jd_style: Optional[CompanyJDStyle] = None,
        # ↓ 선택 정책: 생성 스냅샷/기본 프리셋
        style_source: Literal["generated", "default"] = "default",
        default_style_name: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = "ko",  # ✅ 추가
    ) -> str:
        """
        CompanyKnowledge + (기본/생성 스타일) 기반 최종 JD 생성 (markdown)
        """
        rendered = await self._prepare_generation_inputs(
            company, default_style_name, jd_style, job, job_code, knowledge, language, style_source
        )
        response = await self.llm.invoke(
            prompt=rendered["user_text"],
            system=rendered.get("system"),
            model=model,
        )
        if not isinstance(response, str):
            raise ValueError("JD 생성 응답이 문자열이 아닙니다.")

        if "```" in response:
            response = re.sub(r"```markdown", "", response)
            response = re.sub(r"```json", "", response)
            response = re.sub(r"```", "", response)

        return response.strip()

    # ✅ 스트리밍 버전
    async def generate_jd_markdown_stream(
        self,
        *,
        company: str,
        job: str,
        job_code: Optional[str] = None,
        knowledge: CompanyKnowledge,
        jd_style: Optional[CompanyJDStyle] = None,
        style_source: Literal["generated", "default"] = "generated",
        default_style_name: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = "ko",
    ) -> AsyncIterator[str]:
        """
        LLM 스트리밍을 그대로 흘려보냄(순수 텍스트 청크). 라우터에서 누적·저장 처리.
        """
        rendered = await self._prepare_generation_inputs(
            company, default_style_name, jd_style, job, job_code, knowledge, language, style_source
        )
        # LLMClient.stream 은 텍스트 델타를 yield
        async for chunk in self.llm.stream(
            prompt=rendered["user_text"],
            system=rendered.get("system"),
            model=model,
        ):
            yield chunk
