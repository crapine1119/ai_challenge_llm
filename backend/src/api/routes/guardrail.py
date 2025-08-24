# api/routes/guardrail.py
from fastapi import APIRouter, Body

from service.guardrail import GuardrailService

router = APIRouter(prefix="/guardrail", tags=["guardrail"])
guardrail_service = GuardrailService()


@router.post("/check")
async def check_guardrail(payload: dict = Body(...)):
    """
    사용자가 입력한 JSON payload 내 텍스트에
    부적절한 단어가 포함되어 있는지 검사
    """
    result = guardrail_service.check_payload_rule(payload)
    return result
