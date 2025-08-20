import logging
from typing import Optional, Dict, Any, List

from domain.company_analysis.models import CompanyKnowledge, CompanyJDStyle
from infrastructure.db.database import get_session
from infrastructure.db.repository import GeneratedInsightRepository
from infrastructure.db.repository import RawJDRepository
from infrastructure.llm.json_schemas import COMPANY_KNOWLEDGE_JSON_SCHEMA, COMPANY_JD_STYLE_JSON_SCHEMA
from infrastructure.llm.openai_client import OpenAIAsyncLLM
from infrastructure.prompt.manager import render_by_style, render_by_key_version

logger = logging.getLogger(__name__)

JOB_CODE_NAME = {
    "1000201": "인사담당자",
    "1000242": "AI/ML 엔지니어",
    "1000229": "백엔드개발자",
    "1000230": "프론트엔드개발자",
    "1000187": "마케팅기획",
    "1000210": "재무담당자",
}

DEFAULT_EXTRACT_KEY = "company.analysis.knowledge"
DEFAULT_ZERO_SHOT_KEY = "company.analysis.job_competency_zero_shot"
DEFAULT_STYLE_KEY = "company.analysis.jd_style"
DEFAULT_VERSION = "v1"


class CompanyAnalysisService:
    """
    회사/직무 기반으로
    1) JD들로부터 지식/역량 추출 (있으면 추출, 없으면 제로샷)
    2) 회사 JD 스타일 추출
    결과는 generated_insights에 저장
    """

    def __init__(self, llm: Optional[OpenAIAsyncLLM] = None):
        self.llm = llm or OpenAIAsyncLLM()

    # ---------- Public APIs ----------

    async def extract_knowledge(
        self,
        *,
        company_code: str,
        job_code: str,
        style_name: Optional[str] = None,
        language: Optional[str] = "ko",
        top_k: int = 30,
        within_days: Optional[int] = 365,
        min_chars_per_doc: int = 200,
        save: bool = True,
    ) -> CompanyKnowledge:
        """
        JD가 있으면: 추출 프롬프트 → LLM(JSON)
        JD가 없으면: 제로샷 프롬프트 → LLM(JSON)
        """
        job_name = JOB_CODE_NAME.get(job_code, job_code)

        jd_samples = await self._load_recent_jds(
            company_code=company_code,
            job_code=job_code,
            limit=top_k,
            within_days=within_days,
            min_chars=min_chars_per_doc,
        )
        has_docs = len(jd_samples) > 0

        if has_docs:
            rendered = await self._render_extract(company_code, job_name, jd_samples, style_name, language)
            json_schema = COMPANY_KNOWLEDGE_JSON_SCHEMA
        else:
            rendered = await self._render_zero_shot(company_code, job_name, language)
            json_schema = COMPANY_KNOWLEDGE_JSON_SCHEMA

        result = await self._invoke_json(rendered, json_schema)
        model = CompanyKnowledge.model_validate(result)

        if save:
            await self._save_company_knowledge(company_code, job_code, model)

        return model

    async def extract_company_jd_style(
        self,
        *,
        company_code: str,
        job_code: str,
        language: Optional[str] = "ko",
        top_k: int = 20,
        within_days: Optional[int] = 365,
        min_chars_per_doc: int = 200,
        save: bool = True,
    ) -> CompanyJDStyle:
        """
        회사 JD 스타일(톤/섹션/예시 템플릿) 추출
        """
        job_name = JOB_CODE_NAME.get(job_code, job_code)
        jd_samples = await self._load_recent_jds(
            company_code=company_code,
            job_code=job_code,
            limit=top_k,
            within_days=within_days,
            min_chars=min_chars_per_doc,
        )

        concatenated = self._concat(jd_samples)
        if not concatenated:
            # 문서가 없으면 스타일은 제로샷으로 구성하기 어렵지만,
            # 최소한 직무의 일반적 섹션으로 예시를 생성하도록 빈 문자열 전달
            logger.info("No JD docs for style; proceeding with empty concatenation.")

        rendered = await render_by_key_version(
            key=DEFAULT_STYLE_KEY,
            version=DEFAULT_VERSION,
            language=language,
            context={
                "company_name": company_code,
                "job_name": job_name,
                "concatenated_jds": concatenated or "자료 없음: 일반적 JD 스타일을 생성해라.",
            },
        )
        result = await self._invoke_json(rendered, COMPANY_JD_STYLE_JSON_SCHEMA)
        model = CompanyJDStyle.model_validate(result)

        if save:
            await self._save_company_style(company_code, job_code, model)

        return model

    async def analyze_company_jd(
        self,
        *,
        company_code: str,
        job_code: str,
        style_name: Optional[str] = None,
        language: Optional[str] = "ko",
        save: bool = True,
    ) -> Dict[str, Any]:
        """
        원샷 분석: 지식/역량 + 스타일을 한 번에 수행
        """
        knowledge = await self.extract_knowledge(
            company_code=company_code,
            job_code=job_code,
            style_name=style_name,
            language=language,
            save=save,
        )
        style = await self.extract_company_jd_style(
            company_code=company_code,
            job_code=job_code,
            language=language,
            save=save,
        )
        return {
            "company_code": company_code,
            "job_code": job_code,
            "knowledge": knowledge.model_dump(),
            "style": style.model_dump(),
        }

    # ---------- Private helpers ----------

    async def _load_recent_jds(
        self,
        *,
        company_code: str,
        job_code: str,
        limit: int,
        within_days: Optional[int],
        min_chars: int,
    ) -> List[str]:
        texts: List[str] = []
        async for session in get_session():
            repo = RawJDRepository(session)
            rows = await repo.fetch_texts_for_company_job(
                company_code=company_code, job_code=job_code, limit=limit, within_days=within_days
            )
            for _jd_id, _title, txt in rows:
                if txt and len(txt.strip()) >= min_chars:
                    texts.append(txt.strip())
        return texts

    async def _render_extract(
        self,
        company_code: str,
        job_name: str,
        jd_samples: List[str],
        style_name: Optional[str],
        language: Optional[str],
    ) -> Dict[str, Any]:
        concatenated = self._concat(jd_samples)
        # 스타일 매핑이 있으면 우선 사용, 없으면 기본 키 사용
        rendered = await render_by_style(
            style_name=style_name,
            fallback_key=DEFAULT_EXTRACT_KEY,
            fallback_ver=DEFAULT_VERSION,
            language=language,
            context={
                "company_name": company_code,
                "job_name": job_name,
                "concatenated_jds": concatenated,
            },
        )
        return rendered

    async def _render_zero_shot(
        self,
        company_code: str,
        job_name: str,
        language: Optional[str],
    ) -> Dict[str, Any]:
        rendered = await render_by_key_version(
            key=DEFAULT_ZERO_SHOT_KEY,
            version=DEFAULT_VERSION,
            language=language,
            context={
                "company_name": company_code,
                "job_name": job_name,
            },
        )
        return rendered

    async def _invoke_json(self, rendered: Dict[str, Any], json_schema: Dict[str, Any]) -> Dict[str, Any]:
        system = rendered.get("system")
        user_text = rendered["user_text"]
        params = rendered.get("params") or {}
        result = await self.llm.invoke(prompt=user_text, system=system, json_schema=json_schema, **params)
        assert isinstance(result, dict), "LLM must return JSON for structured prompt"
        return result

    def _concat(self, docs: List[str], max_chars: int = 18000) -> str:
        # 과도한 토큰 폭주 방지: 단순 앞에서 자르기
        joined = "\n\n---\n\n".join(docs)
        return joined[:max_chars]

    async def _save_company_knowledge(self, company_code: str, job_code: str, model: CompanyKnowledge) -> int:
        async for session in get_session():
            repo = GeneratedInsightRepository(session)
            insight_id = await repo.add_company_knowledge(
                company_code=company_code,
                job_code=job_code,
                payload_json=model.model_dump(),
            )
            return insight_id
        return -1

    async def _save_company_style(self, company_code: str, job_code: str, model: CompanyJDStyle) -> int:
        async for session in get_session():
            repo = GeneratedInsightRepository(session)
            insight_id = await repo.add_company_style(
                company_code=company_code,
                job_code=job_code,
                payload_json=model.model_dump(),
            )
            return insight_id
        return -1


