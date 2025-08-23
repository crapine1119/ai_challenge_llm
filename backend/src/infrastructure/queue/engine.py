# src/infrastructure/queue/engine.py
import asyncio
import uuid
from datetime import timedelta
from typing import Optional, Dict, Any, List

from infrastructure.queue.config import QueueConfig
from infrastructure.queue.metrics import QueueMetrics, NoopQueueMetrics
from infrastructure.queue.models import (
    RequestInfo,
    QueueItem,
    Status,
    Limits,
    AdmitResult,
    FinishResult,
    QueueSnapshot,
)
from infrastructure.queue.repo import IQueueRepo, InMemoryQueueRepo
from infrastructure.queue.scheduler import RoundRobinScheduler


class QueueEngine:
    """
    상태머신(enqueue/admit/finish), ETA, snapshot.
    """

    def __init__(
        self,
        *,
        repo: Optional[IQueueRepo] = None,
        scheduler: Optional[RoundRobinScheduler] = None,
        config: Optional[QueueConfig] = None,
        metrics: Optional[QueueMetrics] = None,
    ) -> None:
        self.repo = repo or InMemoryQueueRepo()
        self.scheduler = scheduler or RoundRobinScheduler()
        self.config = config or QueueConfig()
        self.metrics = metrics or NoopQueueMetrics()

        self._eta_samples: List[float] = []  # 최근 완료 시간 샘플(초)
        self._lock = asyncio.Lock()

    # -------- public API --------

    async def enqueue(self, user_id: str, payload: Dict[str, Any]) -> RequestInfo:
        req = RequestInfo(request_id=str(uuid.uuid4()), user_id=user_id, payload=payload)
        item = QueueItem(request_id=req.request_id, user_id=req.user_id, payload=req.payload)
        await self.repo.add(item)
        self.metrics.observe_enqueue(user_id)
        return req

    async def admit(self) -> AdmitResult:
        limits = Limits(
            max_inflight_global=self.config.max_inflight_global,
            max_inflight_per_user=self.config.max_inflight_per_user,
        )
        # 만료 처리 먼저
        await self._expire_queued()

        ids = await self.scheduler.select_admissions(
            repo=self.repo, limits=limits, batch_max=self.config.admit_batch_size
        )
        admitted_items: List[QueueItem] = []
        for rid in ids:
            it = await self.repo.mark_admitted(rid)
            if it and it.status == Status.inflight:
                # 간단 ETA: 최근 평균 사용
                it.eta_sec = self._avg_eta()
                admitted_items.append(it)
                self.metrics.observe_admit(it.user_id)
        capacity_left = max(0, self.config.max_inflight_global - await self.repo.inflight_count_global())
        return AdmitResult(admitted=admitted_items, capacity_left=capacity_left)

    async def finish(self, request_id: str, ok: bool, reason: Optional[str] = None) -> FinishResult:
        it = await self.repo.mark_finished(request_id, ok=ok, reason=reason)
        if not it:
            return FinishResult(request_id=request_id, status=Status.canceled, duration_sec=None)

        dur = None
        if it.admitted_at and it.finished_at:
            dur = (it.finished_at - it.admitted_at).total_seconds()
            await self._push_eta_sample(dur)

        if ok:
            self.metrics.observe_finish(it.user_id, success=True, duration_sec=dur)
        else:
            self.metrics.observe_finish(it.user_id, success=False, duration_sec=dur)

        return FinishResult(request_id=request_id, status=it.status, duration_sec=dur)

    async def cancel(self, request_id: str, reason: str = "client_cancel") -> Status:
        it = await self.repo.cancel(request_id, reason)
        return it.status if it else Status.canceled

    async def status(self, request_id: str) -> Optional[QueueItem]:
        return await self.repo.get(request_id)

    async def snapshot(self) -> QueueSnapshot:
        snap = await self.repo.stats_snapshot(avg_finish_sec=self._avg_eta())
        self.metrics.gauge_inflight_global(snap.inflight_global)
        return snap

    # -------- internal helpers --------

    async def _expire_queued(self) -> None:
        """
        대기열 TTL 만료 처리.
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        ttl = timedelta(seconds=self.config.queued_ttl_sec)

        # 단순히 repo 내부 아이템을 순회해야 하지만 repo는 캡슐화되어 있음.
        # InMemory 구현에 한정해도 되지만, 범용성을 위해 공개 get()을 사용하고
        # user 목록 + peek/dequeue로 소거는 비용이 큼.
        # 여기서는 InMemory 전용 최적화 대신, "peek→시간 확인→취소" 접근을 반복.
        user_ids = await self.repo.list_user_ids()
        for uid in user_ids:
            # 여러 개 만료 가능 — 안전하게 반복
            while True:
                rid = await self.repo.peek_user_queue(uid)
                if not rid:
                    break
                it = await self.repo.get(rid)
                if not it:
                    break
                if (now - it.enqueued_at) > ttl:
                    await self.repo.cancel(rid, "ttl_expired")
                    self.metrics.observe_expire(uid)
                    continue
                break

    async def _push_eta_sample(self, dur: float) -> None:
        async with self._lock:
            self._eta_samples.append(dur)
            if len(self._eta_samples) > self.config.eta_window:
                self._eta_samples = self._eta_samples[-self.config.eta_window :]

    def _avg_eta(self) -> Optional[float]:
        if not self._eta_samples:
            return None
        return sum(self._eta_samples) / len(self._eta_samples)
