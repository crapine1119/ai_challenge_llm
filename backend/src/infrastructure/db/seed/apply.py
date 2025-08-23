# src/infrastructure/db/seed/apply.py
import hashlib
import json
from typing import Iterable, Optional

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import Prompt, JDStyle, JobCode
from infrastructure.db.seed.schema import SeedBundle

_SEED_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS seed_applied (
  id BIGSERIAL PRIMARY KEY,
  bundle TEXT NOT NULL,
  version TEXT NOT NULL,
  checksum TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_seed_applied UNIQUE (bundle, version)
);
"""


async def ensure_seed_table(session: AsyncSession) -> None:
    await session.execute(text(_SEED_TABLE_SQL))
    await session.commit()


def _checksum_bundle(bundle: SeedBundle) -> str:
    raw = json.dumps(bundle.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def _seed_already_applied(session: AsyncSession, bundle: SeedBundle) -> Optional[str]:
    q = text("SELECT checksum FROM seed_applied WHERE bundle = :b AND version = :v").bindparams(
        b=bundle.bundle, v=bundle.version
    )
    res = await session.execute(q)
    row = res.first()
    return None if row is None else str(row[0])


async def _mark_applied(session: AsyncSession, bundle: SeedBundle, checksum: str) -> None:
    stmt = text(
        "INSERT INTO seed_applied (bundle, version, checksum) VALUES (:b, :v, :c) "
        "ON CONFLICT (bundle, version) DO UPDATE SET checksum = EXCLUDED.checksum, applied_at = NOW()"
    ).bindparams(b=bundle.bundle, v=bundle.version, c=checksum)
    await session.execute(stmt)
    await session.commit()


async def apply_seed_bundle(session: AsyncSession, bundle: SeedBundle, *, force: bool = False) -> bool:
    """
    반환: 실제 변경 적용 여부(True=적용됨, False=스킵)
    - force=False: 동일한 checksum이면 스킵
    """
    await ensure_seed_table(session)

    checksum = _checksum_bundle(bundle)
    prev = await _seed_already_applied(session, bundle)
    if prev == checksum and not force:
        return False

    # 1) job_code_map UPSERT
    for jc in bundle.job_codes:
        stmt = (
            pg_insert(JobCode)
            .values(job_code=jc.job_code, job_name=jc.job_name)
            .on_conflict_do_update(
                index_elements=[JobCode.job_code],
                set_={"job_name": jc.job_name},
            )
        )
        await session.execute(stmt)

    # 2) prompts UPSERT (uq_prompt_key_ver_lang)
    for p in bundle.prompts:
        stmt = (
            pg_insert(Prompt)
            .values(
                prompt_key=p.prompt_key,
                prompt_version=p.prompt_version,
                language=p.language,
                prompt_type=p.prompt_type,
                messages=p.messages,
                template=p.template,
                params=p.params,
                json_schema_key=p.json_schema_key,
                required_vars=p.required_vars,
                is_active=p.is_active,
            )
            .on_conflict_do_update(
                constraint="uq_prompt_key_ver_lang",
                set_={
                    "prompt_type": p.prompt_type,
                    "messages": p.messages,
                    "template": p.template,
                    "params": p.params,
                    "json_schema_key": p.json_schema_key,
                    "required_vars": p.required_vars,
                    "is_active": p.is_active,
                    "updated_at": text("NOW()"),
                },
            )
        )
        await session.execute(stmt)

    # 3) jd_styles UPSERT (style_name UNIQUE)
    for js in bundle.jd_styles:
        stmt = (
            pg_insert(JDStyle)
            .values(
                style_name=js.style_name,
                prompt_key=js.prompt_key,
                prompt_version=js.prompt_version,
                is_active=js.is_active,
            )
            .on_conflict_do_update(
                index_elements=[JDStyle.style_name],
                set_={
                    "prompt_key": js.prompt_key,
                    "prompt_version": js.prompt_version,
                    "is_active": js.is_active,
                },
            )
        )
        await session.execute(stmt)

    await session.commit()
    await _mark_applied(session, bundle, checksum)
    return True


async def apply_all_seeds(session: AsyncSession, bundles: Iterable[SeedBundle], *, force: bool = False) -> int:
    """
    모든 번들을 순차 적용. 적용된 번들 수 반환.
    """
    applied = 0
    for b in bundles:
        changed = await apply_seed_bundle(session, b, force=force)
        if changed:
            applied += 1
    return applied
