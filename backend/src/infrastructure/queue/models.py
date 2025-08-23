# src/infrastructure/queue/models.py
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, List

# Pydantic v2 / v1 호환
try:
    from pydantic import BaseModel, Field, ConfigDict, model_validator

    _V2 = True
except Exception:  # pragma: no cover
    from pydantic import BaseModel, Field  # type: ignore
    from pydantic import root_validator as model_validator  # type: ignore

    ConfigDict = None  # type: ignore
    _V2 = False


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Status(str, Enum):
    queued = "queued"
    inflight = "inflight"
    finished = "finished"
    failed = "failed"
    canceled = "canceled"
    expired = "expired"


class Limits(BaseModel):
    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    max_inflight_global: int = 16
    max_inflight_per_user: int = 2


class RequestInfo(BaseModel):
    """
    큐에 들어오는 클라이언트 요청 DTO.
    """

    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    request_id: str
    user_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0  # 현재 라운드로빈이라 우선순위는 사용하지 않지만 확장용
    created_at: datetime = Field(default_factory=utcnow)


class QueueItem(BaseModel):
    """
    내부 저장 모델(상태머신).
    """

    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    request_id: str
    user_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: Status = Status.queued
    enqueued_at: datetime = Field(default_factory=utcnow)
    admitted_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    fail_reason: Optional[str] = None
    # ETA 추정용
    eta_sec: Optional[float] = None


class UserWindow(BaseModel):
    """
    사용자별 관측 지표(스냅샷).
    """

    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    user_id: str
    queued: int = 0
    inflight: int = 0
    finished: int = 0
    failed: int = 0
    canceled: int = 0


class AdmitResult(BaseModel):
    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    admitted: List[QueueItem] = Field(default_factory=list)
    capacity_left: int = 0


class FinishResult(BaseModel):
    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    request_id: str
    status: Status
    duration_sec: Optional[float] = None


class QueueSnapshot(BaseModel):
    if _V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    ts: datetime = Field(default_factory=utcnow)
    totals: Dict[str, int] = Field(default_factory=dict)  # by Status
    inflight_global: int = 0
    per_user: List[UserWindow] = Field(default_factory=list)
    # 간단 ETA(최근 완료 평균)
    avg_finish_sec: Optional[float] = None
