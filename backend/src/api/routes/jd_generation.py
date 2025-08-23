from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import db_session
from api.schemas.jd_generation import JDGenerateRequest, JDGenerateResponse
from domain.company_analysis.models import CompanyKnowledge, CompanyJDStyle
from infrastructure.llm.factory import make_llm
from infrastructure.prompt.manager import PromptManager
from service.jd_generation import JDGenerationService

router = APIRouter(prefix="/jd", tags=["jd"])


async def _load_latest_insight(
    session: AsyncSession, *, company_code: str, job_code: str, type_name: str
) -> Optional[Dict[str, Any]]:
    q = text(
        """
        SELECT analysis_json
        FROM generated_insights
        WHERE company_code = :c
          AND job_code = :j
          AND analysis_json->>'type' = :t
        ORDER BY generated_date DESC
        LIMIT 1
        """
    )
    res = await session.execute(q, {"c": company_code, "j": job_code, "t": type_name})
    row = res.first()
    return None if not row else row[0]


async def _load_job_name(session: AsyncSession, job_code: str) -> Optional[str]:
    q = text("SELECT job_name FROM job_code_map WHERE job_code = :jc LIMIT 1")
    res = await session.execute(q, {"jc": job_code})
    row = res.first()
    return None if not row else str(row[0])


@router.post("/generate", response_model=JDGenerateResponse)
async def generate_jd(
    body: JDGenerateRequest,
    session: AsyncSession = Depends(db_session),
):
    # LLM 선택 (없으면 .env 기본)
    llm = make_llm(provider=body.provider, model=body.model)
    pm = PromptManager()
    svc = JDGenerationService(llm=llm, prompt_manager=pm)

    knowledge: Optional[CompanyKnowledge] = None
    style: Optional[CompanyJDStyle] = None
    company_code: Optional[str] = body.company_code
    job_code: Optional[str] = body.job_code

    if body.knowledge and body.jd_style:
        try:
            knowledge = CompanyKnowledge.model_validate(body.knowledge)
            style = CompanyJDStyle.model_validate(body.jd_style)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid knowledge/style payload: {e}")
    elif body.company_code and body.job_code:
        kn = await _load_latest_insight(
            session, company_code=body.company_code, job_code=body.job_code, type_name="company_knowledge_v1"
        )
        st = await _load_latest_insight(
            session, company_code=body.company_code, job_code=body.job_code, type_name="company_jd_style_v1"
        )
        if not kn or not st:
            raise HTTPException(status_code=404, detail="No saved knowledge/style for given company_code/job_code")
        try:
            knowledge = CompanyKnowledge.model_validate(kn.get("payload") or {})
            style = CompanyJDStyle.model_validate(st.get("payload") or {})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Saved insight payload invalid: {e}")

        company_code = company_code or body.company_code
        job_code = job_code or (await _load_job_name(session, body.job_code)) or body.job_code
    else:
        raise HTTPException(
            status_code=400, detail="Provide either (knowledge & jd_style) or (company_code & job_code)."
        )

    company_code = company_code or "회사"
    job_code = job_code or "직무"

    try:
        markdown = await svc.generate_jd_markdown(
            company=company_code,
            job=job_code,
            knowledge=knowledge,  # type: ignore[arg-type]
            jd_style=style,  # type: ignore[arg-type]
            model=body.model,  # per-request 모델 사용 (없으면 svc 내부 기본)
        )
    except AssertionError as e:
        raise HTTPException(status_code=502, detail=f"LLM assertion failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return JDGenerateResponse(company_code=company_code, job_code=job_code, markdown=markdown)
