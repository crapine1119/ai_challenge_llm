import re
import json
import time
import argparse
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7",
}

DATE_PAT = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")

def fetch_soup(url: str, session: requests.Session, referer: str | None = None, sleep: float = 0.5) -> BeautifulSoup:
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    r = session.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    time.sleep(sleep)  # polite delay
    return BeautifulSoup(r.text, "html.parser")

def norm_ws(s: str | None) -> str | None:
    if not s:
        return None
    return re.sub(r"\s+", " ", s).strip()

def extract_dates_from_main(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    start_date = end_date = None
    # 접수기간 블록에서 '시작일', '마감일' 라벨 근처의 YYYY.MM.DD 추출
    for node in soup.find_all(string=lambda x: x and ("시작일" in x or "마감일" in x)):
        parent_txt = node.parent.get_text(" ", strip=True) if node.parent else str(node)
        m = DATE_PAT.search(parent_txt)
        if not m:
            sib = node.find_next(string=DATE_PAT)
            if sib:
                m = DATE_PAT.search(sib)
        if m:
            y, mo, d = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            date_str = f"{y:04d}.{mo:02d}.{d:02d}"
            if "시작일" in node:
                start_date = start_date or date_str
            if "마감일" in node:
                end_date = end_date or date_str
    return start_date, end_date

def extract_company_from_main(soup: BeautifulSoup) -> str | None:
    for sel in [".coInfo h4", ".coName", ".tbCompany .co", "h3", "h4"]:
        el = soup.select_one(sel)
        if el:
            text = norm_ws(el.get_text(" ", strip=True))
            if text and len(text) <= 80:
                return text
    return None

def find_iframe_src(soup: BeautifulSoup) -> str | None:
    # 우선 id가 확실한 프레임
    iframe = soup.select_one("iframe#gib_frame")
    if iframe and iframe.has_attr("src"):
        return iframe["src"]
    # 혹시 다른 이름으로 바뀐 경우를 대비해 GI_Read_Comt_Ifrm 포함 링크 탐색
    cand = soup.select_one('iframe[src*="GI_Read_Comt_Ifrm"]')
    if cand and cand.has_attr("src"):
        return cand["src"]
    return None

def parse_iframe_detail(iframe_soup: BeautifulSoup) -> dict:
    """
    iframe 내부에서 상세요강 본문 HTML/텍스트를 뽑는다.
    사이트 구조가 바뀔 수 있어, 여러 선택자를 시도 후 최종 fallback으로 <body> 사용.
    """
    # 흔히 본문 컨테이너로 쓰일만한 후보들
    candidates = [
        "#devContent", "#gibContent", "#giContent", ".giView", ".tbDetail",
        ".giDetail", "article", "section",
    ]
    html = text = None
    for sel in candidates:
        cont = iframe_soup.select_one(sel)
        if cont and len(cont.get_text(strip=True)) > 30:
            html = str(cont)
            text = cont.get_text("\n", strip=True)
            break
    if not html:
        body = iframe_soup.body or iframe_soup
        html = str(body)
        text = body.get_text("\n", strip=True)
    # 너무 긴 텍스트는 예시 출력에서 자름
    return {
        "detail_html": html,
        "detail_text": text[:4000],
    }

def parse_gi_read(url: str) -> dict:
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    with requests.Session() as sess:
        # 1) 메인 상세 페이지
        main_soup = fetch_soup(url, sess)

        # 제목(og:title 우선)
        og = main_soup.select_one('meta[property="og:title"]')
        title = norm_ws(og["content"]) if og and og.get("content") else None
        if not title:
            h = main_soup.select_one("h1, h2, title")
            title = norm_ws(h.get_text(" ", strip=True)) if h else None

        company = extract_company_from_main(main_soup)
        start_date, end_date = extract_dates_from_main(main_soup)

        # 2) 상세요강 iframe src 찾고, 해당 URL GET
        iframe_src = find_iframe_src(main_soup)
        iframe_data = None
        if iframe_src:
            iframe_url = urljoin(base, iframe_src)
            iframe_soup = fetch_soup(iframe_url, sess, referer=url)  # referer 넣어주는 게 안전
            iframe_data = parse_iframe_detail(iframe_soup)
        else:
            iframe_url = None

        return {
            "url": url,
            "title": title,
            "company": company,
            "start_date": start_date,
            "end_date": end_date,
            "iframe_url": iframe_url,
            **(iframe_data or {"detail_html": None, "detail_text": None}),
        }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    data = parse_gi_read(args.url)
    print(json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None))

if __name__ == "__main__":
    main()
