from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func, desc

from api.schemas.styles import (
    StylePresetListResponse,
    StylePresetResponse,
    StylePresetItem,
    GeneratedStyleLatestResponse,
    GeneratedStyleListResponse,
    GeneratedStyleItem,
)
from domain.company_analysis.models import CompanyJDStyle
from infrastructure.db.database import get_session
from infrastructure.db.models import JDStyle, GeneratedStyle

router = APIRouter(prefix="/styles", tags=["styles"])


# ----------------------------
# 프리셋: 목록/단건
# ----------------------------
@router.get("/presets", response_model=StylePresetListResponse)
async def list_presets(only_active: bool = Query(True, description="활성 프리셋만")):
    async for session in get_session():
        q = select(JDStyle)
        if only_active:
            q = q.where(JDStyle.is_active.is_(True))
        q = q.order_by(JDStyle.style_name.asc())

        rows: List[JDStyle] = (await session.execute(q)).scalars().all()

        items: List[StylePresetItem] = []
        for r in rows:
            payload = r.payload_json or {}
            # payload_json → CompanyJDStyle
            cjds = CompanyJDStyle.model_validate(
                {
                    "style_label": payload.get("style_label") or r.style_name,
                    "tone_keywords": payload.get("tone_keywords") or [],
                    "section_outline": payload.get("section_outline") or [],
                    "templates": payload.get("templates") or {},
                    "example_jd_markdown": payload.get("example_jd_markdown") or "",
                }
            )
            items.append(StylePresetItem(style_name=r.style_name, is_active=bool(r.is_active), style=cjds))

        return StylePresetListResponse(items=items)


@router.get("/presets/{style_name}", response_model=StylePresetResponse)
async def get_preset(style_name: str):
    async for session in get_session():
        q = select(JDStyle).where(JDStyle.style_name == style_name).limit(1)
        row: Optional[JDStyle] = (await session.execute(q)).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="style preset not found")

        payload = row.payload_json or {}
        cjds = CompanyJDStyle.model_validate(
            {
                "style_label": payload.get("style_label") or row.style_name,
                "tone_keywords": payload.get("tone_keywords") or [],
                "section_outline": payload.get("section_outline") or [],
                "templates": payload.get("templates") or {},
                "example_jd_markdown": payload.get("example_jd_markdown") or "",
            }
        )
        return StylePresetResponse(style_name=row.style_name, is_active=bool(row.is_active), style=cjds)


# ----------------------------
# 생성 스냅샷: 최신/목록
# ----------------------------
@router.get("/generated/latest", response_model=GeneratedStyleLatestResponse)
async def get_latest_generated_style(company_code: str, job_code: str):
    async for session in get_session():
        q = (
            select(GeneratedStyle)
            .where(
                GeneratedStyle.company_code == company_code,
                GeneratedStyle.job_code == job_code,
            )
            .order_by(desc(GeneratedStyle.created_at))
            .limit(1)
        )
        row: Optional[GeneratedStyle] = (await session.execute(q)).scalars().first()

        if not row:
            return GeneratedStyleLatestResponse(company_code=company_code, job_code=job_code, latest=None)

        cjds = CompanyJDStyle.model_validate(
            {
                "style_label": row.style_label or "",
                "tone_keywords": row.tone_keywords or [],
                "section_outline": row.section_outline or [],
                "templates": row.templates or {},
                "example_jd_markdown": "",
            }
        )
        item = GeneratedStyleItem(
            id=row.id,
            company_code=row.company_code,
            job_code=row.job_code,
            created_at=row.created_at,
            style=cjds,
        )
        return GeneratedStyleLatestResponse(company_code=company_code, job_code=job_code, latest=item)


@router.get("/generated", response_model=GeneratedStyleListResponse)
async def list_generated_styles(
    company_code: Optional[str] = None,
    job_code: Optional[str] = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    async for session in get_session():
        base = select(GeneratedStyle)
        cnt = select(func.count(GeneratedStyle.id))

        if company_code:
            base = base.where(GeneratedStyle.company_code == company_code)
            cnt = cnt.where(GeneratedStyle.company_code == company_code)
        if job_code:
            base = base.where(GeneratedStyle.job_code == job_code)
            cnt = cnt.where(GeneratedStyle.job_code == job_code)

        base = base.order_by(desc(GeneratedStyle.created_at)).offset(offset).limit(limit)

        rows = (await session.execute(base)).scalars().all()
        total = (await session.execute(cnt)).scalar_one()

        items: List[GeneratedStyleItem] = []
        for r in rows:
            cjds = CompanyJDStyle.model_validate(
                {
                    "style_label": r.style_label or "",
                    "tone_keywords": r.tone_keywords or [],
                    "section_outline": r.section_outline or [],
                    "templates": r.templates or {},
                    "example_jd_markdown": "",
                }
            )
            items.append(
                GeneratedStyleItem(
                    id=r.id,
                    company_code=r.company_code,
                    job_code=r.job_code,
                    created_at=r.created_at,
                    style=cjds,
                )
            )

        return GeneratedStyleListResponse(total=total, items=items)
