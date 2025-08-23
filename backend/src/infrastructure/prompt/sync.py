import argparse
import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple
from typing import Optional, Dict, Any

import yaml
from sqlalchemy import Select, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.database import SessionLocal, get_session
from infrastructure.db.models import Prompt as PromptORM
from infrastructure.prompt.repository import PromptRepository
from infrastructure.prompt.schema import PromptFile

# ===== 설정 =====
LOGGER = logging.getLogger("prompt.sync")

# 폴더 규약: src/prompts/{lang}/{key}.{version}.yaml
PROMPT_ROOT = Path(os.getenv("PROMPT_ROOT", "src/prompts"))
YAML_EXTS = {".yml", ".yaml"}


@dataclass
class SyncStats:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0


# ===== 파일 로딩 =====
def _discover_yaml_files(root: str | Path, language: Optional[str] = None) -> List[Path]:
    root_path = Path(root)
    if not root_path.exists():
        LOGGER.warning("Prompt root does not exist: %s", root_path)
        return []
    files: List[Path] = []
    # 언어를 지정하면 해당 서브폴더(예: ko/, en/)를 우선적으로 뒤진다.
    if language:
        lang_dir = root_path / language
        if lang_dir.exists():
            for p in lang_dir.rglob("*"):
                if p.is_file() and p.suffix.lower() in YAML_EXTS:
                    files.append(p)
    # 나머지 전체도 탐색
    for p in root_path.rglob("*"):
        if p.is_file() and p.suffix.lower() in YAML_EXTS:
            if p not in files:
                files.append(p)
    files.sort()
    return files


def _load_yaml(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"YAML must be a mapping: {p}")
        return data


def _to_promptfile(d: Dict[str, Any]) -> PromptFile:
    # PromptFile가 기본값/검증을 담당
    return PromptFile(**d)


def load_prompts_from_dir(root: str | Path, language: Optional[str] = None) -> List[PromptFile]:
    files = _discover_yaml_files(root, language=language)
    out: List[PromptFile] = []
    for p in files:
        try:
            data = _load_yaml(p)
            pf = _to_promptfile(data)
            out.append(pf)
        except Exception as e:
            LOGGER.exception("Failed to load %s: %s", p, e)
    return out


# ===== DB 비교/업서트 =====
async def _fetch_existing(
    session: AsyncSession, *, key: str, version: str, language: Optional[str]
) -> Optional[PromptORM]:
    q: Select = select(PromptORM).where(
        PromptORM.prompt_key == key,
        PromptORM.prompt_version == version,
        # 존재 여부 판단에서 is_active를 걸면 비활성 레코드가 있을 때 중복 판단이 어긋날 수 있음.
        # 필요 시 아래 한 줄을 해제해도 무방하지만, 통상 존재 확인은 상태와 분리하는 것이 안전하다.
        # PromptORM.is_active.is_(True),
    )
    if language is None:
        q = q.where(PromptORM.language.is_(None))
    else:
        q = q.where(PromptORM.language == language)
    res = await session.execute(q.limit(1))
    return res.scalars().first()


def _row_dict(row: PromptORM) -> Dict[str, Any]:
    return dict(
        prompt_key=row.prompt_key,
        prompt_version=row.prompt_version,
        language=row.language,
        prompt_type=row.prompt_type,
        messages=row.messages,
        template=row.template,
        params=row.params,
        json_schema_key=row.json_schema_key,
        required_vars=row.required_vars,
        is_active=row.is_active,
    )


def _pf_dict(pf: PromptFile) -> Dict[str, Any]:
    return dict(
        prompt_key=pf.key,
        prompt_version=pf.version,
        language=pf.language,
        prompt_type=pf.prompt_type,
        messages=pf.messages,
        template=pf.template,
        params=pf.params or {},
        json_schema_key=pf.json_schema_key,
        required_vars=pf.required_vars or [],
        is_active=True,
    )


def _is_changed(existing: PromptORM, pf: PromptFile) -> bool:
    a = _row_dict(existing)
    b = _pf_dict(pf)
    # JSON 비교를 위해 문자열화(키 순서 영향 제거)
    j_a = json.dumps(a, sort_keys=True, ensure_ascii=False)
    j_b = json.dumps(b, sort_keys=True, ensure_ascii=False)
    return j_a != j_b


async def upsert_prompt(session: AsyncSession, pf: PromptFile) -> Tuple[str, str]:
    """
    반환: ("created"|"updated"|"unchanged", message)
    """
    existing = await _fetch_existing(session, key=pf.key, version=pf.version, language=pf.language)
    values = _pf_dict(pf)

    if existing and not _is_changed(existing, pf):
        return "unchanged", f"{pf.key}/{pf.version}/{pf.language or '∅'}"

    ins = pg_insert(PromptORM).values(**values)

    # 언어 NULL/NOT NULL에 따라 유니크 인덱스가 다름 (partial unique + 일반 unique)
    if pf.language is None:
        stmt = ins.on_conflict_do_update(
            index_elements=[PromptORM.prompt_key, PromptORM.prompt_version],
            index_where=PromptORM.language.is_(None),
            set_={
                "prompt_type": values["prompt_type"],
                "messages": values["messages"],
                "template": values["template"],
                "params": values["params"],
                "json_schema_key": values["json_schema_key"],
                "required_vars": values["required_vars"],
                "is_active": values["is_active"],
                "updated_at": text("NOW()"),
            },
        )
    else:
        stmt = ins.on_conflict_do_update(
            index_elements=[PromptORM.prompt_key, PromptORM.prompt_version, PromptORM.language],
            index_where=PromptORM.language.is_not(None),  # ⭐ 부분 인덱스와 일치하도록 추가
            set_={
                "prompt_type": values["prompt_type"],
                "messages": values["messages"],
                "template": values["template"],
                "params": values["params"],
                "json_schema_key": values["json_schema_key"],
                "required_vars": values["required_vars"],
                "is_active": values["is_active"],
                "updated_at": text("NOW()"),
            },
        )

    await session.execute(stmt)
    if existing:
        return "updated", f"{pf.key}/{pf.version}/{pf.language or '∅'}"
    return "created", f"{pf.key}/{pf.version}/{pf.language or '∅'}"


