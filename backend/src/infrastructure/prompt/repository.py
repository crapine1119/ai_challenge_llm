from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import Prompt, JDStyle


class PromptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, *, key: str, version: str, language: Optional[str] = None) -> Optional[Prompt]:
        q = select(Prompt).where(Prompt.prompt_key == key, Prompt.prompt_version == version)
        if language:
            q = q.where((Prompt.language == language) | (Prompt.language.is_(None)))
        res = await self.session.execute(q.order_by(Prompt.language.is_(None)))  # lang 정확 매치 우선
        return res.scalars().first()


class StylePromptResolver:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve(self, style_name: Optional[str], fallback_key: str, fallback_ver: str) -> tuple[str, str]:
        if not style_name:
            return fallback_key, fallback_ver
        q = select(JDStyle).where(JDStyle.style_name == style_name, JDStyle.is_active.is_(True))
        row = (await self.session.execute(q)).scalars().first()
        if row and row.prompt_key and row.prompt_version:
            return row.prompt_key, row.prompt_version
        return fallback_key, fallback_ver
