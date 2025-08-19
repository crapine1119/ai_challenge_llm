from datetime import date
from typing import Dict, Any
from typing import Optional

from sqlalchemy import insert
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
