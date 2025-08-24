# src/service/llm_queue.py
"""
단순 LLM 대기열/상태 서비스 (프로세스 메모리 기반)
- 사용자별 동시 처리 수(in-progress)
- 내 앞에 몇 명(옵션: request_id 제공 시)
- 평균 대기시간 ETA (사용자/글로벌 최근 처리시간 EMA 기반)
주의: 단일 프로세스에서만 일관. 배포 확장 시 Redis 등으로 교체 필요.

구현 메모:
- 내부 큐/스케줄/상태머신은 infrastructure.queue.* 모듈(Engine/Repo/Scheduler)을 사용합니다.
- per-user EMA(지수이동평균)는 이 퍼사드에서 관리합니다(Engine은 글로벌 평균만 집계).
- position_in_user 계산을 위해 Repo에 user_queue_ids(user_id) 메서드가 있으면 사용합니다.
  (없으면 0으로 폴백; InMemoryQueueRepo에는 구현 권장)
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List

from infrastructure.queue.config import load_queue_config
from infrastructure.queue.engine import QueueEngine
from infrastructure.queue.metrics import NoopQueueMetrics, PrometheusQueueMetrics
from infrastructure.queue.models import QueueItem
from infrastructure.queue.repo import InMemoryQueueRepo
from infrastructure.queue.scheduler import RoundRobinScheduler


# --- 간단 EMA 도우미 -----------------------------------------------------------


@dataclass
class _EMAEntry:
    value: float
    alpha: float


class _EMAStore:
    def __init__(self, *, default: float = 20.0, alpha: float = 0.2):
        self._default = default
        self._alpha = alpha
        self._by_user: Dict[str, _EMAEntry] = {}

    def update(self, user_id: str, sample: float) -> float:
        cur = self._by_user.get(user_id)
        if cur is None:
            cur = _EMAEntry(value=self._default, alpha=self._alpha)
        cur.value = cur.alpha * sample + (1.0 - cur.alpha) * cur.value
        self._by_user[user_id] = cur
        return cur.value

    def get(self, user_id: str) -> float:
        cur = self._by_user.get(user_id)
        return cur.value if cur else self._default

    def set_alpha(self, alpha: float) -> None:
        self._alpha = alpha
        for e in self._by_user.values():
            e.alpha = alpha


# --- LLMQueueService 퍼사드 ----------------------------------------------------
class LLMQueueService:
    """
    간단 라운드로빈 스케줄 + per-user/글로벌 동시성 제한.
    Engine(admit/finish/snapshot) 위에 얇은 편의 API를 제공합니다.
    """

    def __init__(
        self,
        *,
        per_user_limit: Optional[int] = None,
        global_limit: Optional[int] = None,
        ema_alpha: float = 0.2,
        use_prom_metrics: bool = False,
        engine: Optional[QueueEngine] = None,
    ):
        cfg = load_queue_config()
        if per_user_limit is not None:
            cfg = type(cfg)(
                max_inflight_global=global_limit if global_limit is not None else cfg.max_inflight_global,
                max_inflight_per_user=per_user_limit,
                admit_batch_size=cfg.admit_batch_size,
                queued_ttl_sec=cfg.queued_ttl_sec,
                eta_window=cfg.eta_window,
                metrics_backend=cfg.metrics_backend,
            )
        if global_limit is not None and per_user_limit is None:
            cfg = type(cfg)(
                max_inflight_global=global_limit,
                max_inflight_per_user=cfg.max_inflight_per_user,
                admit_batch_size=cfg.admit_batch_size,
                queued_ttl_sec=cfg.queued_ttl_sec,
                eta_window=cfg.eta_window,
                metrics_backend=cfg.metrics_backend,
            )

        metrics = PrometheusQueueMetrics() if use_prom_metrics or cfg.metrics_backend == "prom" else NoopQueueMetrics()

        self.engine: QueueEngine = engine or QueueEngine(
            repo=InMemoryQueueRepo(),
            scheduler=RoundRobinScheduler(),
            config=cfg,
            metrics=metrics,
        )

        # per-user EMA 저장 (Engine은 글로벌 평균만 집계)
        self._ema = _EMAStore(default=20.0, alpha=ema_alpha)

        # 내부 락: 퍼사드 수준 동시 호출 제어(옵션)
        self._lock = asyncio.Lock()

    # ---------- Enqueue / Admit / Finish ----------

    async def enqueue(self, user_key: str, payload: Optional[Dict[str, Any]] = None) -> Tuple[str, int]:
        """
        요청을 사용자 큐에 넣고 (request_id, 큐 내 내 위치 0기준)을 반환.
        """
        payload = payload or {}
        async with self._lock:
            req = await self.engine.enqueue(user_key, payload)
            # 위치 계산
            pos = await self._position_in_user(user_key, req.request_id)
            return req.request_id, pos

    async def try_admit_next(self) -> Optional[Tuple[str, str]]:
        """
        스케줄러: 가능한 경우 다음 요청을 승인하고 (user_key, request_id) 반환. 없으면 None.
        """
        # Engine은 batch admit를 수행하므로 한 번 호출에 여러 개 선점될 수 있음.
        res = await self.engine.admit()
        if not res.admitted:
            return None
        first = res.admitted[0]
        return first.user_id, first.request_id

    async def finish(
        self,
        request_id: str,
        *,
        duration_sec: Optional[float] = None,
        ok: bool = True,
        reason: str = "",
    ) -> None:
        """
        처리 완료 보고.
        - Engine.finish()를 호출하여 상태/지표 갱신
        - per-user EMA를 업데이트 (duration_sec 인자가 있으면 우선 사용, 없으면 Engine 측 계산값 사용)
        """
        # 완료 전 user_id를 조회(파이프라인 호환)
        item: Optional[QueueItem] = await self.engine.status(request_id)
        user_id = item.user_id if item else None

        result = await self.engine.finish(request_id, ok=ok, reason=reason)
        # EMA 업데이트
        if user_id:
            sample = duration_sec if duration_sec is not None else result.duration_sec
            if sample is not None:
                self._ema.update(user_id, sample)

    # ---------- Status / ETA ----------

    async def my_status(self, user_key: str, request_id: Optional[str] = None) -> Dict[str, float | int]:
        """
        사용자/요청 기준 상태 스냅샷 제공.
        - in_progress_user / in_progress_global
        - position_in_user (request_id 없으면 0)
        - queue_len_user
        - eta_seconds (대략값: position / per_user_limit * ema_latency_user, 없으면 글로벌 평균 폴백)
        """
        cfg = self.engine.config

        # 동시 실행 카운트
        in_prog_user = await self.engine.repo.inflight_count_user(user_key)
        in_prog_global = await self.engine.repo.inflight_count_global()

        # 큐 정보
        queue_ids = await self._user_queue_ids(user_key)
        queue_len = len(queue_ids)

        # 내 위치
        pos = 0
        if request_id:
            try:
                pos = queue_ids.index(request_id)
            except ValueError:
                pos = 0  # 큐에 없으면 진행중/완료로 간주

        # ETA: per-user EMA 우선, 없으면 글로벌 평균
        ema_user = self._ema.get(user_key)
        global_eta = (await self.engine.snapshot()).avg_finish_sec
        avg = ema_user if ema_user else (global_eta or 20.0)

        per_user_parallel = max(cfg.max_inflight_per_user, 1)
        eta = (pos / per_user_parallel) * avg

        return {
            "per_user_limit": cfg.max_inflight_per_user,
            "global_limit": cfg.max_inflight_global,
            "in_progress_user": in_prog_user,
            "in_progress_global": in_prog_global,
            "queue_len_user": queue_len,
            "position_in_user": pos,
            "eta_seconds": round(float(eta), 1),
        }

    async def snapshot(self) -> Dict[str, Dict[str, float | int]]:
        """
        전체 사용자 상태 요약(간단 통계용).
        { user_key: { in_progress, queue_len, ema_latency }, "_global": { in_progress, users } }
        """
        # 사용자 목록을 Repo에서 직접 가져올 수 없으므로, snapshot(per_user 윈도우)이 제공되면 활용
        snap = await self.engine.snapshot()

        summary: Dict[str, Dict[str, float | int]] = {}
        for uw in snap.per_user:
            summary[uw.user_id] = {
                "in_progress": uw.inflight,
                "queue_len": uw.queued,
                "ema_latency": round(float(self._ema.get(uw.user_id)), 2),
            }

        summary["_global"] = {
            "in_progress": snap.inflight_global,
            "users": len(snap.per_user),
        }
        return summary

    # ---------- 내부 유틸 ----------

    async def _user_queue_ids(self, user_id: str) -> List[str]:
        """
        Repo가 user_queue_ids(user_id) API를 제공하면 사용하고, 없으면 빈 리스트 반환.
        (정확한 position 계산을 위해 InMemoryQueueRepo에 본 메서드 구현을 권장)
        """
        repo = self.engine.repo
        if hasattr(repo, "user_queue_ids"):
            return list(await repo.user_queue_ids(user_id))  # type: ignore[attr-defined]
        return []

    async def _position_in_user(self, user_id: str, request_id: str) -> int:
        ids = await self._user_queue_ids(user_id)
        try:
            return ids.index(request_id)
        except ValueError:
            # 이미 dequeue/진행중이면 0
            return 0
