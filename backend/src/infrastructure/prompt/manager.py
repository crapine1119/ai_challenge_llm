from functools import lru_cache
from typing import Any, Dict, Optional, List

from langchain.prompts import PromptTemplate
from langchain.prompts.chat import ChatPromptTemplate

from infrastructure.db.database import get_session
from infrastructure.db.models import Prompt as PromptORM
from infrastructure.prompt.repository import PromptRepository, StylePromptResolver


class PromptRenderResult(Dict[str, Any]):
    """
    반환값:
      - system: Optional[str]
      - user_text: str                # LLM.invoke 용
      - json_schema_key: Optional[str]
      - params: Dict[str, Any]
    """


@lru_cache(maxsize=512)
def _split_system_user_from_messages(messages: List[Dict[str, str]]) -> tuple[Optional[str], str]:
    sys_parts, user_parts = [], []
    for m in messages:
        role = (m.get("role") or "").lower()
        content = m.get("content") or ""
        if role == "system":
            sys_parts.append(content)
        elif role == "user":
            user_parts.append(content)
        # assistant/tool은 렌더 후 무시(맥락 프롬프트로만 사용한다면 필요 시 확장)
    system = "\n".join(sys_parts) if sys_parts else None
    user_text = "\n\n".join(user_parts)
    return system, user_text


def _ensure_required_vars(required: List[str], ctx: Dict[str, Any]) -> None:
    missing = [k for k in required or [] if k not in ctx]
    if missing:
        raise KeyError(f"Missing prompt variables: {missing}")


async def render_by_key_version(
    *,
    key: str,
    version: str,
    language: Optional[str],
    context: Dict[str, Any],
) -> PromptRenderResult:
    async for session in get_session():
        repo = PromptRepository(session)
        p: Optional[PromptORM] = await repo.get(key=key, version=version, language=language)
        if not p or not p.is_active:
            raise LookupError(f"Prompt not found or inactive: {key}/{version} (lang={language})")

        # 필수 변수 체크
        _ensure_required_vars(p.required_vars or [], context)

        # string 템플릿
        if p.prompt_type == "string":
            tmpl = PromptTemplate.from_template(p.template or "")
            user_text = tmpl.format(**context)
            return PromptRenderResult(
                system=None,
                user_text=user_text,
                json_schema_key=p.json_schema_key,
                params=p.params or {},
                language=language,
                key=key,
                version=version,
            )

        # chat 템플릿
        if p.prompt_type == "chat":
            # DB의 messages는 [{role, content(=template)}...]
            # LangChain ChatPromptTemplate로 렌더
            msgs = p.messages or []
            chat = ChatPromptTemplate.from_messages([(m["role"], m["content"]) for m in msgs])
            rendered_msgs = chat.format_messages(**context)
            # LangChain Message 객체를 다시 role/content로 변환
            serial = [{"role": m.type, "content": m.content} for m in rendered_msgs]
            system, user_text = _split_system_user_from_messages(serial)
            return PromptRenderResult(
                system=system,
                user_text=user_text,
                json_schema_key=p.json_schema_key,
                params=p.params or {},
                language=language,
                key=key,
                version=version,
            )

        raise ValueError(f"Unsupported prompt_type: {p.prompt_type}")


async def render_by_style(
    *,
    style_name: Optional[str],
    fallback_key: str,
    fallback_ver: str,
    language: Optional[str],
    context: Dict[str, Any],
) -> PromptRenderResult:
    async for session in get_session():
        resolver = StylePromptResolver(session)
        key, ver = await resolver.resolve(style_name, fallback_key, fallback_ver)
    return await render_by_key_version(key=key, version=ver, language=language, context=context)
