import logging
import re
import urllib.parse as urlparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Iterable, Tuple

from bs4 import BeautifulSoup
from tqdm import tqdm

from infrastructure.http_client import HttpClient

BASE = "https://www.jobkorea.co.kr"
LIST_PATH_TMPL = "/company/{company_id}/Recruit"

DATE_PAT = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
EXCLUDE_HEADING_RE = re.compile(r"(유의\s*사항|꼭\s*읽어주세요|주의\s*사항|안내\s*사항)", re.I)
HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]


@dataclass
class JobListItem:
    title: str
    href: str  # absolute URL
    job_id: Optional[str]  # GI_Read/{job_id}
    meta: Dict[str, str]


@dataclass
class JobDetail:
    job_id: str
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    career: Optional[str]
    education: Optional[str]
    employment_type: Optional[str]
    salary: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    detail_html: Optional[str]
    detail_text: Optional[str]
    url: str
    iframe_url: Optional[str]


def _abs(href: str) -> str:
    return urlparse.urljoin(BASE, href)


def _extract_job_id(url: str) -> Optional[str]:
    try:
        parts = urlparse.urlparse(url).path.strip("/").split("/")
        if len(parts) >= 3 and parts[0].lower() == "recruit" and parts[1].lower() == "gi_read":
            return parts[2]
    except Exception:
        pass
    return None


