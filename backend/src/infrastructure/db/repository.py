# src/infrastructure/db/repository.py
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Tuple, Sequence

from sqlalchemy import func, update, desc, text, select, distinct
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.company_analysis.models import CompanyJDStyle
from infrastructure.db.models import GeneratedInsight, JDStyle, GeneratedStyle, GeneratedJD, RawJobDescription, JobCode


def build_style_digest_markdown(
    payload: Dict[str, Any],
    *,
    company_code: Optional[str] = None,
    job_code: Optional[str] = None,
    max_chars: int = 20000,
) -> Optional[str]:
    """
    회사 JD 스타일 프리뷰를 Markdown으로 생성.
    - 목적: 리뷰/검색용 가독성 있는 요약 텍스트
    - 구성: 라벨, 톤 키워드, 섹션 아웃라인, 섹션별 템플릿(있으면)
    - 반환: 내용이 없으면 None
    """
    if not payload:
        return None

    label: str = (payload.get("style_label") or "").strip()
    tones: List[str] = payload.get("tone_keywords") or []
    outline: List[str] = payload.get("section_outline") or []
    templates: Dict[str, str] = payload.get("templates") or {}

    parts: List[str] = []

    # 헤더
    header = f"# JD Style Preview: {label or 'N/A'}"
    parts.append(header)

    # 컨텍스트
    ctx_bits = []
    if company_code:
        ctx_bits.append(f"company={company_code}")
    if job_code:
        ctx_bits.append(f"job={job_code}")
    if ctx_bits:
        parts.append(f"*context*: {', '.join(ctx_bits)}")

    # 톤
    if tones:
        parts.append("## Tone keywords")
        parts.append("\n".join(f"- {t}" for t in tones))

    # 섹션 아웃라인
    if outline:
        parts.append("## Section outline")
        parts.append("\n".join(f"{i+1}. {s}" for i, s in enumerate(outline)))

    # 섹션 템플릿(있으면)
    if templates:
        parts.append("## Section templates")
        # outline 순서를 우선 사용하고, 없는 경우엔 templates 키를 보완
        ordered_sections: List[str] = list(outline) if outline else list(templates.keys())
        seen = set(ordered_sections)
        # outline에 없던 템플릿 키도 뒤에 추가
        for k in templates.keys():
            if k not in seen:
                ordered_sections.append(k)

        for sec in ordered_sections:
            body = (templates.get(sec) or "").strip()
            if body:
                parts.append(f"### {sec}\n{body}")
            else:
                parts.append(f"### {sec}\n<!-- no template provided -->")

    text = "\n\n".join(parts).strip()
    if not text:
        return None

    # 과도한 길이 제한(인덱싱/전송 보호)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n<!-- truncated -->"

    return text or None


