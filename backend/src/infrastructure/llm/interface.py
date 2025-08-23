from typing import Any, AsyncIterator, Dict, Optional, Protocol, Union

JsonObj = Dict[str, Any]


class LLMClient(Protocol):
    async def invoke(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        json_schema: Optional[JsonObj] = None,
        strict: bool = True,
        **options: Any,  # ✅ 프롬프트 params 전달 허용
    ) -> Union[str, JsonObj]:
        """
        단발 호출.
        - json_schema가 주어지면 JSON(딕셔너리) 반환
        - 아니면 문자열 반환
        - options: temperature, max_output_tokens, top_p, stop 등 생성 파라미터
        """

    async def stream(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        토큰 스트리밍. 텍스트 델타를 차례로 yield.
        """
