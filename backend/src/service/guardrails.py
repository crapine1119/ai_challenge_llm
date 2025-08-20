from typing import List, Tuple

from domain.guardrail.ports import InputGuardPort, OutputGuardPort
from domain.guardrail.types import Action, Decision


class GuardrailPipeline:
    def __init__(self, inputs: List[InputGuardPort], outputs: List[OutputGuardPort]):
        self.input_guards = inputs
        self.output_guards = outputs

    async def pre_input(self, text: str) -> Tuple[str, Decision]:
        current = text
        agg_findings = []
        final_action = Action.ALLOW
        last_decision = Decision(action=Action.ALLOW, findings=[])

        for g in self.input_guards:
            d = await g.assess(current)
            agg_findings += d.findings
            last_decision = d
            if d.action == Action.BLOCK:
                return current, Decision(action=Action.BLOCK, findings=agg_findings, message=d.message)
            if d.action == Action.SANITIZE and d.sanitized_text:
                current = d.sanitized_text
                final_action = Action.SANITIZE
        return current, Decision(action=final_action, findings=agg_findings)

    async def post_output(self, text: str) -> Tuple[str, Decision]:
        current = text
        agg_findings = []
        final_action = Action.ALLOW
        last_decision = Decision(action=Action.ALLOW, findings=[])

        for g in self.output_guards:
            d = await g.assess(current)
            agg_findings += d.findings
            last_decision = d
            if d.action == Action.BLOCK:
                return current, Decision(action=Action.BLOCK, findings=agg_findings, message=d.message)
            if d.action == Action.SANITIZE and d.sanitized_text:
                current = d.sanitized_text
                final_action = Action.SANITIZE
        return current, Decision(action=final_action, findings=agg_findings)
