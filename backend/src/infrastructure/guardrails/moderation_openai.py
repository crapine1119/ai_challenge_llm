import os

from openai import AsyncOpenAI

from domain.guardrail.ports import InputGuardPort, OutputGuardPort
from domain.guardrail.types import Decision, Finding, Action

MODEL = os.getenv("OPENAI_MODERATION_MODEL", "omni-moderation-latest")


class OpenAIModeration(InputGuardPort, OutputGuardPort):
    def __init__(self, threshold: float = 0.5):
        self.cli = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.threshold = threshold

    async def assess(self, text: str) -> Decision:
        # 간단 예시: OpenAI moderation(텍스트 안전성) 기준
        resp = await self.cli.moderations.create(model=MODEL, input=text)
        cat_scores = resp.results[0].category_scores  # dict[str,float]
        findings = [Finding(category=k, score=v, details={}) for k, v in cat_scores.items() if v >= self.threshold]
        if findings:
            return Decision(
                action=Action.BLOCK, findings=findings, message="안전 정책에 위배되는 내용이 포함되어 있습니다."
            )
        return Decision(action=Action.ALLOW, findings=[])
