from datetime import date, timedelta
from typing import Dict, Any, List, Tuple, Optional

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import GeneratedInsight, RawJobDescription


class RawJDRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_by_job_id(
        self,
        *,
        source: str,
        company_code: str,
        job_code: str,
        job_id: str,
        url: str,
        title: Optional[str],
        jd_text: str,
        end_date: date,
    ) -> int:
        stmt = (
            insert(RawJobDescription)
            .values(
                source=source,
                company_code=company_code,
                job_code=job_code,
                job_id=job_id,
                url=url,
                title=title,
                jd_text=jd_text,
                end_date=end_date,
            )
            .on_conflict_do_update(
                constraint="uq_raw_source_jobid",
                set_={
                    "company_code": company_code,
                    "job_code": job_code,
                    "url": url,
                    "title": title,
                    "jd_text": jd_text,
                    "end_date": end_date,
                },
            )
            .returning(RawJobDescription.id)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one()

    async def fetch_texts_for_company_job(
        self,
        *,
        company_code: str,
        job_code: str,
        limit: int = 50,
        within_days: Optional[int] = None,
    ) -> List[Tuple[int, Optional[str], str]]:
        """
        반환: list[(jd_id, title, jd_text)]
        """
        q = select(RawJobDescription.id, RawJobDescription.title, RawJobDescription.jd_text).where(
            RawJobDescription.company_code == company_code,
            RawJobDescription.job_code == job_code,
            RawJobDescription.jd_text.isnot(None),
        )
        if within_days:
            q = q.where(RawJobDescription.crawled_date >= date.today() - timedelta(days=within_days))
        q = q.order_by(RawJobDescription.id.desc()).limit(limit)
        rows = (await self.session.execute(q)).all()
        return [(r[0], r[1], r[2]) for r in rows]


class GeneratedInsightRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_analysis(
        self,
        *,
        jd_id: int,
        company_code: str,
        job_code: str,
        analysis_json: Optional[Dict[str, Any]] = None,
    ) -> int:
        stmt = (
            insert(GeneratedInsight)
            .values(
                jd_id=jd_id,
                company_code=company_code,
                job_code=job_code,
                analysis_json=analysis_json,
            )
            .returning(GeneratedInsight.id)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one()

    async def add_generation_text(
        self,
        *,
        jd_id: int,
        company_code: str,
        job_code: str,
        llm_text: str,
        analysis_json: Optional[Dict[str, Any]] = None,  # 필요하면 함께 저장
    ) -> int:
        stmt = (
            insert(GeneratedInsight)
            .values(
                jd_id=jd_id,
                company_code=company_code,
                job_code=job_code,
                llm_text=llm_text,
                analysis_json=analysis_json,
            )
            .returning(GeneratedInsight.id)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one()

    async def add_company_knowledge(
        self,
        *,
        company_code: str,
        job_code: str,
        payload_json: Dict[str, Any],
    ) -> int:
        row = GeneratedInsight(
            jd_id=None,
            company_code=company_code,
            job_code=job_code,
            analysis_json={"type": "company_knowledge_v1", "payload": payload_json},
            llm_text=None,
        )
        self.session.add(row)
        await self.session.flush()
        return row.id

    async def add_company_style(
        self,
        *,
        company_code: str,
        job_code: Optional[str],
        payload_json: Dict[str, Any],
    ) -> int:
        row = GeneratedInsight(
            jd_id=None,
            company_code=company_code,
            job_code=job_code or "",
            analysis_json={"type": "company_jd_style_v1", "payload": payload_json},
            llm_text=payload_json.get("example_jd_markdown"),
        )
        self.session.add(row)
        await self.session.flush()
        return row.id
