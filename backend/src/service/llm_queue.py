"""
단순 LLM 대기열/상태 서비스 (프로세스 메모리 기반)
- 사용자별 동시 처리 수(in-progress)
- 내 앞에 몇 명(옵션: request_id 제공 시)
- 평균 대기시간 ETA (사용자/글로벌 최근 처리시간 EMA 기반)
주의: 단일 프로세스에서만 일관. 배포 확장 시 Redis 등으로 교체 필요.
"""

import asyncio
import time
import uuid
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple


@dataclass
class RequestInfo:
    user_key: str
    request_id: str
    enqueued_at: float


@dataclass
class UserWindow:
    in_progress: int = 0
    queue: Deque[str] = field(default_factory=deque)  # request_id 순서
    ema_latency: float = 20.0  # 기본 평균 처리시간(초)
    last_finish: float = 0.0


class LLMQueueService:
    """
    간단한 라운드로빈 스케줄 + per-user 동시성 제한 + 글로벌 동시성 제한
    """

    def __init__(self, *, per_user_limit: int = 1, global_limit: int = 8, ema_alpha: float = 0.2):
        self.per_user_limit = per_user_limit
        self.global_limit = global_limit
        self.ema_alpha = ema_alpha

        self._users: Dict[str, UserWindow] = defaultdict(UserWindow)
        self._requests: Dict[str, RequestInfo] = {}
        self._admit_rr: Deque[str] = deque()  # 라운드로빈 사용자 키
        self._global_in_progress: int = 0

        self._lock = asyncio.Lock()

    # ---------- Enqueue / Admit / Finish ----------

    async def enqueue(self, user_key: str) -> Tuple[str, int]:
        """
        요청을 사용자 큐에 넣고 request_id와 큐 내 내 위치(0 기반)를 반환.
        """
        async with self._lock:
            req_id = uuid.uuid4().hex
            now = time.time()

            win = self._users[user_key]
            win.queue.append(req_id)
            if user_key not in self._admit_rr:
                self._admit_rr.append(user_key)

            self._requests[req_id] = RequestInfo(user_key=user_key, request_id=req_id, enqueued_at=now)
            pos = len(win.queue) - 1
            return req_id, pos

    async def try_admit_next(self) -> Optional[Tuple[str, str]]:
        """
        스케줄러: 가능한 경우 다음 요청을 승인 (user_key, request_id) 반환.
        없으면 None.
        """
        async with self._lock:
            if self._global_in_progress >= self.global_limit or not self._admit_rr:
                return None

            for _ in range(len(self._admit_rr)):
                user_key = self._admit_rr[0]
                win = self._users[user_key]

                # 비어 있거나 이미 상한이면 다음 사용자로
                if not win.queue or win.in_progress >= self.per_user_limit:
                    self._admit_rr.rotate(-1)
                    continue

                req_id = win.queue.popleft()
                win.in_progress += 1
                self._global_in_progress += 1

                # 사용자 큐가 비었으면 라운드로빈에서 제거
                if not win.queue:
                    self._admit_rr.popleft()
                else:
                    self._admit_rr.rotate(-1)

                return user_key, req_id

            return None

    async def finish(self, request_id: str, *, duration_sec: float) -> None:
        """
        처리 완료 보고: 동시성 카운터 감소 + EMA 업데이트
        """
        async with self._lock:
            info = self._requests.pop(request_id, None)
            if not info:
                return
            win = self._users.get(info.user_key)
            if not win:
                return

            # 카운터 감소
            if win.in_progress > 0:
                win.in_progress -= 1
            if self._global_in_progress > 0:
                self._global_in_progress -= 1

            # EMA 갱신
            alpha = self.ema_alpha
            win.ema_latency = alpha * duration_sec + (1 - alpha) * win.ema_latency
            win.last_finish = time.time()

            # 사용자 큐가 남아있다면 RR에 다시 넣음
            if win.queue and info.user_key not in self._admit_rr:
                self._admit_rr.append(info.user_key)

    # ---------- Status / ETA ----------

    async def my_status(self, user_key: str, request_id: Optional[str] = None) -> Dict[str, float | int]:
        """
        사용자/요청 기준 상태 스냅샷 제공.
        - in_progress_user / in_progress_global
        - position_in_user (request_id 없으면 0)
        - queue_len_user
        - eta_seconds (대략값: position / per_user_limit * ema_latency_user fallback global)
        """
        async with self._lock:
            win = self._users[user_key]
            pos = 0
            if request_id:
                # 사용자 큐에서 내 앞에 몇 명?
                try:
                    pos = list(win.queue).index(request_id)
                except ValueError:
                    pos = 0  # 큐에 없으면 진행 중 or 이미 완료로 간주

            # ETA 계산
            avg = win.ema_latency or 20.0
            per_user_parallel = max(self.per_user_limit, 1)
            eta = (pos / per_user_parallel) * avg

            return {
                "per_user_limit": self.per_user_limit,
                "global_limit": self.global_limit,
                "in_progress_user": win.in_progress,
                "in_progress_global": self._global_in_progress,
                "queue_len_user": len(win.queue),
                "position_in_user": pos,
                "eta_seconds": round(eta, 1),
            }

    async def snapshot(self) -> Dict[str, Dict[str, float | int]]:
        """
        전체 사용자 상태 요약(간단 통계용).
        """
        async with self._lock:
            summary = {}
            for user_key, win in self._users.items():
                summary[user_key] = {
                    "in_progress": win.in_progress,
                    "queue_len": len(win.queue),
                    "ema_latency": round(win.ema_latency, 2),
                }
            summary["_global"] = {
                "in_progress": self._global_in_progress,
                "users": len(self._users),
            }
            return summary
