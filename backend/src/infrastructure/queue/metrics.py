# src/infrastructure/queue/metrics.py
from abc import ABC, abstractmethod
from typing import Optional

# Prometheus가 있으면 사용, 없으면 noop로 동작
try:
    from prometheus_client import Counter, Gauge, Histogram  # type: ignore

    _PROM = True
except Exception:  # pragma: no cover
    _PROM = False


class QueueMetrics(ABC):
    @abstractmethod
    def observe_enqueue(self, user_id: str) -> None: ...

    @abstractmethod
    def observe_admit(self, user_id: str) -> None: ...

    @abstractmethod
    def observe_finish(self, user_id: str, *, success: bool, duration_sec: Optional[float]) -> None: ...

    @abstractmethod
    def gauge_inflight_global(self, n: int) -> None: ...

    @abstractmethod
    def observe_expire(self, user_id: str) -> None: ...


class NoopQueueMetrics(QueueMetrics):
    def observe_enqueue(self, user_id: str) -> None:  # pragma: no cover
        pass

    def observe_admit(self, user_id: str) -> None:  # pragma: no cover
        pass

    def observe_finish(self, user_id: str, *, success: bool, duration_sec: Optional[float]) -> None:  # pragma: no cover
        pass

    def gauge_inflight_global(self, n: int) -> None:  # pragma: no cover
        pass

    def observe_expire(self, user_id: str) -> None:  # pragma: no cover
        pass


class PrometheusQueueMetrics(QueueMetrics):
    def __init__(self) -> None:
        if not _PROM:  # pragma: no cover
            raise RuntimeError("prometheus_client is not installed")

        self.enqueued = Counter("queue_enqueued_total", "Total enqueued items", ["user"])
        self.admitted = Counter("queue_admitted_total", "Total admitted items", ["user"])
        self.finished = Counter(
            "queue_finished_total",
            "Total finished items by status",
            ["user", "status"],  # status: success|failed
        )
        self.inflight_gauge = Gauge("queue_inflight_global", "Current global inflight")
        self.expired = Counter("queue_expired_total", "Total expired items", ["user"])
        self.latency = Histogram(
            "queue_duration_seconds",
            "Duration from admit to finish in seconds",
            buckets=(0.1, 0.3, 1, 3, 5, 10, 20, 30, 60, 120, 300),
        )

    def observe_enqueue(self, user_id: str) -> None:
        self.enqueued.labels(user=user_id).inc()

    def observe_admit(self, user_id: str) -> None:
        self.admitted.labels(user=user_id).inc()

    def observe_finish(self, user_id: str, *, success: bool, duration_sec: Optional[float]) -> None:
        self.finished.labels(user=user_id, status="success" if success else "failed").inc()
        if duration_sec is not None:
            self.latency.observe(duration_sec)

    def gauge_inflight_global(self, n: int) -> None:
        self.inflight_gauge.set(n)

    def observe_expire(self, user_id: str) -> None:
        self.expired.labels(user=user_id).inc()
