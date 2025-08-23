# src/infrastructure/queue/scheduler.py
import itertools
from typing import List, Optional

from infrastructure.queue.models import Limits
from infrastructure.queue.repo import IQueueRepo


class RoundRobinScheduler:
    """
    사용자별 라운드로빈 스케줄러.
    - 유저 목록을 순회하며 유저별 inflight < per_user_limit 일 때 한 건씩 선점
    - 글로벌 동시실행 한도까지 반복
    """

    def __init__(self) -> None:
        self._cursor_user: Optional[str] = None  # 페어니스 강화를 위한 라운드로빈 커서

    async def select_admissions(
        self,
        *,
        repo: IQueueRepo,
        limits: Limits,
        batch_max: int,
    ) -> List[str]:
        capacity = limits.max_inflight_global - await repo.inflight_count_global()
        capacity = max(0, min(capacity, batch_max))
        if capacity == 0:
            return []

        user_ids = await repo.list_user_ids()
        if not user_ids:
            return []

        # 커서 정렬: 마지막으로 사용한 사용자 다음부터
        if self._cursor_user and self._cursor_user in user_ids:
            start_idx = (user_ids.index(self._cursor_user) + 1) % len(user_ids)
            rr_order = user_ids[start_idx:] + user_ids[:start_idx]
        else:
            rr_order = list(user_ids)

        admitted_ids: List[str] = []
        # 라운드로빈 순회 반복
        for user_id in itertools.cycle(rr_order):
            if len(admitted_ids) >= capacity:
                break

            # 더 이상 대기열이 없으면 중단 조건
            peek = await repo.peek_user_queue(user_id)
            if peek is None:
                # 해당 유저가 더 이상 큐가 없으면 순열에서 제거
                rr_order = [u for u in rr_order if u != user_id]
                if not rr_order:
                    break
                continue

            # 유저별 동시실행 한도 체크
            u_inflight = await repo.inflight_count_user(user_id)
            if u_inflight >= limits.max_inflight_per_user:
                # 다음 유저
                continue

            # 유저 큐에서 하나 뽑기
            req_id = await repo.dequeue_for_user(user_id)
            if req_id is None:
                continue

            admitted_ids.append(req_id)
            self._cursor_user = user_id

        return admitted_ids
