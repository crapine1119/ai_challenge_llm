# src/api/routes/catalog.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import db_session
from api.schemas.catalog import CompanyListResponse, JobListResponse, JobItem
from infrastructure.db.repository import CatalogRepository

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/companies/collected", response_model=CompanyListResponse)
async def get_collected_companies(session: AsyncSession = Depends(db_session)):
    repo = CatalogRepository(session)
    companies = await repo.distinct_companies()
    return CompanyListResponse(companies=companies)


@router.get("/jobs/collected", response_model=JobListResponse)
async def get_collected_jobs_by_company(
    company_code: str = Query(..., min_length=1),
    session: AsyncSession = Depends(db_session),
):
    repo = CatalogRepository(session)
    rows = await repo.distinct_jobs_for_company(company_code)
    items = [JobItem(code=code, name=name) for code, name in rows]
    return JobListResponse(company_code=company_code, jobs=items)
