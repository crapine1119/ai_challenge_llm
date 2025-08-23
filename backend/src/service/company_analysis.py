import logging
from typing import Optional, Dict, Any, List

from domain.company_analysis.models import CompanyKnowledge, CompanyJDStyle
from infrastructure.db.database import get_session
from infrastructure.db.repository import (
    GeneratedInsightRepository,
    StyleSnapshotRepository,
    build_style_digest_markdown,
)
from infrastructure.db.repository import RawJDRepository
from infrastructure.llm.json_schemas import (
    COMPANY_KNOWLEDGE_JSON_SCHEMA,
    COMPANY_JD_STYLE_JSON_SCHEMA,
)
from infrastructure.llm.openai_client import OpenAIAsyncLLM
from infrastructure.prompt.manager import render_by_style, render_by_key_version

logger = logging.getLogger(__name__)

GLOBAL_COMPANY = "__global__"  # ✅ Zero-shot 용 글로벌 company code

JOB_CODE_NAME = {
    "1000201": "인사담당자",
    "1000242": "AI/ML 엔지니어",
    "1000229": "백엔드개발자",
    "1000230": "프론트엔드개발자",
    "1000187": "마케팅기획",
    "1000210": "재무담당자",
}

DEFAULT_EXTRACT_KEY = "company.analysis.job_competency_few_shot"
DEFAULT_ZERO_SHOT_KEY = "company.analysis.job_competency_zero_shot"
DEFAULT_STYLE_KEY = "company.analysis.jd_style"
DEFAULT_VERSION = "v1"


def _prune_to_schema(data: Any, schema: Dict[str, Any]) -> Any:
    """
    LLM 응답(data)을 JSON Schema(schema)에 맞춰 재귀적으로 가지치기.

    - object:
        * properties에 정의된 키는 해당 서브스키마로 prune
        * additionalProperties:
            - False (또는 미지정) → 미정의 키 제거
            - True → 미정의 키도 그대로 허용
            - dict(스키마) → 미정의 키의 값을 그 스키마로 재귀 prune
    - array : items 스키마 기준으로 각 요소를 prune
    - primitive: 그대로 유지
    - anyOf/oneOf: 첫 유효 스키마 또는 첫 항목 적용, allOf: 순차 적용
    - type이 ["string","null"] 같은 리스트일 때: data 타입에 맞는 것을 우선 선택
    """
    if schema is None:
        return data

    # 조합 스키마
    for comb in ("allOf", "oneOf", "anyOf"):
        subs = schema.get(comb)
        if isinstance(subs, list) and subs:
            if comb == "allOf":
                out = data
                for sub in subs:
                    out = _prune_to_schema(out, sub)
                return out
            # oneOf/anyOf: 가장 먼저 매칭되는 것을 사용 (간단화)
            return _prune_to_schema(data, subs[0])

    # type이 리스트면 data 타입에 가장 어울리는 것을 고르기
    stype = schema.get("type")
    if isinstance(stype, list):
        # 간단 매칭
        py2js = {
            dict: "object",
            list: "array",
            str: "string",
            bool: "boolean",
            int: "number",
            float: "number",
            type(None): "null",
        }
        want = py2js.get(type(data))
        if want in stype:
            stype = want
        else:
            stype = stype[0]  # fallback
    # 이하 stype은 문자열 또는 None

    # object
    if stype == "object" and isinstance(data, dict):
        props = schema.get("properties") or {}
        addl = schema.get("additionalProperties", False)  # 기본 False 취급
        out: Dict[str, Any] = {}

        # 1) 정의된 키 먼저 처리
        for k, sub in props.items():
            if k in data:
                out[k] = _prune_to_schema(data[k], sub)

        # 2) 미정의 키 처리: additionalProperties 정책 반영
        for k, v in data.items():
            if k in props:
                continue
            if addl is True:
                # 전부 허용
                out[k] = v
            elif isinstance(addl, dict):
                # 스키마로 재귀 prune (맵 타입 지원)
                out[k] = _prune_to_schema(v, addl)
            else:
                # False 또는 기타 → drop
                pass

        return out

        # object인데 data가 dict가 아니면 그대로 반환(혹은 {}로 강제하고 싶으면 그 정책 적용)
    # array
    if stype == "array" and isinstance(data, list):
        item_schema = schema.get("items")
        if item_schema:
            return [_prune_to_schema(x, item_schema) for x in data]
        return data

    # primitive/unknown → 그대로
    return data


