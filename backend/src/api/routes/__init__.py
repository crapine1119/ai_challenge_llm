from fastapi import APIRouter

from api.routes.collect import router as collect_router
from api.routes.company_analysis import router as company_analysis_router
from api.routes.jd_generation import router as jd_router
from api.routes.styles import router as styles_router

api_router = APIRouter()
api_router.include_router(collect_router)
api_router.include_router(company_analysis_router)
api_router.include_router(jd_router)
api_router.include_router(styles_router)
