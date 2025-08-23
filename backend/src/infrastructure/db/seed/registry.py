# src/infrastructure/db/seed/registry.py
import json
from importlib import resources
from typing import Iterable, List

from infrastructure.db.seed.schema import SeedBundle

_PACKAGE = "infrastructure.db.seed.data"


def list_seed_files() -> List[str]:
    # 패키지에 포함된 .json 파일 모두 로드 (예: core.v1.json)
    paths = []
    for entry in resources.files(_PACKAGE).iterdir():
        if entry.is_file() and entry.name.endswith(".json"):
            paths.append(entry.name)
    paths.sort()
    return paths


def load_seed_bundles() -> Iterable[SeedBundle]:
    for name in list_seed_files():
        with resources.as_file(resources.files(_PACKAGE) / name) as fp:
            raw = json.loads(fp.read_text(encoding="utf-8"))
            yield SeedBundle.model_validate(raw)
