import json
import logging
from typing import Optional, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import db_session
from api.schemas.jd_generation import JDGenerateRequest, JDGenerateResponse, JDGetResponse, JDListResponse, JDItem
from domain.company_analysis.models import CompanyKnowledge, CompanyJDStyle
from infrastructure.db.repository import (
    JDRepository,
    StyleSnapshotRepository,
    DefaultStyleRepository,
    GeneratedInsightRepository,
    load_job_name,
)
from infrastructure.llm.factory import make_llm
from infrastructure.prompt.manager import PromptManager
from service.jd_generation import JDGenerationService

router = APIRouter(prefix="/jd", tags=["jd"])


def _title_from_markdown(md: str, fallback: str) -> str:
    first = (md or "").splitlines()[0].strip()
    if first.startswith("#"):
        t = first.lstrip("#").strip()
        return t or fallback
    return fallback


async def _resolve_style_meta_for_saving(
    session: AsyncSession,
    *,
    style_override: Optional[CompanyJDStyle],
    style_source_req: str,  # request.style_source
    default_style_name: Optional[str],
    company_code: str,
    job_code: str,
) -> dict:
    # 1) 명시 오버라이드(직접 전달) 우선
    if style_override is not None:
        return {"style_source": "override", "style_preset_name": None, "style_snapshot_id": None}

    # 2) 생성 스냅샷 선택
    if style_source_req == "generated":
        snap = await StyleSnapshotRepository(session).latest_for(company_code=company_code, job_code=job_code)
        return {
            "style_source": "generated",
            "style_preset_name": None,
            "style_snapshot_id": (snap.id if snap else None),
        }

    # 3) 기본 프리셋
    name = default_style_name or "일반적"
    # 존재 확인은 선택적(저장 필드용으로 이름만 기록해도 됨)
    _ = await DefaultStyleRepository(session).get_preset(style_name=name)
    return {"style_source": "default", "style_preset_name": name, "style_snapshot_id": None}


