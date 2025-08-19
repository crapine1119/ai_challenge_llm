from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class JobListItem:
    title: str
    href: str
    job_id: Optional[str]
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
