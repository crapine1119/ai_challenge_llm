# src/api/routes/company_analysis.py
from fastapi import APIRouter, HTTPException

from api.schemas.company_analysis import (
    KnowledgeZeroShotRequest,
    KnowledgeZeroShotResponse,
    KnowledgeFewShotRequest,
    KnowledgeFewShotResponse,
    StyleOnlyRequest,
    StyleOnlyResponse,
    AnalyzeAllRequest,
    AnalyzeAllResponse,
)
from infrastructure.llm.factory import LLMFactory
from service.company_analysis import CompanyAnalysisService, GLOBAL_COMPANY

router = APIRouter(prefix="/company-analysis", tags=["company-analysis"])


def _make_service(req) -> CompanyAnalysisService:
    """
    provider/model/json_format 지정에 따라 LLM 클라이언트를 생성하고 Service에 주입.
    .env 기본값은 LLMFactory 내부에서 처리.
    """
    llm = LLMFactory.from_env(
        provider=req.provider,
        model=req.model,
        json_format=req.json_format,
    )
    return CompanyAnalysisService(llm=llm)


# ---------- Zero-shot ----------
@router.post("/knowledge/zero-shot", response_model=KnowledgeZeroShotResponse)
async def knowledge_zero_shot(req: KnowledgeZeroShotRequest):
    try:
        svc = _make_service(req)
        knowledge = await svc.extract_knowledge_zero_shot(
            job_code=req.job_code,
            language=req.language,
            save=req.save,
            json_format=req.json_format,
        )
        return KnowledgeZeroShotResponse(
            company_code=GLOBAL_COMPANY,
            job_code=req.job_code,
            knowledge=knowledge,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Few-shot ----------
@router.post("/knowledge/few-shot", response_model=KnowledgeFewShotResponse)
async def knowledge_few_shot(req: KnowledgeFewShotRequest):
    try:
        svc = _make_service(req)
        knowledge = await svc.extract_knowledge_few_shot(
            company_code=req.company_code,
            job_code=req.job_code,
            language=req.language,
            top_k=req.top_k,
            within_days=req.within_days,
            min_chars_per_doc=req.min_chars_per_doc,
            save=req.save,
            json_format=req.json_format,
        )
        return KnowledgeFewShotResponse(
            company_code=req.company_code,
            job_code=req.job_code,
            knowledge=knowledge,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Style ----------
@router.post("/style", response_model=StyleOnlyResponse)
async def extract_style(req: StyleOnlyRequest):
    try:
        svc = _make_service(req)
        style = await svc.extract_company_jd_style(
            company_code=req.company_code,
            job_code=req.job_code,
            language=req.language,
            top_k=req.top_k,
            within_days=req.within_days,
            min_chars_per_doc=req.min_chars_per_doc,
            save=req.save,
            json_format=req.json_format,
        )
        return StyleOnlyResponse(company_code=req.company_code, job_code=req.job_code, style=style)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Analyze All (few-shot + style) ----------
@router.post("/analyze-all", response_model=AnalyzeAllResponse)
async def analyze_all(req: AnalyzeAllRequest):
    try:
        svc = _make_service(req)
        result = await svc.analyze_all(
            company_code=req.company_code,
            job_code=req.job_code,
            language=req.language,
            save=req.save,
            json_format=req.json_format,
        )
        return AnalyzeAllResponse(
            company_code=req.company_code,
            job_code=req.job_code,
            knowledge=result["knowledge"],
            style=result["style"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