def _norm(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return re.sub(r"\s+", " ", s).strip()


class JobKoreaCrawler:
    """
    - 회사 채용 리스트(진행/지난) 수집
    - 상세 페이지 파싱(iframe 포함)
    """

    def __init__(self, http: Optional[HttpClient] = None):
        self.http = http or HttpClient()

    def build_list_url(self, company_id: int, **params) -> str:
        path = LIST_PATH_TMPL.format(company_id=company_id)
        qs = {k: v for k, v in params.items() if v is not None}
        return urlparse.urljoin(BASE, path) + ("?" + urlparse.urlencode(qs) if qs else "")

    def parse_list_items(self, soup: BeautifulSoup) -> List[JobListItem]:
        items: List[JobListItem] = []
        for a in soup.select('a[href*="/Recruit/GI_Read/"]'):
            title = a.get_text(strip=True)
            if not title:
                continue
            if "프리랜서" in title or "전 직무" in title:
                continue
            href = _abs(a.get("href"))
            job_id = _extract_job_id(href)
            if not job_id:
                continue
            meta_text = " ".join(x.get_text(" ", strip=True) for x in [a.parent, a.find_parent()] if x)[:500]
            meta: Dict[str, str] = {}
            for key in [
                "서울",
                "경기",
                "인천",
                "부산",
                "경력",
                "신입",
                "학력",
                "정규직",
                "계약직",
                "연봉",
                "급여",
                "D-",
            ]:
                if key in meta_text:
                    meta[key] = "Y"
            items.append(JobListItem(title=title, href=href, job_id=job_id, meta=meta))
        return list({it.href: it for it in items}.values())

    @staticmethod
    def _text_one(soup: BeautifulSoup, selectors: Iterable[str]) -> Optional[str]:
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return _norm(el.get_text(" ", strip=True))
        return None

    @staticmethod
    def _company_from_main(soup: BeautifulSoup) -> Optional[str]:
        for sel in [".coInfo h4", ".coName", ".tbCompany .co", "h3", "h4", "a[href*='/Company/']"]:
            el = soup.select_one(sel)
            if el:
                t = _norm(el.get_text(" ", strip=True))
                if t and len(t) <= 80:
                    return t
        return None

    @staticmethod
    def _dates_from_main(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        start_date = end_date = None
        for node in soup.find_all(string=lambda x: x and ("시작일" in x or "마감일" in x)):
            parent_txt = node.parent.get_text(" ", strip=True) if node.parent else str(node)
            m = DATE_PAT.search(parent_txt)
            if not m:
                sib = node.find_next(string=DATE_PAT)
                if sib:
                    m = DATE_PAT.search(sib)
            if m:
                y, mo, d = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                ds = f"{y:04d}.{mo:02d}.{d:02d}"
                if "시작일" in node:
                    start_date = start_date or ds
                if "마감일" in node:
                    end_date = end_date or ds
        return start_date, end_date

    @staticmethod
    def _find_iframe_src(soup: BeautifulSoup) -> Optional[str]:
        iframe = soup.select_one("iframe#gib_frame")
        if iframe and iframe.has_attr("src"):
            return iframe["src"]
        cand = soup.select_one('iframe[src*="GI_Read_Comt_Ifrm"]')
        if cand and cand.has_attr("src"):
            return cand["src"]
        return None

    @staticmethod
    def _parse_iframe_detail(iframe_soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        candidates = [
            "#devContent",
            "#gibContent",
            "#giContent",
            ".giView",
            ".tbDetail",
            ".giDetail",
            "article",
            "section",
        ]
        for sel in candidates:
            cont = iframe_soup.select_one(sel)
            if cont and len(cont.get_text(strip=True)) > 30:
                return str(cont), cont.get_text("\n", strip=True)

        body = iframe_soup.body or iframe_soup
        for bad in body.select("style, script"):
            bad.decompose()

        headings = [h for h in body.find_all(HEADINGS) if _norm(h.get_text(" ", strip=True))]
        for h in headings:
            text = _norm(h.get_text(" ", strip=True))
            if text and EXCLUDE_HEADING_RE.search(text):
                for sib in list(h.next_siblings):
                    name = getattr(sib, "name", None)
                    if name in HEADINGS or name == "hr":
                        break
                    try:
                        sib.decompose()
                    except Exception:
                        pass
                try:
                    h.decompose()
                except Exception:
                    pass
        return str(body), body.get_text("\n", strip=True)

    def parse_detail(self, url: str) -> JobDetail:
        main_html = self.http.get(url).text
        main_soup = BeautifulSoup(main_html, "html.parser")

        og = main_soup.select_one('meta[property="og:title"]')
        title = _norm(og["content"]) if og and og.get("content") else None
        if not title:
            title = self._text_one(main_soup, ["h1", "h2", "title"])

        company = self._company_from_main(main_soup)
        start_date, end_date = self._dates_from_main(main_soup)

        career = education = employment_type = salary = None
        for label in ["경력", "신입", "무관"]:
            if main_soup.find(string=lambda s: s and label in s):
                career = label
                break
        for label in ["학력", "학력무관", "대졸", "초대졸", "고졸"]:
            if main_soup.find(string=lambda s: s and label in s):
                education = label
                break
        for label in ["정규직", "계약직", "인턴", "파견직", "프리랜서"]:
            if main_soup.find(string=lambda s: s and label in s):
                employment_type = label
                break
        for label in ["연봉", "급여", "회사내규"]:
            if main_soup.find(string=lambda s: s and label in s):
                salary = label
                break

        location = None
        for box in main_soup.select("section, .giView, .viewTb, .tbDetail, .tbSupport"):
            txt = box.get_text(" ", strip=True)
            if "지역" in txt and not location:
                location = next(
                    (tok for tok in txt.split() if any(k in tok for k in ["서울", "경기", "부산", "인천"])), None
                )

        iframe_src = self._find_iframe_src(main_soup)
        iframe_url = urlparse.urljoin(url, iframe_src) if iframe_src else None
        detail_html = detail_text = None
        if iframe_url:
            iframe_html = self.http.get(iframe_url, referer=url).text
            iframe_soup = BeautifulSoup(iframe_html, "html.parser")
            detail_html, detail_text = self._parse_iframe_detail(iframe_soup)

        job_id = _extract_job_id(url) or ""
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
            detail_html=detail_html,
            detail_text=detail_text,
            url=url,
            iframe_url=iframe_url,
        )

    def crawl_company_recruits(
        self,
        company_id: int,
        *,
        list_params: Optional[Dict[str, str]] = None,
        max_details: int = 5,
    ) -> List[Tuple[JobListItem, Optional[JobDetail]]]:
        list_params = list_params or {}
        curr_list_url = self.build_list_url(company_id, **list_params, ChkDispType="1")
        prev_list_url = self.build_list_url(company_id, **list_params, ChkDispType="2")
        logging.info(f"Crawl Page for {curr_list_url}")
        curr_items = self.parse_list_items(BeautifulSoup(self.http.get(curr_list_url).text, "html.parser"))
        prev_items = self.parse_list_items(BeautifulSoup(self.http.get(prev_list_url).text, "html.parser"))

        parsed_items = curr_items + prev_items

        if parsed_items:
            logging.info(f"Items for {company_id} are parsed ({len(parsed_items)})")

            results: List[Tuple[JobListItem, Optional[JobDetail]]] = []
            for it in tqdm(parsed_items[:max_details], postfix="Crawling..."):
                try:
                    detail = self.parse_detail(it.href)
                except Exception:
                    detail = None
                results.append((it, detail))
            return results
        else:
            logging.warning(
                f"It is Possible that connection for url ({curr_list_url}) is blocked.\nPlease Check connection with the browser."
            )


# if __name__ == "__main__":
#     import argparse
#     import json
#     import sys
#     from dataclasses import asdict
#     from urllib.parse import parse_qs
#
#     parser = argparse.ArgumentParser(description="JobKorea 회사 채용공고 크롤링 (리스트+상세 파싱)")
#     parser.add_argument("--company_id", type=int, help="JobKorea 회사 ID (예: 1517115)", default=1517115)
#     parser.add_argument("--max-details", type=int, default=20, help="수집할 최대 상세 건수")
#     parser.add_argument(
#         "--param",
#         action="append",
#         default=[],
#         help="리스트 쿼리 파라미터 (key=value 형태, 여러 번 지정 가능, 예: --param Page=1)",
#     )
#     parser.add_argument(
#         "--qs",
#         type=str,
#         default=None,
#         help="리스트 쿼리 파라미터 raw querystring (예: 'Page=1&CareerType=1')",
#     )
#     parser.add_argument("--pretty", action="store_true", help="JSON pretty 출력")
#     parser.add_argument(
#         "--out",
#         type=str,
#         default="-",
#         help="출력 경로 (기본: '-' → stdout). 파일 경로를 주면 파일로 저장",
#     )
#
#     args = parser.parse_args()
#
#     # list_params 병합 (qs → param 순으로 덮어씀)
#     list_params = {}
#     if args.qs:
#         for k, vlist in parse_qs(args.qs, keep_blank_values=True).items():
#             list_params[k] = vlist[-1] if vlist else ""
#     for kv in args.param:
#         if "=" in kv:
#             k, v = kv.split("=", 1)
#             list_params[k] = v
#
#     # 로깅
#     logging.basicConfig(
#         level=logging.INFO,
#         format="%(asctime)s %(levelname)s %(name)s: %(message)s",
#     )
#     logger = logging.getLogger("jobkorea_crawler.main")
#     logger.info(
#         "crawl.start company_id=%s max_details=%s list_params=%s",
#         args.company_id,
#         args.max_details,
#         list_params,
#     )
#
#     crawler = JobKoreaCrawler(http=HttpClient())
#     pairs = crawler.crawl_company_recruits(
#         company_id=args.company_id,
#         list_params=list_params,
#         max_details=args.max_details,
#     )
#
#     # 결과 직렬화
#     out = []
#     with_detail_text = 0
#     for li, detail in pairs:
#         if detail and detail.detail_text:
#             with_detail_text += 1
#         out.append(
#             {
#                 "list_item": asdict(li),
#                 "detail": asdict(detail) if detail else None,
#             }
#         )
#
#     payload = json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None)
#
#     if args.out == "-" or not args.out:
#         sys.stdout.write(payload + ("" if payload.endswith("\n") else "\n"))
#     else:
#         with open(args.out, "w", encoding="utf-8") as f:
#             f.write(payload)
#
#     logging.info(
#         "crawl.end total=%d with_detail_text=%d out=%s",
#         len(pairs),
#         with_detail_text,
#         args.out if args.out else "-",
#     )
