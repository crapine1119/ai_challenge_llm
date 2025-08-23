# src/infrastructure/llm/factory.py
import os
from typing import Optional, Tuple

from infrastructure.llm.interface import LLMClient
from infrastructure.llm.openai_client import OpenAIAsyncLLM

# Gemini OpenAI-호환 엔드포인트 기본값
_GEMINI_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _defaults_for_provider(provider: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    provider별 (api_key, base_url, default_model) 기본값을 .env에서 가져옵니다.
    """
    p = (provider or "openai").lower()
    if p == "openai":
        return (
            os.getenv("OPENAI_API_KEY"),
            os.getenv("OPENAI_BASE_URL"),  # 없으면 OpenAI SDK 기본
            os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
        )
    if p == "gemini":
        return (
            os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_BASE_URL") or _GEMINI_DEFAULT_BASE_URL,
            os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash"),
        )
    # fallback: openai
    return (
        os.getenv("OPENAI_API_KEY"),
        os.getenv("OPENAI_BASE_URL"),
        os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
    )


class LLMFactory:
    """
    라우트/서비스에서 손쉽게 LLM 클라이언트를 만들기 위한 팩토리.
    - provider: "openai" | "gemini" (미지정 시 LLM_PROVIDER 또는 openai)
    - model: 미지정 시 각 provider의 기본 모델(.env)
    - json_format: 현재는 클라이언트 생성시엔 사용하지 않음(서비스에서 invoke 시 전달)
    """

    @staticmethod
    def from_env(
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        json_format: bool = False,  # 서비스 레벨에서 invoke(...)에 넘깁니다.
    ) -> LLMClient:
        prov = (provider or os.getenv("LLM_PROVIDER") or "openai").lower()
        api_key, base_url, default_model = _defaults_for_provider(prov)
        chosen_model = model or default_model

        if prov == "openai":
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is not set.")
            # base_url은 없으면 OpenAI 기본을 사용
        elif prov == "gemini":
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY is not set.")
            # base_url 기본값(_GEMINI_DEFAULT_BASE_URL) 적용됨
        else:
            # 알 수 없는 provider → openai로 폴백
            prov = "openai"
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")
            if not chosen_model:
                chosen_model = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")

        # OpenAI-호환 클라이언트 (Gemini도 base_url로 동일 경로 사용)
        return OpenAIAsyncLLM(
            text_model=chosen_model,
            api_key=api_key,
            base_url=base_url,
            provider=prov,  # 내부에서 분기 처리할 수 있도록 힌트 제공
        )


# 과거 코드 호환용 별칭
def make_llm(*, provider: Optional[str] = None, model: Optional[str] = None) -> LLMClient:
    return LLMFactory.from_env(provider=provider, model=model)