# Pseudo Code
# class CompanyAnalysisService:
#     def extract_knowledge(self, document):
#         """
#         :param document:
#         :return:
#         """
#         """
#         Request: 회사 코드, 직무 코드
#
#         # 직무별 역량 추출
#         await extract_job_competency(Request) -> Response:
#             + infra/db (JD 리스트 조회) >>> list[JD: str]
#             + infra/llm (LLM 객체 호출)
#             + async domain/job_competency (생성)
#
#         # 정보 없이 기술 역량만 생성
#         await generate_job_competency(Request) -> Response:
#             + infra/llm (LLM 객체 호출)
#             + async domain/job_competency (생성)
#
#         Response:
#             기본:
#                 소개
#                 문화
#                 인재상
#             자격요건:
#                 역량 / 기술 / 프로젝트 경험
#             우대사항:
#                 역량 / 기술 / 프로젝트 경험
#             기타:
#                 복지
#                 근무지
#                 전형
#
#         이렇게 관리해야할듯함: template or dict
#         {
#             "introduction": ...
#             "skills": ...
#         }
#
#
#         # 직무별 역량 저장
#         save_llm_output(Response) -> None:
#             + infra/db
#
#         """
#
#     def extract_company_jd_style(self) -> str:
#         """
#         JD를 분석해서 회사의 JD 스타일을 추출하면 좋을 것 같음
#         결과는 형태만 있는 예시 JD 느낌
#
#         > 이러면 나중에 스타일 고를 때 1) 기본, 2) 회사 스타일, 3) 기술적, 4) 트랜디 (노션?)가 가능할 듯
#         """
#
#     def analyze_company_jd(self):
#         """
#         :return:
#
#         위 두개가 각각 api로 만들고 front에서 조절해서 호출할건지,
#         아니면 합쳐서 하나로 만들고 호출할건지 정해야함
#         """
