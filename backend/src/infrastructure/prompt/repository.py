# src/infrastructure/prompt/repository.py
from typing import Optional, Any
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import Prompt as PromptORM, JDStyle


class PromptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, *, key: str, version: str, language: Optional[str] = None) -> Optional[PromptORM]:
        """
        (key, version, language)로 프롬프트를 조회합니다.
        우선순위:
          1) language 정확 매치
          2) language=NULL (기본)
        모든 케이스에서 is_active=True만 반환합니다.
        """
        q = select(PromptORM).where(
            PromptORM.prompt_key == key,
            PromptORM.prompt_version == version,
            PromptORM.is_active.is_(True),
        )

        if language:
            # exact match 또는 NULL만 대상으로 제한
            q = q.where((PromptORM.language == language) | (PromptORM.language.is_(None)))
            # True가 먼저 오도록 desc 정렬 → 정확 매치가 1차, 그다음 NULL
            q = q.order_by((PromptORM.language == language).desc(), PromptORM.language.is_(None).asc())
        else:
            # language가 None이면 기본(NULL) 우선
            # (language IS NOT NULL) 의 False(NULL) → True(비NULL) 순서로 정렬되므로 NULL이 먼저 온다.
            q = q.order_by(PromptORM.language.isnot(None))

        res = await self.session.execute(q.limit(1))
        return res.scalars().first()

    async def upsert_one(
        self,
        *,
        key: str,
        version: str,
        language: Optional[str],
        prompt_type: str,
        messages: Optional[list],
        template: Optional[str],
        params: dict[str, Any],
        json_schema_key: Optional[str],
        required_vars: list,
        content_hash: Optional[str],
        is_active: bool = True,
    ) -> int:
        stmt = (
            pg_insert(PromptORM)
            .values(
                prompt_key=key,
                prompt_version=version,
                language=language,
                prompt_type=prompt_type,
                messages=messages,
                template=template,
                params=params,
                json_schema_key=json_schema_key,
                required_vars=required_vars,
                is_active=is_active,
                content_hash=content_hash,
            )
            .on_conflict_do_update(
                constraint="uq_prompt_key_ver_lang",
                set_={
                    "prompt_type": prompt_type,
                    "messages": messages,
                    "template": template,
                    "params": params,
                    "json_schema_key": json_schema_key,
                    "required_vars": required_vars,
                    "is_active": is_active,
                    "content_hash": content_hash,
                },
            )
            .returning(PromptORM.id)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.scalar_one()


class StylePromptResolver:
    """
    style_name → (prompt_key, prompt_version) 매핑을 조회합니다.
    - 지정된 스타일이 없거나 비활성/미완이면 fallback (key, ver) 반환
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve(self, style_name: Optional[str], fallback_key: str, fallback_ver: str) -> Tuple[str, str]:
        if not style_name:
            return fallback_key, fallback_ver

        q = select(JDStyle).where(
            JDStyle.style_name == style_name,
            JDStyle.is_active.is_(True),
        )
        row = (await self.session.execute(q.limit(1))).scalars().first()

        if row and row.prompt_key and row.prompt_version:
            return row.prompt_key, row.prompt_version
        return fallback_key, fallback_ver
