from typing import Any, Dict, Iterator, List, Tuple, Union

from better_profanity import profanity

from third_party.korcen_compat import SOURCE as KORCEN_SOURCE
from third_party.korcen_compat import check as ko_check, highlight as ko_highlight

JsonLike = Union[Dict[str, Any], List[Any], str, int, float, bool, None]


def _iter_strings(obj: JsonLike, base_path: str = "$") -> Iterator[Tuple[str, str]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_strings(v, f"{base_path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _iter_strings(v, f"{base_path}[{i}]")
    elif isinstance(obj, str):
        yield base_path, obj


class GuardrailService:
    """패키지 기반 간단 가드레일 (korcen + better_profanity)."""

    def __init__(self) -> None:
        try:
            profanity.load_censor_words()
        except Exception:
            pass

    def check_payload_rule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        flags: List[Dict[str, Any]] = []
        for field_path, text in _iter_strings(payload):
            # EN: better-profanity
            try:
                if profanity.contains_profanity(text):
                    flags.append(
                        {
                            "lang": "en",
                            "field_path": field_path,
                            "original": text,
                            "masked": profanity.censor(text),
                            "library": "better-profanity",
                        }
                    )
            except Exception:
                pass

            # KO: korcen (정식 → 폴백)
            try:
                if ko_check(text):
                    flags.append(
                        {
                            "lang": "ko",
                            "field_path": field_path,
                            "original": text,
                            "masked": ko_highlight(text, level="all", marker="▩"),
                            "library": f"korcen ({KORCEN_SOURCE})",
                        }
                    )
            except Exception:
                pass

        ok = len(flags) == 0
        return {
            "ok": ok,
            "message": (
                "적절성 검사 통과"
                if ok
                else f"부적절한 표현이 감지되었습니다({len(flags)}건). 문구를 수정한 뒤 다시 시도해주세요."
            ),
            "flags": flags,
        }

    # TODO: possible to develop but additional experiments for model performance are required
    def check_payload_openai(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # client = OpenAI(api_key="sk...")
        # response = client.moderations.create(model="omni-moderation-latest", input=str(payload))  # 최신 moderation 모델
        # print(json.dumps(response.results[0].model_dump(), indent=2))
        pass
