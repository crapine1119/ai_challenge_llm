import logging
import time
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple

from domain.job_entities import JobListItem, JobDetail
from infrastructure.crawler import JobKoreaCrawler  # 기존 크롤러 파일 경로 예시
from infrastructure.db.database import get_session
from infrastructure.db.repository import GeneratedInsightRepository, RawJDRepository
from infrastructure.http_client import HttpClient

SOURCE = "jobkorea"


def _pick_jd_text(detail: Optional[JobDetail]) -> Optional[str]:
    if not detail:
        return None
    if detail.detail_text and detail.detail_text.strip():
        return detail.detail_text.strip()
    return None


def _derive_url(item: JobListItem, detail: Optional[JobDetail]) -> str:
    return detail.url if detail and detail.url else item.href


def _derive_title(item: JobListItem, detail: Optional[JobDetail]) -> Optional[str]:
    return detail.title if detail and detail.title else item.title


def _derive_end_date(detail: JobDetail) -> datetime.date:
    try:
        return datetime.strptime(detail.end_date, "%Y.%m.%d").date()
    except Exception as e:
        return date.today()


def _build_basic_meta(item: JobListItem, detail: Optional[JobDetail]) -> Dict:
    meta = {
        "type": "source_meta",
        "source": SOURCE,
        "list_item": {
            "title": item.title,
            "href": item.href,
            "job_id": item.job_id,
            "meta": item.meta,
        },
    }
    if detail:
        meta["detail"] = {
            "company": detail.company,
            "location": detail.location,
            "career": detail.career,
            "education": detail.education,
            "employment_type": detail.employment_type,
            "salary": detail.salary,
            "start_date": detail.start_date,
            "end_date": detail.end_date,
            "iframe_url": detail.iframe_url,
            "detail_text_len": len(detail.detail_text) if detail.detail_text else 0,
            "detail_html_len": len(detail.detail_html) if detail.detail_html else 0,
        }
    return meta


async def crawl_jobkorea_and_store(
    *,
    company_id: int,
    company_code: str,
    job_code: str,
    list_params: Optional[Dict[str, str]] = None,
    max_details: int = 5,
    save_meta: bool = True,
) -> Dict[str, int]:
    """
    1) 잡코리아 공고 수집
    2) raw_job_descriptions upsert
    3) (옵션) generated_insights.analysis_json 저장
    """
    list_params = list_params or {
        "GI_Part_Code": job_code,
        "Search_Order": "1",
        "Part_Btn_Stat": "0",
    }

    # === 시작 로그 ===
    logging.info(
        "crawl.start source=%s company_id=%s company_code=%s job_code=%s max_details=%s list_params=%s",
        SOURCE,
        company_id,
        "???",
        job_code,
        max_details,
        list_params,
    )
    t0 = time.monotonic()

    crawler = JobKoreaCrawler(http=HttpClient())
    pairs: List[Tuple[JobListItem, Optional[JobDetail]]] = crawler.crawl_company_recruits(
        company_id=company_id, list_params=list_params, max_details=max_details
    )
    saved_raw = 0
    saved_meta_cnt = 0
    total = len(pairs)
    skipped_no_jobid = 0
    skipped_no_text = 0
    errors = 0

    async for session in get_session():
        raw_repo = RawJDRepository(session)
        insight_repo = GeneratedInsightRepository(session)

        for item, detail in pairs:
            try:
                # 필수 키 확인
                jid = detail.job_id if detail and detail.job_id else item.job_id
                if not jid:
                    skipped_no_jobid += 1
                    continue

                jd_text = _pick_jd_text(detail)
                if not jd_text:
                    skipped_no_text += 1
                    continue

                url = _derive_url(item, detail)
                title = _derive_title(item, detail)
                meta_payload = _build_basic_meta(item, detail) if save_meta else None
                if meta_detail := meta_payload.get("detail", None):
                    company_code = meta_detail.get("company", None)
                else:
                    company_code = f"unknown:{jid}"
                jd_id = await raw_repo.upsert_by_job_id(
                    source=SOURCE,
                    company_code=company_code,
                    job_code=job_code,
                    job_id=jid,
                    url=url,
                    title=title,
                    jd_text=jd_text,
                    end_date=_derive_end_date(detail),
                    meta_json=meta_payload,  # ✅ 메타를 raw에 저장
                )

                saved_raw += 1
                if meta_payload:
                    saved_meta_cnt += 1

            except Exception as e:
                errors += 1
                logging.exception(
                    "crawl.item_error job_id=%s url=%s error=%s",
                    (detail.job_id if detail else item.job_id),
                    _derive_url(item, detail),
                    e,
                )

    dt = time.monotonic() - t0
    # === 종료 로그 ===
    logging.info(
        "crawl.end source=%s company_id=%s company_code=%s job_code=%s "
        "total=%d saved_raw=%d saved_meta=%d skipped_no_jobid=%d skipped_no_text=%d errors=%d duration_sec=%.2f",
        SOURCE,
        company_id,
        company_code,
        job_code,
        total,
        saved_raw,
        saved_meta_cnt,
        skipped_no_jobid,
        skipped_no_text,
        errors,
        dt,
    )

    return {"saved_raw": saved_raw, "saved_meta": saved_meta_cnt}
