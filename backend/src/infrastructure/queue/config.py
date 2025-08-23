# src/infrastructure/queue/config.py
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class QueueConfig:
    # 글로벌/유저 동시실행 제한
    max_inflight_global: int = 16
    max_inflight_per_user: int = 2
    # 한번에 admit 시도할 최대 개수(스케줄러 루프에서 사용)
    admit_batch_size: int = 64
    # 대기열 TTL(초) — 오래된 요청 자동 취소
    queued_ttl_sec: int = 60 * 30  # 30분
    # 추정 ETA 샘플 개수(완료 시간 평균을 낼 때 사용)
    eta_window: int = 50
    # 메트릭 백엔드: "noop" | "prom"
    metrics_backend: str = "noop"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def load_queue_config() -> QueueConfig:
    return QueueConfig(
        max_inflight_global=_int_env("QUEUE_MAX_INFLIGHT", 16),
        max_inflight_per_user=_int_env("QUEUE_USER_MAX_INFLIGHT", 2),
        admit_batch_size=_int_env("QUEUE_ADMIT_BATCH", 64),
        queued_ttl_sec=_int_env("QUEUE_TTL_SEC", 1800),
        eta_window=_int_env("QUEUE_ETA_WINDOW", 50),
        metrics_backend=os.getenv("QUEUE_METRICS", "noop").lower(),
    )