async def load_job_name(session: AsyncSession, job_code: str) -> Optional[str]:
    q = text("SELECT job_name FROM job_code_map WHERE job_code = :jc LIMIT 1")
    res = await session.execute(q, {"jc": job_code})
    row = res.first()
    return None if not row else str(row[0])


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
        meta_json: Optional[Dict[str, Any]] = None,  # 수집 메타(raw에 저장)
    ) -> int:
        """
        (source, job_id) 고유 제약 기반 UPSERT.
        meta_json이 주어지면 insert/update 모두 반영.
        """
        insert_values: Dict[str, Any] = {
            "source": source,
            "company_code": company_code,
            "job_code": job_code,
            "job_id": job_id,
            "url": url,
            "title": title,
            "jd_text": jd_text,
            "end_date": end_date,
        }
        if meta_json is not None:
            insert_values["meta_json"] = meta_json

        update_values: Dict[str, Any] = {
            "company_code": company_code,
            "job_code": job_code,
            "url": url,
            "title": title,
            "jd_text": jd_text,
            "end_date": end_date,
        }
        if meta_json is not None:
            update_values["meta_json"] = meta_json

        stmt = (
            pg_insert(RawJobDescription)
            .values(**insert_values)
            .on_conflict_do_update(
                constraint="uq_raw_source_jobid",
                set_=update_values,
            )
            .returning(RawJobDescription.id)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one()

    async def set_meta_by_id(self, jd_id: int, meta_json: Dict[str, Any]) -> None:
        """
        별도 메타 갱신이 필요할 때 사용.
        """
        stmt = update(RawJobDescription).where(RawJobDescription.id == jd_id).values(meta_json=meta_json)
        await self.session.execute(stmt)
        await self.session.commit()

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
        선택적 기간 필터는 end_date 기준으로 적용한다.
        """
        q = select(
            RawJobDescription.id,
            RawJobDescription.title,
            RawJobDescription.jd_text,
        ).where(
            RawJobDescription.company_code == company_code,
            RawJobDescription.job_code == job_code,
            RawJobDescription.jd_text.isnot(None),
        )

        if within_days:
            since = date.today() - timedelta(days=within_days)
            q = q.where(RawJobDescription.end_date >= since)

        # 최근 공고 우선: end_date DESC → id DESC
        q = q.order_by(RawJobDescription.end_date.desc(), RawJobDescription.id.desc()).limit(limit)

        rows = (await self.session.execute(q)).all()
        return [(r[0], r[1], r[2]) for r in rows]


class GeneratedInsightRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def latest_raw(self, *, company_code: str, job_code: str) -> Optional[Dict[str, Any]]:
        q = text(
            """
            SELECT analysis_json
              FROM generated_insights
             WHERE company_code = :c
               AND job_code = :j
               AND analysis_json->>'type' = 'company_knowledge_v1'
          ORDER BY generated_date DESC
             LIMIT 1
            """
        )
        row = (await self.session.execute(q, {"c": company_code, "j": job_code})).first()
        return None if not row else row[0]

    async def latest_payload(self, *, company_code: str, job_code: str) -> Optional[Dict[str, Any]]:
        raw = await self.latest_raw(company_code=company_code, job_code=job_code)
        if not raw:
            return None
        payload = raw.get("payload")
        return payload if isinstance(payload, dict) else None

    async def latest_model(self, *, company_code: str, job_code: str):
        # 지연 로딩: pydantic 의존은 런타임에 import
        from domain.company_analysis.models import CompanyKnowledge  # type: ignore

        payload = await self.latest_payload(company_code=company_code, job_code=job_code)
        return None if payload is None else CompanyKnowledge.model_validate(payload)

    async def exists(self, *, company_code: str, job_code: str) -> bool:
        # 기존 GeneratedInsightRepository.has_company_knowledge 와 동일 의미
        q = select(func.count(GeneratedInsight.id)).where(
            GeneratedInsight.company_code == company_code,
            GeneratedInsight.job_code == job_code,
            GeneratedInsight.analysis_json["type"].astext == "company_knowledge_v1",
        )
        return (await self.session.execute(q)).scalar_one() > 0

    async def add_company_knowledge(
        self,
        *,
        company_code: str,
        job_code: str,
        payload_json: Dict[str, Any],
        prompt_id: Optional[int] = None,  # ✅
        prompt_key: Optional[str] = None,  # ✅
        prompt_version: Optional[str] = None,  # ✅
        prompt_language: Optional[str] = None,  # ✅
    ) -> int:
        """
        회사×직무 단위의 Knowledge 스냅샷 저장(LLM 생성 결과).
        """
        row = GeneratedInsight(
            jd_id=None,
            company_code=company_code,
            job_code=job_code,
            analysis_json={"type": "company_knowledge_v1", "payload": payload_json},
            llm_text=None,
            prompt_id=prompt_id,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            prompt_language=prompt_language,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.commit()
        return row.id

    async def add_company_style(
        self,
        *,
        company_code: str,
        job_code: Optional[str],
        payload_json: Dict[str, Any],
        prompt_id: Optional[int] = None,  # ✅
        prompt_key: Optional[str] = None,  # ✅
        prompt_version: Optional[str] = None,  # ✅
        prompt_language: Optional[str] = None,  # ✅
    ) -> int:
        """
        회사×직무(옵션)의 JD 스타일 스냅샷 저장(LLM 생성 결과).
        llm_text에는 '스타일 다이제스트(Markdown)'를 넣어 검색/리뷰에 활용한다.
        - 구성: style_label / tone_keywords / section_outline / templates 요약본
        """
        digest = build_style_digest_markdown(
            payload_json,
            company_code=company_code,
            job_code=job_code,
        )

        row = GeneratedInsight(
            jd_id=None,
            company_code=company_code,
            job_code=job_code,  # None 허용
            analysis_json={"type": "company_jd_style_v1", "payload": payload_json},
            llm_text=digest,  # 예시 마크다운 대신 다이제스트 저장
            prompt_id=prompt_id,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            prompt_language=prompt_language,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.commit()
        return row.id

    async def has_company_knowledge(self, *, company_code: str, job_code: str) -> bool:
        q = select(func.count(GeneratedInsight.id)).where(
            GeneratedInsight.company_code == company_code,
            GeneratedInsight.job_code == job_code,
            GeneratedInsight.analysis_json["type"].astext == "company_knowledge_v1",
        )
        return (await self.session.execute(q)).scalar_one() > 0


class DefaultStyleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_preset(self, *, style_name: str) -> Optional[CompanyJDStyle]:
        q = select(JDStyle).where(JDStyle.style_name == style_name, JDStyle.is_active.is_(True)).limit(1)
        row = (await self.session.execute(q)).scalars().first()
        if not row or not row.payload_json:
            return None
        # payload_json → CompanyJDStyle
        return CompanyJDStyle.model_validate(row.payload_json)


class StyleSnapshotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_style_snapshot(
        self,
        *,
        company_code: str,
        job_code: Optional[str],
        payload: Dict[str, Any],
        digest_md: Optional[str],
        prompt_meta: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> int:
        row = GeneratedStyle(
            company_code=company_code,
            job_code=job_code,
            style_label=(payload.get("style_label") or "").strip(),
            tone_keywords=payload.get("tone_keywords") or [],
            section_outline=payload.get("section_outline") or [],
            templates=payload.get("templates") or {},
            digest_md=digest_md,
            prompt_id=(prompt_meta or {}).get("id"),
            prompt_key=(prompt_meta or {}).get("key"),
            prompt_version=(prompt_meta or {}).get("version"),
            prompt_language=(prompt_meta or {}).get("language") or "",
            provider=provider,
            model=model,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.commit()
        return row.id

    async def latest_for(self, *, company_code: str, job_code: Optional[str]) -> Optional[GeneratedStyle]:
        q = (
            select(GeneratedStyle)
            .where(
                GeneratedStyle.company_code == company_code,
                GeneratedStyle.job_code == job_code,
            )
            .order_by(GeneratedStyle.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(q)
        return res.scalars().first()


class JobCodeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> List[Tuple[str, str]]:
        rows = (await self.session.execute(select(JobCode.job_code, JobCode.job_name))).all()
        return [(r[0], r[1]) for r in rows]


class JDRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_generated(
        self,
        *,
        company_code: str,
        job_code: str,
        title: str,
        markdown: str,
        sections: Optional[List[Dict[str, Any]]] = None,
        meta: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        prompt_meta: Optional[Dict[str, Any]] = None,  # {key,version,language}
        style_source: Optional[str] = None,  # 'generated' | 'default' | 'override'
        style_preset_name: Optional[str] = None,
        style_snapshot_id: Optional[int] = None,
    ) -> int:
        row = GeneratedJD(
            company_code=company_code,
            job_code=job_code,
            title=title,
            jd_markdown=markdown,
            sections=sections,
            meta=meta or {},
            provider=provider,
            model_name=model_name,
            prompt_key=(prompt_meta or {}).get("key"),
            prompt_version=(prompt_meta or {}).get("version"),
            prompt_language=(prompt_meta or {}).get("language"),
            style_source=style_source,
            style_preset_name=style_preset_name,
            style_snapshot_id=style_snapshot_id,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.commit()
        return row.id

    async def latest(self, *, company_code: str, job_code: str) -> Optional[GeneratedJD]:
        q = (
            select(GeneratedJD)
            .where(
                GeneratedJD.company_code == company_code,
                GeneratedJD.job_code == job_code,
            )
            .order_by(desc(GeneratedJD.created_at))
            .limit(1)
        )
        return (await self.session.execute(q)).scalars().first()

    async def get(self, *, jd_id: int) -> Optional[GeneratedJD]:
        q = select(GeneratedJD).where(GeneratedJD.id == jd_id).limit(1)
        return (await self.session.execute(q)).scalars().first()

    async def list(
        self,
        *,
        company_code: Optional[str] = None,
        job_code: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, Sequence[GeneratedJD]]:
        base = select(GeneratedJD)
        cnt = select(func.count(GeneratedJD.id))
        if company_code:
            base = base.where(GeneratedJD.company_code == company_code)
            cnt = cnt.where(GeneratedJD.company_code == company_code)
        if job_code:
            base = base.where(GeneratedJD.job_code == job_code)
            cnt = cnt.where(GeneratedJD.job_code == job_code)
        base = base.order_by(desc(GeneratedJD.created_at)).offset(offset).limit(limit)
        rows = (await self.session.execute(base)).scalars().all()
        total = (await self.session.execute(cnt)).scalar_one()
        return total, rows


class CatalogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def distinct_companies(self) -> List[str]:
        """
        수집된 JD가 존재하는 company_code 목록(distinct, 정렬)
        """
        q = (
            select(distinct(RawJobDescription.company_code))
            .where(RawJobDescription.company_code.is_not(None))
            .order_by(RawJobDescription.company_code.asc())
        )
        rows = (await self.session.execute(q)).all()
        return [r[0] for r in rows if r and r[0]]

    async def distinct_jobs_for_company(self, company_code: str) -> List[tuple[str, str]]:
        """
        특정 회사에서 수집된 job_code 목록과 이름.
        이름은 job_code_map에서 조회, 없으면 code 자체를 name으로 설정.
        """
        # 1) 코드 목록
        q_codes = (
            select(distinct(RawJobDescription.job_code))
            .where(
                RawJobDescription.company_code == company_code,
                RawJobDescription.job_code.is_not(None),
            )
            .order_by(RawJobDescription.job_code.asc())
        )
        codes = [r[0] for r in (await self.session.execute(q_codes)).all() if r and r[0]]
        if not codes:
            return []

        # 2) 이름 매핑
        q_names = select(JobCode.job_code, JobCode.job_name).where(JobCode.job_code.in_(codes))
        mapping = {r[0]: r[1] for r in (await self.session.execute(q_names)).all() if r}
        return [(c, mapping.get(c, c)) for c in codes]