def _prompt_meta_from_rendered(rendered: Dict[str, Any]) -> Dict[str, Any]:
    """render_by_* 결과에서 prompt 메타 추출 (DB 추적용)."""
    return {
        "id": rendered.get("prompt_id"),
        "key": rendered.get("key"),
        "version": rendered.get("version"),
        "language": rendered.get("language"),
    }


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
    async def extract_knowledge_zero_shot(
        self,
        *,
        job_code: str,
        language: Optional[str] = "ko",
        save: bool = True,
        json_format: bool = True,
    ) -> CompanyKnowledge:
        """등록된 JD 없이 직무만으로 제로샷 지식 생성"""
        job_name = JOB_CODE_NAME.get(job_code, job_code)
        rendered = await self._render_zero_shot(GLOBAL_COMPANY, job_name, language)

        logger.info("\tZero-shot knowledge: begin")
        result = await self._invoke_json(rendered, json_schema=COMPANY_KNOWLEDGE_JSON_SCHEMA, json_format=json_format)
        model = CompanyKnowledge.model_validate(result)
        if save:
            await self._save_company_knowledge(GLOBAL_COMPANY, job_code, model, rendered=rendered)
        logger.info("\tZero-shot knowledge: done")
        return model

    async def extract_knowledge_few_shot(
        self,
        *,
        company_code: str,
        job_code: str,
        language: Optional[str] = "ko",
        top_k: int = 3,
        within_days: Optional[int] = None,
        min_chars_per_doc: int = 200,
        save: bool = True,
        json_format: bool = True,
    ) -> CompanyKnowledge:
        """회사×직무의 최신 JD 샘플을 이용한 지식 생성 (문서 없으면 에러)"""
        job_name = JOB_CODE_NAME.get(job_code, job_code)
        jd_samples = await self._load_recent_jds(
            company_code=company_code,
            job_code=job_code,
            limit=top_k,
            within_days=within_days,
            min_chars=min_chars_per_doc,
        )
        if not jd_samples:
            raise ValueError("Few-shot을 위한 JD 샘플이 없습니다. 먼저 크롤링 또는 기간/조건을 확인하세요.")
        rendered = await self._render_extract(company_code, job_name, jd_samples, None, language)
        logger.info("\tFew-shot knowledge: begin")
        result = await self._invoke_json(rendered, json_schema=COMPANY_KNOWLEDGE_JSON_SCHEMA, json_format=json_format)
        model = CompanyKnowledge.model_validate(result)
        if save:
            await self._save_company_knowledge(company_code, job_code, model, rendered=rendered)
        logger.info("\tFew-shot knowledge: done")
        return model

    async def extract_company_jd_style(
        self,
        *,
        company_code: str,
        job_code: str,
        language: Optional[str] = "ko",
        top_k: int = 3,
        within_days: Optional[int] = None,
        min_chars_per_doc: int = 200,
        save: bool = True,
        json_format: bool = False,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> CompanyJDStyle:
        """
        회사 JD 스타일(톤/섹션/템플릿) 추출 → generated_styles 스냅샷 저장
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
            logger.warning("No JD docs for style; proceeding with empty concatenation.")

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

        logger.info("\tStyle extraction: begin")
        result = await self._invoke_json(rendered, json_schema=COMPANY_JD_STYLE_JSON_SCHEMA, json_format=json_format)
        model = CompanyJDStyle.model_validate(result)

        if save:
            prompt_meta = _prompt_meta_from_rendered(rendered)
            await self._save_company_style(
                company_code=company_code,
                job_code=job_code,
                model=model,
                provider=provider,
                model_name=model_name,
                prompt_meta=prompt_meta,
            )
        logger.info("\tStyle extraction: done")
        return model

        # ---------- Public: Analyze (few-shot + style) ----------

    async def analyze_all(
        self,
        *,
        company_code: str,
        job_code: str,
        language: Optional[str] = "ko",
        save: bool = True,
        json_format: bool = False,
    ) -> Dict[str, Any]:
        """
        한 번에 실행:
          1) Few-shot Knowledge (회사×직무 JD 기반)
          2) Style (회사×직무)
        """
        knowledge = await self.extract_knowledge_few_shot(
            company_code=company_code,
            job_code=job_code,
            language=language,
            save=save,
            json_format=json_format,
        )
        style = await self.extract_company_jd_style(
            company_code=company_code,
            job_code=job_code,
            language=language,
            save=save,
            json_format=json_format,
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

    async def _invoke_json(
        self,
        rendered: Dict[str, Any],
        json_schema: Optional[Dict[str, Any]] = None,
        *,
        json_format: bool = False,
    ) -> Dict[str, Any]:
        system = rendered.get("system")
        user_text = rendered["user_text"]
        params = rendered.get("params") or {}

        # 프롬프트가 준 key로 스키마 해석(명시 인자 우선)
        from infrastructure.llm.json_schemas import resolve_json_schema

        schema = json_schema or resolve_json_schema(rendered.get("json_schema_key"))
        if not schema:
            raise ValueError(f"JSON schema not resolved (key={rendered.get('json_schema_key')})")

        result = await self.llm.invoke(
            prompt=user_text,
            system=system,
            json_schema=schema,
            json_format=json_format,  # OpenAI: response_format, Gemini: 프롬프트 강제 + 파싱
            **params,
        )
        assert isinstance(result, dict), "LLM must return JSON for structured prompt"

        # ✅ 여기서 반드시 스키마 프루닝
        pruned = _prune_to_schema(result, schema)

        # pruned가 dict가 아니면 빈 dict로 폴백 (Pydantic이 기본값 넣을 수 있게)
        return pruned if isinstance(pruned, dict) else {}

    def _concat(self, docs: List[str], max_docs: int = 5, max_chars: int = 18000) -> str:
        # 과도한 토큰 폭주 방지: 단순 앞에서 자르기
        joined = "\n\n---\n\n".join(docs[:max_docs])
        if len(joined) > max_chars:
            joined = f"{joined[:max_chars]}..."

        return joined

    async def _save_company_knowledge(
        self,
        company_code: str,
        job_code: str,
        model: CompanyKnowledge,
        rendered: Dict[str, Any],
    ) -> int:
        async for session in get_session():
            repo = GeneratedInsightRepository(session)
            insight_id = await repo.add_company_knowledge(
                company_code=company_code,
                job_code=job_code,
                payload_json=model.model_dump(),
                prompt_id=rendered.get("prompt_id"),
                prompt_key=rendered.get("key"),
                prompt_version=rendered.get("version"),
                prompt_language=rendered.get("language"),
            )
            return insight_id
        return -1

    async def _save_company_style(
        self,
        company_code: str,
        job_code: str,
        model: CompanyJDStyle,
        *,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        prompt_meta: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        스타일은 generated_styles 스냅샷으로 저장.
        """
        async for session in get_session():
            repo = StyleSnapshotRepository(session)
            digest = build_style_digest_markdown(
                model.model_dump(),
                company_code=company_code,
                job_code=job_code,
            )
            style_id = await repo.add_style_snapshot(
                company_code=company_code,
                job_code=job_code,
                payload=model.model_dump(),
                digest_md=digest,
                prompt_meta=prompt_meta or {},
                provider=provider,
                model=model_name,
            )
            return style_id
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
