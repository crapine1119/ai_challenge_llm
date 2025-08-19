import time
import hashlib
import requests
from dataclasses import dataclass
from typing import Optional

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str
    headers: dict
    content_hash: str


class HttpClient:
    """
    - 공통 헤더/Referer
    - 예의상 지연(sleep)
    - 간단 재시도(backoff)
    """

    def __init__(self, timeout: int = 20, sleep: float = 0.6, retries: int = 2, backoff: float = 0.7):
        self.session = requests.Session()
        self.timeout = timeout
        self.sleep = sleep
        self.retries = retries
        self.backoff = backoff

    def get(self, url: str, *, headers: Optional[dict] = None, referer: Optional[str] = None) -> FetchResult:
        h = dict(DEFAULT_HEADERS)
        if headers:
            h.update(headers)
        if referer:
            h["Referer"] = referer

        last_err = None
        for attempt in range(self.retries + 1):
            try:
                r = self.session.get(url, headers=h, timeout=self.timeout)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
                time.sleep(self.sleep)
                text = r.text
                ch = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
                return FetchResult(
                    url=url, status_code=r.status_code, text=text, headers=dict(r.headers), content_hash=ch
                )
            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(self.backoff * (attempt + 1))
                else:
                    raise
        raise last_err  # 방어적
