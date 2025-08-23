# src/infrastructure/queue/repo.py
import asyncio
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

from infrastructure.queue.models import QueueItem, Status, UserWindow, QueueSnapshot


@dataclass
class _UserQueues:
    queued: Deque[str]
    inflight: int


class IQueueRepo:
    """
    저장소 포트(인터페이스).
    """

    async def add(self, item: QueueItem) -> None: ...
    async def get(self, request_id: str) -> Optional[QueueItem]: ...
    async def mark_admitted(self, request_id: str) -> Optional[QueueItem]: ...
    async def mark_finished(self, request_id: str, ok: bool, reason: Optional[str]) -> Optional[QueueItem]: ...
    async def cancel(self, request_id: str, reason: str) -> Optional[QueueItem]: ...
    async def dequeue_for_user(self, user_id: str) -> Optional[str]: ...
    async def peek_user_queue(self, user_id: str) -> Optional[str]: ...
    async def list_user_ids(self) -> List[str]: ...
    async def inflight_count_global(self) -> int: ...
    async def inflight_count_user(self, user_id: str) -> int: ...
    async def stats_snapshot(self, avg_finish_sec: Optional[float]) -> QueueSnapshot: ...
    async def user_queue_ids(self, user_id: str) -> List[str]: ...


class InMemoryQueueRepo(IQueueRepo):
    """
    프로덕션 전, 단일 프로세스용 InMemory 저장소.
    멀티워커/멀티프로세스 환경에선 Redis/ZooKeeper 등으로 대체 필요.
    """

    def __init__(self) -> None:
        self._items: Dict[str, QueueItem] = {}
        self._by_user: Dict[str, _UserQueues] = defaultdict(lambda: _UserQueues(deque(), 0))
        self._lock = asyncio.Lock()

    async def add(self, item: QueueItem) -> None:
        async with self._lock:
            self._items[item.request_id] = item
            self._by_user[item.user_id].queued.append(item.request_id)

    async def get(self, request_id: str) -> Optional[QueueItem]:
        async with self._lock:
            return self._items.get(request_id)

    async def _pop_from_user(self, user_id: str) -> Optional[str]:
        uq = self._by_user.get(user_id)
        if not uq or not uq.queued:
            return None
        return uq.queued.popleft()

    async def dequeue_for_user(self, user_id: str) -> Optional[str]:
        async with self._lock:
            return await self._pop_from_user(user_id)

    async def peek_user_queue(self, user_id: str) -> Optional[str]:
        async with self._lock:
            uq = self._by_user.get(user_id)
            if not uq or not uq.queued:
                return None
            return uq.queued[0]

    async def mark_admitted(self, request_id: str) -> Optional[QueueItem]:
        async with self._lock:
            item = self._items.get(request_id)
            if not item or item.status != Status.queued:
                return item
            item.status = Status.inflight
            from datetime import datetime, timezone

            item.admitted_at = datetime.now(timezone.utc)
            self._by_user[item.user_id].inflight += 1
            return item

    async def mark_finished(self, request_id: str, ok: bool, reason: Optional[str]) -> Optional[QueueItem]:
        async with self._lock:
            item = self._items.get(request_id)
            if not item or item.status not in (Status.inflight, Status.queued):
                return item  # 이미 종료/취소/만료

            from datetime import datetime, timezone

            item.status = Status.finished if ok else Status.failed
            item.finished_at = datetime.now(timezone.utc)
            item.fail_reason = None if ok else (reason or "failed")

            # inflight 감소
            uq = self._by_user.get(item.user_id)
            if uq and uq.inflight > 0:
                uq.inflight -= 1
            return item

    async def cancel(self, request_id: str, reason: str) -> Optional[QueueItem]:
        async with self._lock:
            item = self._items.get(request_id)
            if not item or item.status != Status.queued:
                return item
            item.status = Status.canceled
            item.fail_reason = reason
            # 대기열에서 제거 필요: deque에서 해당 ID 제거
            uq = self._by_user.get(item.user_id)
            if uq:
                try:
                    uq.queued.remove(request_id)
                except ValueError:
                    pass
            return item

    async def inflight_count_global(self) -> int:
        async with self._lock:
            return sum(1 for it in self._items.values() if it.status == Status.inflight)

    async def inflight_count_user(self, user_id: str) -> int:
        async with self._lock:
            uq = self._by_user.get(user_id)
            return uq.inflight if uq else 0

    async def list_user_ids(self) -> List[str]:
        async with self._lock:
            return [u for u, uq in self._by_user.items() if uq.queued or uq.inflight]

    async def stats_snapshot(self, avg_finish_sec: Optional[float]) -> QueueSnapshot:
        from datetime import datetime, timezone

        async with self._lock:
            totals: Dict[str, int] = defaultdict(int)
            per_user_map: Dict[str, UserWindow] = {}

            for it in self._items.values():
                totals[it.status.value] += 1
                uw = per_user_map.setdefault(
                    it.user_id, UserWindow(user_id=it.user_id, queued=0, inflight=0, finished=0, failed=0, canceled=0)
                )
                if it.status == Status.queued:
                    uw.queued += 1
                elif it.status == Status.inflight:
                    uw.inflight += 1
                elif it.status == Status.finished:
                    uw.finished += 1
                elif it.status in (Status.failed, Status.expired):
                    uw.failed += 1
                elif it.status == Status.canceled:
                    uw.canceled += 1

            inflight_global = totals.get(Status.inflight.value, 0)
            return QueueSnapshot(
                ts=datetime.now(timezone.utc),
                totals=dict(totals),
                inflight_global=inflight_global,
                per_user=list(per_user_map.values()),
                avg_finish_sec=avg_finish_sec,
            )

    async def user_queue_ids(self, user_id: str) -> List[str]:
        async with self._lock:
            uq = self._by_user.get(user_id)
            return list(uq.queued) if uq else []
