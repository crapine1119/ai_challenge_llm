from fastapi import APIRouter

from api.routes.catalog import router as catalog_router
from api.routes.collect import router as collect_router
from api.routes.company_analysis import router as company_analysis_router
from api.routes.guardrail import router as guardrail_router
from api.routes.jd_generation import router as jd_router
from api.routes.llm_queue import router as llm_queue_router
from api.routes.styles import router as styles_router

api_router = APIRouter()
api_router.include_router(collect_router)
api_router.include_router(company_analysis_router)
api_router.include_router(jd_router)
api_router.include_router(styles_router)
api_router.include_router(llm_queue_router)
api_router.include_router(guardrail_router)
api_router.include_router(catalog_router)  # ✅ 추가
