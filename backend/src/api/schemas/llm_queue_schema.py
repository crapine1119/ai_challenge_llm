from typing import Optional, Dict, List, Literal, Union

from pydantic import BaseModel, Field, ConfigDict


class EnqueuedItem(BaseModel):
    request_id: str
    position: int


# 시뮬레이션 옵션
class SimOptions(BaseModel):

    model_config = ConfigDict(extra="forbid")
    fixed_sec: Optional[float] = Field(default=None, ge=0)
    min_sec: float = Field(default=3, ge=0)
    max_sec: float = Field(default=5, ge=0)


# “N명 대기 → 실제 생성 호출” 요청
# (JDGenerateRequest를 직접 import해도 되고, 스키마 결합을 줄이려면 Dict[str, Any]로 둬도 됩니다)
from api.schemas.jd_generation import JDGenerateRequest  # ← 기존 스키마 재사용


class SimThenGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prequeue_count: int = Field(default=10, ge=0, le=200)
    sim: SimOptions = Field(default_factory=SimOptions)
    jd: JDGenerateRequest  # 그대로 포워딩
    user_id: Optional[str] = None
    wait_timeout_sec: Optional[float] = Field(default=None, ge=1)


# 응답은 /jd/generate와 동일 스키마 사용
from api.schemas.jd_generation import JDGenerateResponse

SimThenGenerateResponse = JDGenerateResponse


class SimThenGenerateAsyncAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    status: Literal["accepted"]
    links: Dict[str, str] = Field(default_factory=dict)


# 라우터 데코레이터에서 아래 Union을 사용합니다.
SimThenGenerateAnyResponse = Union[JDGenerateResponse, SimThenGenerateAsyncAccepted]


# ---------- Queue State schema ----------
class UserWindowOut(BaseModel):
    user_id: str
    queued: int
    inflight: int
    finished: int
    failed: int
    canceled: int


class QueueSnapshotOut(BaseModel):
    ts: str
    totals: Dict[str, int]
    inflight_global: int
    avg_finish_sec: Optional[float] = None
    per_user: List[UserWindowOut] = Field(default_factory=list)


class QueueConfigOut(BaseModel):
    global_limit: int
    per_user_limit: int
    admit_batch_size: int
    queued_ttl_sec: int
    eta_window: int


class QueueStateResponse(BaseModel):
    config: "QueueConfigOut"
    snapshot: "QueueSnapshotOut"
    service_summary: Dict[str, Dict[str, int | float]]
    capacity_left: int
    # ▼ 단일 유저 대기 정보(요청하신 핵심 필드)
    user_id: str
    remaining_ahead: int  # 앞에 남은 인원(= 현재 queued 길이)
    eta_seconds: float  # 예상 대기 시간(초): queued/per_user_limit * EMA
    wait_percent: float  # 대기 진행률(%): since_ts 기준 경과시간/ETA


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    status: str  # queued|waiting|generating|finished|failed
    progress: float  # 0~100
    prequeue_done: int
    prequeue_total: int
    remaining_ahead: int  # 지금 앞에 남은(queued) 개수
    eta_seconds: float  # 내 차례까지 ETA(초)
    wait_percent: float  # 서버 자체 계산 대기 진행률(%)
    saved_id: Optional[int] = None
    error: Optional[str] = None
    links: Dict[str, str] = Field(default_factory=dict)
