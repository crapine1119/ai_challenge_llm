# -*- coding: utf-8 -*-
"""
JobKorea company recruit list -> detail crawler (SSR 링크 네비게이션 모방)

- 입력: company_id (예: 1517115)
- 동작:
  1) 회사 채용 리스트 페이지 GET (필터/정렬 쿼리 포함 가능)
  2) 리스트 HTML에서 상세 공고 링크(/Recruit/GI_Read/{id}?...) 추출
  3) 각 상세 페이지 GET 후 핵심 정보(title, location, career, dates 등) 파싱
- 필요: pip install requests beautifulsoup4
"""

import time
import urllib.parse as urlparse
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

from backend.data.crawl_jd_text import parse_gi_read

BASE = "https://www.jobkorea.co.kr"
LIST_PATH_TMPL = "/company/{company_id}/Recruit"

HEADERS = {
    # 일반 브라우저 유저에이전트 사용 (차단 회피가 아니라 예의)
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

@dataclass
class JobListItem:
    title: str
    href: str               # absolute URL to detail
    job_id: Optional[str]   # GI_Read/{job_id}
    meta: Dict[str, str]    # e.g., location, career, etc.

@dataclass
class JobDetail:
    job_id: str
    title: str
    company: Optional[str]
    location: Optional[str]
    career: Optional[str]
    education: Optional[str]
    employment_type: Optional[str]
    salary: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description_text: Optional[str]  # plain text summary

def build_list_url(company_id: int, **params) -> str:
    """
    잡코리아 회사 채용 리스트 URL 구성.
    사이트가 사용하는 대표 파라미터 예:
      GI_Part_Code, Search_Order, ChkDispType, Part_Btn_Stat 등
    """
    path = LIST_PATH_TMPL.format(company_id=company_id)
    qs = {k: v for k, v in params.items() if v is not None}
    return urlparse.urljoin(BASE, path) + ("?" + urlparse.urlencode(qs) if qs else "")

def absolutize(href: str) -> str:
    return urlparse.urljoin(BASE, href)

def extract_job_id_from_detail_url(url: str) -> Optional[str]:
    # 예: https://www.jobkorea.co.kr/Recruit/GI_Read/47503224?Oem_Code=C1
    try:
        parts = urlparse.urlparse(url).path.strip("/").split("/")
        # ["Recruit", "GI_Read", "{id}"]
        if len(parts) >= 3 and parts[0].lower() == "recruit" and parts[1].lower() == "gi_read":
            return parts[2]
    except Exception:
        pass
    return None

def fetch_html(url: str, session: Optional[requests.Session] = None, sleep: float = 0.7) -> BeautifulSoup:
    sess = session or requests.Session()
    r = sess.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    time.sleep(sleep)  # 예의상 지연
    return BeautifulSoup(r.text, "html.parser")

def parse_list_items(soup: BeautifulSoup) -> List[JobListItem]:
    """
    리스트에서 공고 카드/행을 찾아 상세 링크를 수집합니다.
    - 구조는 페이지마다 조금 다를 수 있으므로, 'GI_Read'를 포함하는 <a>를 포괄적으로 탐색
    - 링크 주변 텍스트로 간단한 메타(지역, 경력 등)도 함께 추출
    """
    items: List[JobListItem] = []
    # 1) 모든 a 태그 중 상세로 보이는 것 선별
    for a in soup.select('a[href*="/Recruit/GI_Read/"]'):
        title = a.get_text(strip=True)
        if "프리랜서" in title or "전 직무" in title:
            continue

        href = absolutize(a.get("href"))
        job_id = extract_job_id_from_detail_url(href)
        if not job_id or not title:
            continue

        # 2) 간단 메타: 링크 부모/조상에 적힌 텍스트들 중 유용한 키워드를 heuristic 추출
        meta_text = " ".join(x.get_text(" ", strip=True) for x in [a.parent, a.find_parent()] if x)[:500]
        meta = {}
        for key in ["서울", "경기", "인천", "부산", "경력", "신입", "학력", "정규직", "계약직", "연봉", "급여", "D-"]:
            if key in meta_text:
                meta[key] = "Y"

        items.append(JobListItem(title=title, href=href, job_id=job_id, meta=meta))
    # 중복 제거(같은 공고가 상단/하단에 2곳 노출되는 경우)
    uniq = {}
    for it in items:
        uniq[it.href] = it
    return list(uniq.values())

def parse_detail(soup: BeautifulSoup, job_id: str) -> JobDetail:
    """
    상세 페이지에서 핵심 필드 파싱.
    - 제목/회사/지역/경력/학력/고용형태/급여/시작일/마감일/본문 요약 등
    - 마크업이 바뀔 수 있으므로 CSS 선택자를 느슨하게 구성
    """
    def text(sel_list: List[str]) -> Optional[str]:
        for sel in sel_list:
            el = soup.select_one(sel)
            if el:
                return el.get_text(" ", strip=True)
        return None

    title = text([
        "h1", "h2", ".tit", ".company .tit", "meta[property='og:title']"
    ]) or ""

    company = text([
        ".company", ".coName", ".tbCompany .co", ".giView h3", "a[href*='/Company/']"
    ])

    location = None
    # 상세 영역에 '지역' 라벨이 있는 경우
    for box in soup.select("section, .giView, .viewTb, .tbDetail, .tbSupport"):
        txt = box.get_text(" ", strip=True)
        if "지역" in txt and not location:
            # ' 서울시 서초구 ' 같은 첫 매칭 추출
            location = next((tok for tok in txt.split() if "서울" in tok or "경기" in tok or "부산" in tok), None)

    career = None
    for label in ["경력", "신입", "무관"]:
        if soup.find(string=lambda s: s and label in s):
            career = label
            break

    education = None
    for label in ["학력", "학력무관", "대졸", "초대졸", "고졸"]:
        if soup.find(string=lambda s: s and label in s):
            education = label
            break

    employment_type = None
    for label in ["정규직", "계약직", "인턴", "파견직", "프리랜서"]:
        if soup.find(string=lambda s: s and label in s):
            employment_type = label
            break

    salary = None
    for label in ["연봉", "급여", "회사내규"]:
        if soup.find(string=lambda s: s and label in s):
            salary = label
            break

    # 접수기간
    # 페이지에 "시작일", "마감일" 라벨이 명시되어 있음
    start_date = text([".tbSupport .td", ".support .date .start", "time.start"])
    end_date = None
    # '마감일' 혹은 달력 영역에서 날짜 문자열을 포괄적으로 추출
    for s in soup.find_all(string=True):
        if "마감일" in s:
            # 라벨 다음의 텍스트 일부를 추정
            parent_txt = s.parent.get_text(" ", strip=True) if getattr(s, "parent", None) else str(s)
            # 가장 간단히 숫자와 . 포함 토큰을 하나 추출
            import re
            m = re.search(r"(\d{4}\.\d{2}\.\d{2})", parent_txt)
            if m:
                end_date = m.group(1)
                break

    # 본문 요약(텍스트만)
    # 과도한 길이 방지 위해 앞부분 일부만
    desc_container = soup.select_one("#devContent, .tbDetail, .giView, article")
    description_text = desc_container.get_text("\n", strip=True)[:1500] if desc_container else None

    return JobDetail(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        career=career,
        education=education,
        employment_type=employment_type,
        salary=salary,
        start_date=start_date,
        end_date=end_date,
        description_text=description_text,
    )

def crawl_company_recruits(
    company_id: int,
    list_params: Optional[Dict[str, str]] = None,
    max_details: int = 20,
) -> Dict[str, List[Dict]]:
    """
    - list_params로 GI_Part_Code, Search_Order 등 필터/정렬을 그대로 전달 가능
    - 리스트에서 상세 링크를 모으고, 최대 max_details개 상세를 파싱
    """

    curr_list_url = build_list_url(company_id, **list_params, ChkDispType="1")
    prev_list_url = build_list_url(company_id, **list_params, ChkDispType="2")
    print(f"[LIST] {curr_list_url}")

    with requests.Session() as sess:
        curr_list_soup = fetch_html(curr_list_url, sess)
        curr_items = parse_list_items(curr_list_soup)

        prev_list_soup = fetch_html(prev_list_url, sess)
        prev_items = parse_list_items(prev_list_soup)
        print(f" - found {len(curr_items) + len(prev_items)} postings on list page")

        results = []
        for it in (curr_items + prev_items)[:max_details]:
            try:
                detail_soup = fetch_html(it.href, sess)
                detail = parse_detail(detail_soup, it.job_id or "")
            except:
                detail = None
                print(f"PARSE DETAIL FAILED: {it.title}")
            results.append({
                "item": it,
                "detail": detail
            })

        return results

if __name__ == "__main__":
    """
    - 인사담당자: 1000201
    - AI/ML엔지니어: 1000242
    - 백엔드개발자: 1000229
    - 프론트엔드개발자: 1000230
    - 마케팅기획: 1000187
    - 재무담당자: 1000210
    """


    # 실행 예시
    jd_page_list = crawl_company_recruits(
        company_id=1517115,
        list_params={
            "GI_Part_Code": "1000230",
            "Search_Order": "1",
            "Part_Btn_Stat": "0",
        },
        max_details=5,
    )

    for jd_page in jd_page_list:
        # d["item"]
        if it:=jd_page["item"]:
            href = it.href
            jd_data = parse_gi_read(href)
            print(jd_data["detail_text"])