@router.post("/generate", response_model=JDGenerateResponse)
async def generate_jd(
    body: JDGenerateRequest,
    session: AsyncSession = Depends(db_session),
):
    # LLM / PM / Service
    llm = make_llm(provider=body.provider, model=body.model)
    pm = PromptManager()
    svc = JDGenerationService(llm=llm, prompt_manager=pm)

    # Knowledge: override 우선, 없으면 DB 최신
    if body.knowledge_override is not None:
        try:
            knowledge = CompanyKnowledge.model_validate(body.knowledge_override)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid knowledge_override: {e}")
    else:
        kn_repo = GeneratedInsightRepository(session)
        kn_payload = await kn_repo.latest_payload(company_code=body.company_code, job_code=body.job_code)
        if not kn_payload:
            raise HTTPException(status_code=404, detail="No saved knowledge for given company_code/job_code")
        try:
            knowledge = CompanyKnowledge.model_validate(kn_payload)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Saved knowledge payload invalid: {e}")

    # Style: override 있으면 사용, 없으면 서비스가 policy대로 해결
    style: Optional[CompanyJDStyle] = None
    if body.style_override is not None:
        try:
            style = CompanyJDStyle.model_validate(body.style_override)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid style_override: {e}")

    # 프롬프트 라벨
    company_label = body.company_code
    job_label = (await load_job_name(session, body.job_code)) or body.job_code

    # 생성
    try:
        markdown = await svc.generate_jd_markdown(
            company=company_label,
            job=job_label,
            job_code=body.job_code,
            knowledge=knowledge,
            jd_style=style,
            style_source=body.style_source,
            default_style_name=body.default_style_name,
            model=body.model,
            language=body.language,
        )
    except AssertionError as e:
        raise HTTPException(status_code=502, detail=f"LLM assertion failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 제목 + 메타(가능하면 스타일 요약, 없으면 빈 dict)
    title = _title_from_markdown(markdown, fallback=f"{company_label} {job_label}")
    meta, style_meta = {}, {}
    try:
        style_meta = await _resolve_style_meta_for_saving(
            session,
            style_override=body.style_override,
            style_source_req=body.style_source,
            default_style_name=body.default_style_name,
            company_code=body.company_code,
            job_code=body.job_code,
        )
    except Exception as e:
        pass

    # ✅ 무조건 저장
    repo = JDRepository(session)
    saved_id = await repo.save_generated(
        company_code=company_label,
        job_code=body.job_code,
        title=title,
        markdown=markdown,
        sections=None,
        meta=meta,
        provider=(body.provider or None),
        model_name=(body.model or None),
        prompt_meta={"key": "jd.generation", "version": "v1", "language": body.language},
        style_source=style_meta.get("style_source", None),
        style_preset_name=style_meta.get("style_preset_name", None),
        style_snapshot_id=style_meta.get("style_snapshot_id", None),
    )
    logging.info(f"Save Complete: company_code={company_label}, job_code={job_label}, saved_id={saved_id}")
    return JDGenerateResponse(
        company_code=company_label,
        job_code=job_label,
        markdown=markdown,
        saved_id=saved_id,
    )


# ✅ 신규: 스트리밍 생성(SSE)
@router.post("/generate/stream")
async def generate_jd_stream(
    body: JDGenerateRequest,
    session: AsyncSession = Depends(db_session),
):
    """
    Server-Sent Events 로 JD 생성 텍스트 조각(delta)을 실시간 전송.
    - event: "start"  → 요청 메타
    - event: "delta"  → 본문 조각
    - event: "end"    → 저장 결과(saved_id, title)
    - event: "error"  → 오류 메시지
    """

    # 1) LLM / PM / Service
    llm = make_llm(provider=body.provider, model=body.model)
    pm = PromptManager()
    svc = JDGenerationService(llm=llm, prompt_manager=pm)

    # 2) Knowledge 준비
    if body.knowledge_override is not None:
        try:
            knowledge = CompanyKnowledge.model_validate(body.knowledge_override)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid knowledge_override: {e}")
    else:
        kn_repo = GeneratedInsightRepository(session)
        kn_payload = await kn_repo.latest_payload(company_code=body.company_code, job_code=body.job_code)
        if not kn_payload:
            raise HTTPException(status_code=404, detail="No saved knowledge for given company_code/job_code")
        try:
            knowledge = CompanyKnowledge.model_validate(kn_payload)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Saved knowledge payload invalid: {e}")

    # 3) Style (override 있으면 그대로, 없으면 서비스에서 해석)
    style: Optional[CompanyJDStyle] = None
    if body.style_override is not None:
        try:
            style = CompanyJDStyle.model_validate(body.style_override)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid style_override: {e}")

    # 4) 라벨
    company_label = body.company_code
    job_label = (await load_job_name(session, body.job_code)) or body.job_code

    # 5) 저장 시 사용할 스타일 메타 미리 결정(오류 나더라도 스트림은 계속)
    try:
        style_meta = await _resolve_style_meta_for_saving(
            session,
            style_override=body.style_override,
            style_source_req=body.style_source,
            default_style_name=body.default_style_name,
            company_code=body.company_code,
            job_code=body.job_code,
        )
    except Exception:
        style_meta = {"style_source": None, "style_preset_name": None, "style_snapshot_id": None}

    async def sse_gen() -> AsyncIterator[bytes]:
        # start 이벤트
        start_payload = {
            "event": "start",
            "company_code": company_label,
            "job_code": job_label,
            "provider": body.provider,
            "model": body.model,
            "style_source": style_meta.get("style_source"),
            "style_preset_name": style_meta.get("style_preset_name"),
            "style_snapshot_id": style_meta.get("style_snapshot_id"),
        }
        yield f"event: start\ndata: {json.dumps(start_payload, ensure_ascii=False)}\n\n".encode("utf-8")

        buffer = []
        saved_id = None
        try:
            # LLM 스트림 시작
            async for piece in svc.generate_jd_markdown_stream(
                company=company_label,
                job=job_label,
                job_code=body.job_code,
                knowledge=knowledge,
                jd_style=style,
                style_source=body.style_source,
                default_style_name=body.default_style_name,
                model=body.model,
                language=body.language,
            ):
                buffer.append(piece)
                yield f"event: delta\ndata: {json.dumps({'text': piece}, ensure_ascii=False)}\n\n".encode("utf-8")

            # 전송 완료 → 저장
            markdown = "".join(buffer).strip()
            title = _title_from_markdown(markdown, fallback=f"{company_label} {job_label}")

            repo = JDRepository(session)
            saved_id = await repo.save_generated(
                company_code=company_label,
                job_code=body.job_code,
                title=title,
                markdown=markdown,
                sections=None,
                meta={},  # 필요 시 확장
                provider=(body.provider or None),
                model_name=(body.model or None),
                prompt_meta={"key": "jd.generation", "version": "v1", "language": body.language},
                style_source=style_meta.get("style_source", None),
                style_preset_name=style_meta.get("style_preset_name", None),
                style_snapshot_id=style_meta.get("style_snapshot_id", None),
            )

            end_payload = {"event": "end", "saved_id": saved_id, "title": title}
            yield f"event: end\ndata: {json.dumps(end_payload, ensure_ascii=False)}\n\n".encode("utf-8")

        except Exception as e:
            err = {"event": "error", "message": str(e)}
            yield f"event: error\ndata: {json.dumps(err, ensure_ascii=False)}\n\n".encode("utf-8")

    return StreamingResponse(
        sse_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# --- 조회 API ---
@router.get("/latest", response_model=JDGetResponse)
async def get_latest_jd(company_code: str, job_code: str, session: AsyncSession = Depends(db_session)):
    row = await JDRepository(session).latest(company_code=company_code, job_code=job_code)
    if not row:
        raise HTTPException(status_code=404, detail="No generated JD")
    return JDGetResponse(
        id=row.id,
        company_code=row.company_code,
        job_code=row.job_code,
        markdown=row.jd_markdown,
        title=row.title,
        created_at=row.created_at,
    )


@router.get("/{jd_id}", response_model=JDGetResponse)
async def get_jd_by_id(jd_id: int, session: AsyncSession = Depends(db_session)):
    row = await JDRepository(session).get(jd_id=jd_id)
    if not row:
        raise HTTPException(status_code=404, detail="JD not found")
    return JDGetResponse(
        id=row.id,
        company_code=row.company_code,
        job_code=row.job_code,
        markdown=row.jd_markdown,
        title=row.title,
        created_at=row.created_at,
    )


@router.get("", response_model=JDListResponse)
async def list_jds(
    company_code: Optional[str] = None,
    job_code: Optional[str] = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(db_session),
):
    total, rows = await JDRepository(session).list(
        company_code=company_code, job_code=job_code, limit=limit, offset=offset
    )
    items = [
        JDItem(
            id=r.id,
            company_code=r.company_code,
            job_code=r.job_code,
            markdown=r.jd_markdown,
            title=r.title,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return JDListResponse(total=total, items=items)
