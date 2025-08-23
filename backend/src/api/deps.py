# src/api/deps.py
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.database import get_session
from infrastructure.llm.interface import LLMClient
from infrastructure.llm.openai_client import OpenAIAsyncLLM
from infrastructure.prompt.manager import PromptManager
from service.company_analysis import CompanyAnalysisService
from service.jd_generation import JDGenerationService


# DB 세션(FastAPI 의존성) — get_session은 yield 종속을 지원하므로 그대로 사용 가능
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for s in get_session():
        yield s


def get_llm() -> LLMClient:
    return OpenAIAsyncLLM()


def get_prompt_manager() -> PromptManager:
    return PromptManager()


def get_company_analysis_service(llm: LLMClient = Depends(get_llm)) -> CompanyAnalysisService:
    return CompanyAnalysisService(llm=llm)


def get_jd_generation_service(
    llm: LLMClient = Depends(get_llm),
    pm: PromptManager = Depends(get_prompt_manager),
) -> JDGenerationService:
    return JDGenerationService(llm=llm, prompt_manager=pm)
