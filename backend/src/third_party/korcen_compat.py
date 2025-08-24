"""
third_party/korcen_compat.py

역할:
- 우선 실제 패키지 `korcen`에서 `check`, `highlight_profanity`를 가져오고,
- 실패하면 vendored fallback(= korcen_fallback.py)로 대체.
- 호출부는 동일한 인터페이스(check(text), highlight_profanity(text, level='all'))만 알면 됨.
"""

try:
    # 1) 정식 배포본 우선
    from korcen.check import check as _k_check  # PyPI가 제공하는 불린 판정

    try:
        from korcen import highlight_profanity as _k_highlight  # 일부 배포본엔 없음

        HAS_HIGHLIGHT = True
    except Exception:
        _k_highlight = None
        HAS_HIGHLIGHT = False
    SOURCE = "korcen"
except Exception:
    # 2) 폴백: vendored 코드
    from .korcen_fallback import check as _k_check  # <- 당신이 제공한 코드 파일
    from .korcen_fallback import highlight_profanity as _k_highlight

    HAS_HIGHLIGHT = True
    SOURCE = "vendored-korcen"


def check(text: str) -> bool:
    """비속어 존재 여부(True/False)"""
    try:
        return bool(_k_check(text))
    except Exception:
        return False


def highlight(text: str, level: str = "all", marker: str = "▩") -> str:
    """감지된 표현을 표시(하이라이트/마스킹). 패키지에 없으면 원문 반환."""
    if not HAS_HIGHLIGHT or _k_highlight is None:
        return text
    try:
        return _k_highlight(text, level=level, highlight_char=marker)
    except Exception:
        return text
