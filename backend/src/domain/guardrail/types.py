from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class Action(str, Enum):
    ALLOW = "allow"
    SANITIZE = "sanitize"
    BLOCK = "block"

@dataclass
class Finding:
    category: str           # e.g., "pii", "toxicity", "prompt_injection"
    score: float            # 0~1
    details: Dict

@dataclass
class Decision:
    action: Action
    findings: List[Finding]
    message: Optional[str] = None      # 차단 사유/사용자 안내 메시지
    sanitized_text: Optional[str] = None