async def sync_prompts_to_db(
    *,
    root: str | Path = PROMPT_ROOT,
    language: Optional[str] = None,
    dry_run: bool = False,
) -> SyncStats:
    stats = SyncStats()
    prompts = load_prompts_from_dir(root, language=language)
    LOGGER.info("Discovered %d prompt file(s) under %s", len(prompts), root)

    async with SessionLocal() as session:
        for pf in prompts:
            try:
                if dry_run:
                    # 드라이런: 변경 여부만 계산
                    existing = await _fetch_existing(session, key=pf.key, version=pf.version, language=pf.language)
                    if existing is None:
                        stats.created += 1
                        LOGGER.info("[DRY] create: %s/%s/%s", pf.key, pf.version, pf.language or "∅")
                    elif _is_changed(existing, pf):
                        stats.updated += 1
                        LOGGER.info("[DRY] update: %s/%s/%s", pf.key, pf.version, pf.language or "∅")
                    else:
                        stats.unchanged += 1
                        LOGGER.debug("[DRY] unchanged: %s/%s/%s", pf.key, pf.version, pf.language or "∅")
                    continue

                status, msg = await upsert_prompt(session, pf)
                if status == "created":
                    stats.created += 1
                    LOGGER.info("created: %s", msg)
                elif status == "updated":
                    stats.updated += 1
                    LOGGER.info("updated: %s", msg)
                else:
                    stats.unchanged += 1
                    LOGGER.debug("unchanged: %s", msg)

            except Exception as e:
                stats.failed += 1
                LOGGER.exception("Failed to upsert %s/%s/%s: %s", pf.key, pf.version, pf.language or "∅", e)
                # 🔑 실패 시 트랜잭션 상태 해제 (연쇄 InFailedSQLTransaction 방지)
                try:
                    await session.rollback()
                except Exception:
                    LOGGER.exception("Rollback failed (ignored).")

        if not dry_run:
            try:
                await session.commit()
            except Exception:
                LOGGER.exception("Commit failed; rolling back.")
                await session.rollback()
                # 실패 건수가 이미 카운트되어 있으므로 추가 조치는 생략

    LOGGER.info(
        "Sync done. created=%d updated=%d unchanged=%d failed=%d",
        stats.created,
        stats.updated,
        stats.unchanged,
        stats.failed,
    )
    return stats


def _resolve_path(key: str, version: str, language: Optional[str]) -> Optional[Path]:
    lang = language or "ko"
    p = PROMPT_ROOT / lang / f"{key}.{version}.yaml"
    return p if p.exists() else None


def _stable_hash(obj: Any) -> str:
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


async def fast_sync_one(key: str, version: str, language: Optional[str]) -> Optional[int]:
    """
    해당 key/version/lang에 해당하는 YAML만 읽어서 DB 업서트.
    파일이 없으면 None 반환(조용히 스킵).
    """
    path = _resolve_path(key, version, language)
    if not path:
        return None

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pf = PromptFile(**data)

    # DB 저장 형태로 정규화
    row: Dict[str, Any] = {
        "key": pf.key,
        "version": pf.version,
        "language": pf.language or language,  # 우선순위: 파일 > 호출 인자
        "prompt_type": pf.prompt_type,
        "messages": pf.messages,
        "template": pf.template,
        "params": pf.params or {},
        "json_schema_key": pf.json_schema_key,
        "required_vars": pf.required_vars or [],
    }
    chash = _stable_hash(
        {
            "prompt_type": row["prompt_type"],
            "messages": row["messages"],
            "template": row["template"],
            "params": row["params"],
            "json_schema_key": row["json_schema_key"],
            "required_vars": row["required_vars"],
        }
    )

    async for session in get_session():
        repo = PromptRepository(session)
        pid = await repo.upsert_one(
            key=row["key"],
            version=row["version"],
            language=row["language"],
            prompt_type=row["prompt_type"],
            messages=row["messages"],
            template=row["template"],
            params=row["params"],
            json_schema_key=row["json_schema_key"],
            required_vars=row["required_vars"],
            content_hash=chash,
            is_active=True,
        )
        return pid
    return None


# ===== CLI =====
def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Sync YAML prompts into DB (prompts table).")
    ap.add_argument("--root", default=PROMPT_ROOT, help="Root directory of YAML prompts (default: src/prompts)")
    ap.add_argument("--lang", default=None, help="Language filter (e.g., ko, en)")
    ap.add_argument("--dry-run", action="store_true", help="Do not write to DB; only show what would change")
    return ap.parse_args()


def main() -> None:
    args = _parse_args()
    asyncio.run(
        sync_prompts_to_db(
            root=args.root,
            language=args.lang,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
