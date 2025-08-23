# src/infrastructure/prompt/manager.py
import hashlib
import json
import os
import re
from typing import Any, Dict, Optional, List, Tuple

import yaml
from langchain.prompts import PromptTemplate
from langchain.prompts.chat import ChatPromptTemplate

from infrastructure.db.database import get_session
from infrastructure.db.models import Prompt as PromptORM
from infrastructure.prompt.repository import PromptRepository
from infrastructure.prompt.schema import PromptFile
from infrastructure.prompt.schema import PromptTemplateInput  # PromptTemplateInput 사용
from infrastructure.prompt.sync import fast_sync_one, _resolve_path

FAST_SYNC_ON_STALE = os.getenv("PROMPT_FAST_SYNC", "1").lower() in ("1", "true", "yes", "on")


# 파일 어디든(모듈 전역) 보조 함수 추가
_JINJA_VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _jinja_to_langchain(text: str) -> str:
    # {{ var }} -> {var}
    return _JINJA_VAR.sub(r"{\1}", text)


class PromptRenderResult(Dict[str, Any]):
    """
    반환 키:
      - system: Optional[str]            # 내부 호환 키
      - user_text: str                   # 내부 호환 키
      - json_schema_key: Optional[str]
      - params: Dict[str, Any]
      - key: str
      - version: str
      - language: Optional[str]
      - prompt_id: Optional[int]         # ✅ 프롬프트 FK (prompts.id)

      # 외부 서비스(JDGenerationService 등) 호환 별칭:
      - system_prompt: Optional[str]     # = system
      - prompt: str                      # = user_text
    """


def _split_system_user_from_messages(messages: List[Dict[str, str]]) -> Tuple[Optional[str], str]:
    sys_parts, user_parts = [], []
    for m in messages:
        role = (m.get("role") or "").lower()
        content = m.get("content") or ""
        if role == "system":
            sys_parts.append(content)
        elif role in ["user", "human"]:
            user_parts.append(content)
        # assistant/tool 역할은 현재 렌더 결과에서 제외
    system = "\n".join(sys_parts) if sys_parts else None
    user_text = "\n\n".join(user_parts)
    return system, user_text


def _ensure_required_vars(required: List[str], ctx: Dict[str, Any]) -> None:
    missing = [k for k in (required or []) if k not in ctx]
    if missing:
        raise KeyError(f"Missing prompt variables: {missing}")


async def render_by_key_version(
    *,
    key: str,
    version: str,
    language: Optional[str],
    context: Dict[str, Any],
) -> PromptRenderResult:
    """
    DB에서 (key, version, language) 프롬프트를 가져와 LangChain 템플릿으로 렌더합니다.
    - string 템플릿: PromptTemplate
    - chat 템플릿: ChatPromptTemplate → system/user 분리
    """
    # ✅ 렌더 직전 변경 감지 & 단건 동기화
    await _maybe_fast_sync_before_render(key=key, version=version, language=language)

    async for session in get_session():
        repo = PromptRepository(session)
        p: Optional[PromptORM] = await repo.get(key=key, version=version, language=language)
        if not p or not p.is_active:
            raise LookupError(f"Prompt not found or inactive: {key}/{version} (lang={language})")

        # 필수 변수 체크
        _ensure_required_vars(p.required_vars or [], context)

        # string 템플릿
        if p.prompt_type == "string":
            tmpl_src = _jinja_to_langchain(p.template or "")
            tmpl = PromptTemplate.from_template(tmpl_src)
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
            msgs = p.messages or []
            # Jinja 플레이스홀더를 LangChain 스타일로 변환
            normalized = [(m["role"], _jinja_to_langchain(m["content"])) for m in msgs]
            chat = ChatPromptTemplate.from_messages(normalized)
            rendered_msgs = chat.format_messages(**context)
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
                prompt_id=p.id,
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
    # 🔁 과거에는 style_name → jd_styles → prompt_key/version 매핑을 했음
    # 이제는 prompt 매핑을 사용하지 않으므로 항상 fallback으로 렌더
    return await render_by_key_version(key=fallback_key, version=fallback_ver, language=language, context=context)


# ------------------------------------------------------------------------------
# High-level Manager
# ------------------------------------------------------------------------------


class PromptManager:
    """
    서비스 레이어에서 사용하기 좋은 고수준 API.
    - render_chat(prompt_input): PromptTemplateInput → PromptRenderResult
    """

    async def render_chat(self, prompt_input: PromptTemplateInput) -> PromptRenderResult:
        """
        PromptTemplateInput을 받아 프롬프트를 렌더합니다.
        style_name이 주어지면 스타일 우선, 아니면 (key, version)로 직접 렌더.
        """
        if prompt_input.style_name:
            return await render_by_style(
                style_name=prompt_input.style_name,
                fallback_key=prompt_input.prompt_key,
                fallback_ver=prompt_input.prompt_version,
                language=prompt_input.language,
                context=prompt_input.variables or {},
            )
        return await render_by_key_version(
            key=prompt_input.prompt_key,
            version=prompt_input.prompt_version,
            language=prompt_input.language,
            context=prompt_input.variables or {},
        )


async def _maybe_fast_sync_before_render(key: str, version: str, language: Optional[str]) -> None:
    """
    빠른 변경 감지:
      - 파일이 존재하면 파일의 hash와 DB의 content_hash 비교 → 다르면 그 프롬프트만 upsert
      - 파일이 없으면 아무 것도 안 함
    """
    if not FAST_SYNC_ON_STALE:
        return
    path = _resolve_path(key, version, language)
    if not path:
        return  # 파일이 없으면 스킵

    # 파일 hash 계산

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # 해시 입력값은 sync.py와 동일 구조로

    pf = PromptFile(**data)
    src = {
        "prompt_type": pf.prompt_type,
        "messages": pf.messages,
        "template": pf.template,
        "params": pf.params or {},
        "json_schema_key": pf.json_schema_key,
        "required_vars": pf.required_vars or [],
    }
    s = json.dumps(src, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fhash = hashlib.sha256(s.encode("utf-8")).hexdigest()

    # DB content_hash 조회
    async for session in get_session():
        repo = PromptRepository(session)
        row: Optional[PromptORM] = await repo.get(key=key, version=version, language=language)
        db_hash = getattr(row, "content_hash", None) if row else None

    # 다르면 단건 fast sync 실행
    if fhash != db_hash:
        await fast_sync_one(key, version, language)
