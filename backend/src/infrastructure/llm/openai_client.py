import os
from typing import Any, AsyncIterator, Dict, Optional, Union, List

from openai import AsyncOpenAI  # pip install openai

from infrastructure.llm.interface import LLMClient, JsonObj

DEFAULT_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "o3-mini")


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def _messages(prompt: str, system: Optional[str]) -> List[Dict[str, Any]]:
    msgs: List[Dict[str, Any]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


class OpenAIAsyncLLM(LLMClient):
    """
    - invoke: 텍스트 또는 구조화(JSON Schema) 출력
    - stream: 텍스트 스트리밍
    """

    def __init__(self, *, text_model: Optional[str] = None):
        self.text_model = text_model or DEFAULT_TEXT_MODEL
        self._cli = _client()

    async def invoke(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        json_schema: Optional[JsonObj] = None,
        strict: bool = True,
    ) -> Union[str, JsonObj]:
        model_name = model or self.text_model

        kwargs: Dict[str, Any] = {
            "model": model_name,
            "input": _messages(prompt, system),
        }

        # 구조화 출력 (JSON Schema)
        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": json_schema.get("title", "schema"),
                    "schema": json_schema,
                    "strict": strict,
                },
            }

        resp = await self._cli.responses.create(**kwargs)

        # JSON 요청일 경우
        if json_schema:
            for chunk in resp.output or []:
                if chunk.type == "message":
                    for part in chunk.content:
                        if part.type == "output_json":
                            return part.parsed  # dict
            return {}  # 파싱 실패 시 빈 객체

        # 텍스트 요청일 경우
        out: List[str] = []
        for chunk in resp.output or []:
            if chunk.type == "message":
                for part in chunk.content:
                    if part.type == "output_text":
                        out.append(part.text or "")
        return "".join(out).strip()

    async def stream(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        model_name = model or self.text_model

        async with self._cli.responses.stream(
            model=model_name,
            input=_messages(prompt, system),
        ) as stream:
            async for event in stream:
                # 텍스트 델타만 전송
                if getattr(event, "type", "") == "response.output_text.delta":
                    yield event.delta or ""
            # 필요하면 최종 응답: final = await stream.get_final_response()
