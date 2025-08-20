import re

from domain.guardrail.ports import InputGuardPort, OutputGuardPort
from domain.guardrail.types import Decision, Finding, Action

PHONE_RE = re.compile(r"\b01[0-9]-?\d{3,4}-?\d{4}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class SimplePIIScrubber(InputGuardPort, OutputGuardPort):
    def __init__(self, mask_token: str = "[REDACTED]"):
        self.mask = mask_token

    async def assess(self, text: str) -> Decision:
        findings = []
        sanitized = text

        # 전화번호
        if PHONE_RE.search(text):
            sanitized = PHONE_RE.sub(self.mask, sanitized)
            findings.append(Finding(category="pii.phone", score=1.0, details={}))

        # 이메일
        if EMAIL_RE.search(text):
            sanitized = EMAIL_RE.sub(self.mask, sanitized)
            findings.append(Finding(category="pii.email", score=1.0, details={}))

        if findings and sanitized != text:
            return Decision(action=Action.SANITIZE, findings=findings, sanitized_text=sanitized)
        return Decision(action=Action.ALLOW, findings=findings)
