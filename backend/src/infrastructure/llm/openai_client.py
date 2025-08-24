import json
import logging
import os
import re
from typing import Any, AsyncIterator, Dict, Optional, Union, List

from openai import AsyncOpenAI

from infrastructure.llm.interface import LLMClient, JsonObj

DEFAULT_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
_CODE_BLOCK = re.compile(r"```(?:json)?\s*(.+?)```", flags=re.DOTALL)


DEFAULT_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4.1-mini")
_CODE_BLOCK = re.compile(r"```(?:json)?\s*(.+?)```", flags=re.DOTALL)


def _build_client(api_key: Optional[str], base_url: Optional[str]) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key or os.getenv("OPENAI_API_KEY"),
        base_url=(base_url or os.getenv("OPENAI_BASE_URL") or None),
    )


def _messages(prompt: str, system: Optional[str]) -> List[Dict[str, Any]]:
    msgs: List[Dict[str, Any]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


def _normalize_chat_params(opts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not opts:
        return {}
    out: Dict[str, Any] = {}
    passthrough = [
        "temperature",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "stop",
        "max_tokens",  # OpenAI 스타일
        "seed",
        "logit_bias",
        "metadata",
        "tools",
        "tool_choice",
        "extra_body",  # Gemini 고급 옵션(google.*)
    ]
    for k in passthrough:
        if k in opts:
            out[k] = opts[k]
    return out


def _extract_json_from_braces(s: str) -> Optional[Dict[str, Any]]:
    starts: List[int] = [i for i, ch in enumerate(s) if ch in "{["]
    for start in starts:
        stack: List[str] = []
        in_str = False
        esc = False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            else:
                if ch == '"':
                    in_str = True
                    continue
                if ch in "{[":
                    stack.append(ch)
                elif ch in "}]":
                    if not stack:
                        break
                    top = stack.pop()
                    if (top == "{" and ch != "}") or (top == "[" and ch != "]"):
                        break
                    if not stack:
                        cand = s[start : i + 1].strip()
                        try:
                            obj = json.loads(cand)
                            return obj if isinstance(obj, dict) else {"_list": obj}
                        except Exception:
                            break
    return None


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    m = _CODE_BLOCK.search(text)
    if m:
        cand = m.group(1).strip()
        try:
            return json.loads(cand)
        except Exception:
            parsed = _extract_json_from_braces(cand)
            if parsed is not None:
                return parsed
    parsed = _extract_json_from_braces(text)
    return parsed or {}


def _contains_json_word(msgs: List[Dict[str, Any]]) -> bool:
    for m in msgs:
        if "content" in m and isinstance(m["content"], str) and ("json" in m["content"].lower()):
            return True
    return False


def _merge_extra_body(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    """얕은 병합. google 서브필드는 중첩 병합."""
    out = dict(dst or {})
    if not src:
        return out
    for k, v in src.items():
        if k == "google" and isinstance(v, dict):
            g = dict(out.get("google") or {})
            g.update(v)
            out["google"] = g
        else:
            out[k] = v
    return out


class OpenAIAsyncLLM(LLMClient):
    """
    Chat Completions 기반(OpenAI/Gemini 호환)
    - provider 힌트로 JSON 강제 전략을 분기
    """

    def __init__(
        self,
        *,
        text_model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: Optional[str] = None,  # ✅ 추가
    ):
        self.text_model = text_model or DEFAULT_TEXT_MODEL
        self._cli = _build_client(api_key, base_url)
        self.provider = (provider or "openai").lower()

    async def invoke(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        json_schema: Optional[JsonObj] = None,
        strict: bool = True,  # 호환성 유지
        **params: Any,
    ) -> Union[str, JsonObj]:
        model_name = model or self.text_model
        want_json = bool(params.pop("json_format", False))  # ✅ API 인자 처리

        # 메시지 구성 (+ Gemini에서 JSON 강제 시 시스템 규칙 주입)
        sys_text = system or None
        if json_schema and want_json and self.provider == "gemini":
            rule = "반드시 하나의 유효한 JSON 객체만 출력하고, 그 외 텍스트는 절대 포함하지 마세요."
            sys_text = (system + "\n\n" + rule) if system else rule

        msgs = _messages(prompt, sys_text)
        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": msgs,
        }
        kwargs.update(_normalize_chat_params(params))

        # OpenAI에서만 공식 JSON 강제 파라미터 사용 (호환성)
        if json_schema and want_json and self.provider == "openai":
            kwargs["response_format"] = {"type": "json_object"}

        logging.info(f"[LLM Request]\nSystem:\n{sys_text}\n---\nUser:\n{prompt}")
        resp = await self._cli.chat.completions.create(**kwargs)

        text = ""
        if resp and getattr(resp, "choices", None):
            msg = getattr(resp.choices[0], "message", None)
            if msg and getattr(msg, "content", None):
                text = msg.content or ""

        logging.info(f"[LLM Response]\n{text}")

        if json_schema:
            return _extract_json_from_text(text)

        return (text or "").strip()

    async def stream(
        self, *, prompt: str, system: Optional[str] = None, model: Optional[str] = None, **params
    ) -> AsyncIterator[str]:
        model_name = model or self.text_model
        msgs = _messages(prompt, system)

        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": msgs,
            "stream": True,
        }
        kwargs.update(_normalize_chat_params(params))
        stream = await self._cli.chat.completions.create(**kwargs)
        async for chunk in stream:
            try:
                delta = chunk.choices[0].delta
                piece = getattr(delta, "content", None)
                if piece:
                    yield piece
            except Exception:
                continue
