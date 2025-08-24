"""
toy service to simulate delayed llm response situation
"""

import asyncio
import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Set
from typing import Optional, List, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.jd_generation import JDGenerateResponse
from api.schemas.llm_queue_schema import SimThenGenerateRequest, SimThenGenerateAnyResponse
from api.schemas.llm_queue_schema import TaskStatusResponse, SimThenGenerateAsyncAccepted
from domain.company_analysis.models import CompanyJDStyle
from infrastructure.db.repository import (
    StyleSnapshotRepository,
    DefaultStyleRepository,
)
from service.llm_queue import LLMQueueService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llm/queue", tags=["llm-queue"])
DEFAULT_USER_ID = "demo-user"


def _title_from_markdown(md: str, fallback: str) -> str:
    first = (md or "").splitlines()[0].strip()
    if first.startswith("#"):
        t = first.lstrip("#").strip()
        return t or fallback
    return fallback


async def _resolve_style_meta_for_saving(
    session: AsyncSession,
    *,
    style_override: Optional[CompanyJDStyle],
    style_source_req: str,
    default_style_name: Optional[str],
    company_code: str,
    job_code: str,
) -> dict:
    if style_override is not None:
        return {"style_source": "override", "style_preset_name": None, "style_snapshot_id": None}
    if style_source_req == "generated":
        snap = await StyleSnapshotRepository(session).latest_for(company_code=company_code, job_code=job_code)
        return {
            "style_source": "generated",
            "style_preset_name": None,
            "style_snapshot_id": (snap.id if snap else None),
        }
    name = default_style_name or "일반적"
    _ = await DefaultStyleRepository(session).get_preset(style_name=name)
    return {"style_source": "default", "style_preset_name": name, "style_snapshot_id": None}


# 아주 단순한 메모리 태스크 저장소
class TaskStore:
    def __init__(self) -> None:
        self.data: Dict[str, Dict[str, Any]] = {}

    def create(self, *, user_id: str, req_json: Dict[str, Any], stream_mode: bool = False) -> str:
        tid = str(uuid.uuid4())
        self.data[tid] = {
            "task_id": tid,
            "user_id": user_id,
            "status": "queued",  # queued|waiting|generating|finished|failed
            "created_at": time.time(),
            "finished_at": None,
            "error": None,
            "saved_id": None,
            "result": None,  # JDGenerateResponse
            "meta": {"pre_total": None, "pre_done": 0},
            "stream_mode": stream_mode,
        }
        return tid

    def get(self, tid: str) -> Optional[Dict[str, Any]]:
        return self.data.get(tid)

    def update(self, tid: str, **kwargs: Any) -> None:
        if tid in self.data:
            self.data[tid].update(kwargs)


class EventHub:
    """task_id별로 SSE 구독 큐를 관리하고 이벤트를 브로드캐스트"""

    def __init__(self):
        self._subs: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs.setdefault(task_id, set()).add(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
        try:
            self._subs.get(task_id, set()).discard(q)
        except Exception:
            pass

    async def publish(self, task_id: str, event_type: str, data: dict) -> None:
        payload = {"type": event_type, "data": data, "ts": time.time()}
        for q in list(self._subs.get(task_id, set())):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # 구독자 측이 느린 경우 드롭
                pass


def sse_bytes(event_type: str, data: dict) -> bytes:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


TASKS = TaskStore()
EVENT_HUB = EventHub()


# ---- 기존 시뮬 레Runtime(가짜 대기 처리) 재사용 ----
class SimQueueRuntime:
    def __init__(self, queue: LLMQueueService) -> None:
        self.queue = queue
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        # ▼ 진행률/ETA 자체 계산용 컨텍스트 (user_id별)
        #   { user_id: { "started_ts": float, "baseline_total": int } }
        self.progress_ctx: Dict[str, Dict[str, float | int]] = {}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop(), name="sim_queue_worker")

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                # 🔧 한 번에 여러 건 admit 가능 → 전부 실행으로 태움
                res = await self.queue.engine.admit()
                if not res.admitted:
                    await asyncio.sleep(0.2)
                    continue

                for it in res.admitted:
                    # it: QueueItem (request_id, user_id, payload 포함)
                    asyncio.create_task(self._run_one(it.request_id, dict(it.payload)))
            except Exception as e:
                logger.exception("워커 루프 오류: %s", e)
                await asyncio.sleep(0.5)

    async def _run_one(self, request_id: str, payload: Dict[str, Any]) -> None:

        t0 = time.perf_counter()
        ok = True
        err = None
        try:
            if not payload.get("simulate_only", False):
                raise ValueError("simulation-only queue")
            fixed = payload.get("sim_fixed_sec")
            if fixed is not None:
                delay = max(0.0, float(fixed))
            else:
                mi = float(payload.get("sim_min_sec", 5.0))
                ma = float(payload.get("sim_max_sec", 10.0))
                if ma < mi:
                    ma = mi
                delay = random.uniform(mi, ma)
            await asyncio.sleep(delay)
        except Exception as e:
            ok = False
            err = str(e)
        finally:
            await self.queue.finish(request_id, duration_sec=(time.perf_counter() - t0), ok=ok, reason=err or "")

    # ▼ 큐 길이 변화에 맞춰 baseline을 자동 관리
    def update_progress_ctx(self, *, user_id: str, queued: int, inflight: int) -> None:
        active = int(queued + inflight)

        # 큐가 비면 컨텍스트 리셋
        if active <= 0:
            self.progress_ctx.pop(user_id, None)
            return

        ctx = self.progress_ctx.get(user_id)
        if ctx is None:
            # 처음 관측 → baseline을 현재 작업량으로 시작
            self.progress_ctx[user_id] = {
                "started_ts": float(time.time()),
                "baseline_total": int(active),
            }
            return

        # 작업 도중 새로운 요청이 더 들어오면 baseline을 자연스럽게 확장
        base = int(ctx.get("baseline_total", 0))
        completed_so_far = max(0, base - active)
        # "현재 활성 + 지금까지 완료"가 기존 baseline보다 크면 baseline 상향
        new_base = max(base, active + completed_so_far)
        if new_base != base:
            ctx["baseline_total"] = new_base
            self.progress_ctx[user_id] = ctx


# DI
_queue_service = LLMQueueService()
_runtime = SimQueueRuntime(_queue_service)


async def init_llm_queue_runtime() -> None:  # lifespan에서 호출
    await _runtime.start()


async def shutdown_llm_queue_runtime() -> None:
    await _runtime.stop()


def get_runtime() -> SimQueueRuntime:
    return _runtime


# ---- 내부 유틸: 주어진 request_ids 모두 종료될 때까지 대기 ----
logger = logging.getLogger("llm_queue.wait")


async def _wait_all_finished(rt: SimQueueRuntime, ids: List[str], timeout: Optional[float]) -> None:
    start = time.perf_counter()
    interval = 2.0
    terminal = {"finished", "failed", "canceled", "expired"}

    while True:
        done = 0
        elapsed = time.perf_counter() - start
        summary_parts = []

        # 글로벌 평균(폴백)
        snap = await rt.queue.engine.snapshot()
        global_avg = float(snap.avg_finish_sec or 20.0)

        for rid in ids:
            it = await rt.queue.engine.status(rid)
            if not it:
                logger.info(f"[🟡 {rid}] 상태: 없음 | 경과시간: {elapsed:.2f}초")
                done += 1
                continue

            st = getattr(it.status, "value", str(it.status))
            eta = getattr(it, "eta_sec", None)

            # 🔧 평균 처리시간(1건) 추정: per-user EMA > 글로벌 평균
            try:
                avg_per_item = float(rt.queue._ema.get(it.user_id))
            except Exception:
                avg_per_item = global_avg
            if not avg_per_item or avg_per_item <= 0:
                avg_per_item = global_avg

            # 진행률 추정
            progress = None
            eta_remain = None

            if st == "queued":
                progress = 0
            elif st == "inflight":
                # admitted_at 기반 경과시간
                if it.admitted_at:
                    now = datetime.now(timezone.utc)
                    elapsed_inflight = max(0.0, (now - it.admitted_at).total_seconds())
                else:
                    elapsed_inflight = 0.0

                # 남은 시간/진행률 계산 (ETA 없을 땐 경과/평균으로)
                if eta is not None:
                    eta_remain = max(0.0, float(eta))
                else:
                    eta_remain = max(0.0, avg_per_item - elapsed_inflight)

                if avg_per_item > 0:
                    progress = int(min(95, max(1, (elapsed_inflight / avg_per_item) * 100)))
                else:
                    progress = 50
            elif st == "finished":
                progress = 100
                eta_remain = 0.0
            else:
                progress = None

            progress_str = f"{progress}%" if progress is not None else "N/A"
            eta_str = f" | 예상 남은시간: {eta_remain:.1f}초" if eta_remain is not None else ""

            logger.info(f"[🧩 {rid}] 상태: {st:<9} | 경과시간: {elapsed:.2f}초{eta_str} | 진행률: {progress_str}")

            summary_parts.append(f"{rid[-4:]}:{st[0].upper()}")
            if st in terminal:
                done += 1

        logger.info(f"⏳ 요약 [{elapsed:.1f}초]: " + " ".join(summary_parts))

        if done == len(ids):
            logger.info(f"✅ 총 {len(ids)}개의 요청이 {elapsed:.2f}초 만에 완료되었습니다.")
            return

        if timeout is not None and elapsed > timeout:
            logger.warning(f"❌ {elapsed:.2f}초 동안 {len(ids)}개의 요청 완료를 기다렸으나 타임아웃 발생.")
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="simulation wait timeout")

        await asyncio.sleep(interval)


async def _proxy_jd_stream_to_eventhub(*, task_id: str, base_url: str, jd_payload: dict) -> dict:
    """
    내부 /api/jd/generate/stream SSE를 열어 이벤트를 EVENT_HUB로 중계하고,
    누적 텍스트/최종 메타를 반환합니다.
    """
    url = f"{base_url}/api/jd/generate/stream"
    accum: List[str] = []
    saved_id: Optional[str] = None
    title: Optional[str] = None

    def _pick_text(d: dict) -> str:
        return d.get("text") or d.get("delta") or d.get("content") or ""

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, json=jd_payload) as r:
            cur_event = None
            async for line in r.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    cur_event = line.split(":", 1)[1].strip()
                    continue
                if line.startswith("data:"):
                    raw = line.split(":", 1)[1].strip()
                    try:
                        data = json.loads(raw)
                    except Exception:
                        data = {"text": raw}

                    # EventHub 브로드캐스트
                    await EVENT_HUB.publish(task_id, cur_event or "message", data)

                    if cur_event == "delta":
                        accum.append(_pick_text(data))
                    elif cur_event == "end":
                        saved_id = data.get("saved_id") or saved_id
                        title = data.get("title") or title

    markdown = "".join(accum)
    if not title:
        title = _title_from_markdown(markdown, fallback="제목 미정")

    return {"saved_id": saved_id, "title": title, "markdown": markdown}


# ---- 신규 엔드포인트: N개 대기 후 /jd/generate 호출 ----
@router.post(
    "/sim-then-generate",
    response_model=SimThenGenerateAnyResponse,
    response_model_exclude_none=True,
)
async def sim_then_generate(
    req: SimThenGenerateRequest,
    request: Request,
    rt: SimQueueRuntime = Depends(get_runtime),
    mode: Literal["sync", "async"] = Query("async"),
    stream: bool = Query(True),
    callback_url: Optional[str] = Query(None),
) -> SimThenGenerateAnyResponse:
    """
    1) 동일 사용자 큐에 'simulate_only' 작업들을 prequeue_count 만큼 push
    2) 전부 완료될 때까지 서버에서 대기
    3) 완료되면 내부 HTTP로 /api/jd/generate 호출 → 해당 응답을 그대로 반환
       (JDGenerationService/라우트는 수정하지 않음)
    """
    user_id = req.user_id or DEFAULT_USER_ID

    # 1) 가짜 대기열 push
    ids: List[str] = []
    for _ in range(req.prequeue_count):
        payload = {
            "simulate_only": True,
            "sim_fixed_sec": req.sim.fixed_sec,
            "sim_min_sec": req.sim.min_sec,
            "sim_max_sec": req.sim.max_sec,
        }
        rid, _pos = await rt.queue.enqueue(user_id, payload)
        ids.append(rid)

    if mode == "sync":
        # 2) 다 끝날 때까지 서버에서 대기
        await _wait_all_finished(rt, ids, timeout=req.wait_timeout_sec)
        # 3) 내부 호출로 실제 생성
        base = str(request.base_url).rstrip("/")
        url = f"{base}/api/jd/generate"
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(url, json=req.jd.model_dump(exclude_none=True))
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()

    # === async 모드 ===
    # 즉시 task_id 반환하고, 백그라운드에서 수행
    task_id = TASKS.create(user_id=user_id, req_json=req.jd.model_dump(exclude_none=True), stream_mode=stream)

    async def _bg_work():
        try:
            TASKS.update(task_id, status="waiting", meta={"pre_total": len(ids), "pre_done": 0})
            await EVENT_HUB.publish(task_id, "status", {"status": "waiting"})

            # 시뮬 N건 완료 대기 + 진행률 브로드캐스트
            terminal = {"finished", "failed", "canceled", "expired"}
            while True:
                done = 0
                for rid in ids:
                    it = await rt.queue.engine.status(rid)
                    if not it or it.status.value in terminal:
                        done += 1
                percent = int(done * 100 / max(1, len(ids)))
                meta = {"phase": "prequeue", "pre_total": len(ids), "pre_done": done, "percent": percent}
                TASKS.update(task_id, meta=meta)
                await EVENT_HUB.publish(task_id, "progress", meta)
                if done == len(ids):
                    break
                await asyncio.sleep(1.0)

            # 실제 생성 단계
            TASKS.update(task_id, status="generating")
            await EVENT_HUB.publish(task_id, "status", {"status": "generating"})

            base = str(request.base_url).rstrip("/")
            jd_payload = req.jd.model_dump(exclude_none=True)

            if stream:
                # ✅ 내부 스트림을 EventHub로 브릿지
                result_meta = await _proxy_jd_stream_to_eventhub(
                    task_id=task_id,
                    base_url=base,
                    jd_payload=jd_payload,
                )
                TASKS.update(
                    task_id,
                    status="finished",
                    finished_at=time.time(),
                    saved_id=result_meta.get("saved_id"),
                    result={"title": result_meta.get("title"), "markdown": result_meta.get("markdown")},
                )
            else:
                # 기존 non-stream 경로
                async with httpx.AsyncClient(timeout=None) as client:
                    resp = await client.post(f"{base}/api/jd/generate", json=jd_payload)
                    if resp.status_code >= 400:
                        raise HTTPException(status_code=resp.status_code, detail=resp.text)
                    data = resp.json()

                TASKS.update(
                    task_id,
                    status="finished",
                    finished_at=time.time(),
                    saved_id=data.get("saved_id"),
                    result=data,
                )

            # 웹훅 (옵션)
            if callback_url:
                try:
                    payload = {
                        "task_id": task_id,
                        "status": "finished",
                        "saved_id": TASKS.get(task_id).get("saved_id"),
                        "company_code": jd_payload.get("company_code"),
                        "job_code": jd_payload.get("job_code"),
                    }
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(callback_url, json=payload)
                except Exception:
                    pass

        except Exception as e:
            TASKS.update(task_id, status="failed", finished_at=time.time(), error=str(e))
            await EVENT_HUB.publish(task_id, "error", {"message": str(e)})

    asyncio.create_task(_bg_work())

    # ✅ stream 태스크면 result 링크를 stream으로 돌려줍니다.
    result_link = f"/api/llm/queue/tasks/{task_id}/stream" if stream else f"/api/llm/queue/tasks/{task_id}/result"
    return SimThenGenerateAsyncAccepted(
        task_id=task_id,
        status="accepted",
        links={
            "status": f"/api/llm/queue/tasks/{task_id}/status",
            "result": result_link,  # ✅ stream 시 /stream
        },
    )


# ✅ 변경된 코드 (전체)
@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def task_status(task_id: str, rt: SimQueueRuntime = Depends(get_runtime), user_id: str = Query(DEFAULT_USER_ID)):
    rec = TASKS.get(task_id)
    if not rec:
        raise HTTPException(status_code=404, detail="unknown task_id")

    status_s = rec["status"]
    meta = rec.get("meta") or {}
    pre_total = int(meta.get("pre_total") or 0)
    pre_done = int(meta.get("pre_done") or 0)

    # 진행률(서버 계산) — 대기 구간 0~90%, 생성 단계 90~99%, 완료 100
    if pre_total > 0:
        q_progress = round((pre_done / pre_total) * 90.0, 1)
    else:
        q_progress = 0.0

    if status_s == "generating":
        progress = max(90.0, min(99.0, q_progress + 5.0))
    elif status_s == "finished":
        progress = 100.0
    elif status_s == "failed":
        progress = q_progress
    else:
        progress = q_progress

    # === 큐 스냅샷 기반: 남은 인원/ETA/대기 퍼센트 ===
    snap = await rt.queue.engine.snapshot()
    user_win = next((uw for uw in snap.per_user if uw.user_id == user_id), None)
    queued = int(user_win.queued) if user_win else 0
    inflight = int(user_win.inflight) if user_win else 0

    rt.update_progress_ctx(user_id=user_id, queued=queued, inflight=inflight)
    ctx = rt.progress_ctx.get(user_id, {"baseline_total": 0})
    baseline_total = int(ctx.get("baseline_total", 0))
    active_now = queued + inflight

    try:
        avg_user = float(rt.queue._ema.get(user_id))
    except Exception:
        avg_user = 0.0
    avg_per_item = float(avg_user or (snap.avg_finish_sec or 20.0))

    per_user_parallel = max(1, rt.queue.engine.config.max_inflight_per_user)
    remaining_ahead = queued
    eta_seconds = round((remaining_ahead / per_user_parallel) * avg_per_item, 1)

    if baseline_total <= 0:
        wait_percent = 0.0 if active_now > 0 else 100.0
    else:
        completed = max(0, baseline_total - active_now)
        wait_percent = round(min(100.0, (completed / baseline_total) * 100.0), 1)

    # ✅ stream/non-stream에 따라 result 링크 분기
    result_link = (
        f"/api/llm/queue/tasks/{task_id}/stream"
        if rec.get("stream_mode", False)
        else f"/api/llm/queue/tasks/{task_id}/result"
    )

    return TaskStatusResponse(
        task_id=rec["task_id"],
        status=status_s,
        progress=progress,
        prequeue_done=pre_done,
        prequeue_total=pre_total,
        remaining_ahead=remaining_ahead,
        eta_seconds=eta_seconds,
        wait_percent=wait_percent,
        saved_id=rec.get("saved_id"),
        error=rec.get("error"),
        links={
            "result": result_link,  # ✅ 자동 분기
            "queue_state": f"/api/llm/queue/state?user_id={user_id}",
        },
    )


# ✅ 변경된 코드 (전체)
@router.get(
    "/tasks/{task_id}/result",
    response_model=JDGenerateResponse,
    response_model_exclude_none=True,
)
async def task_result(task_id: str):
    rec = TASKS.get(task_id)
    if not rec:
        raise HTTPException(status_code=404, detail="unknown task_id")

    # ✅ stream 태스크는 /stream 사용
    if rec.get("stream_mode", False):
        raise HTTPException(status_code=400, detail="stream-mode task. Use /tasks/{task_id}/stream")

    st = rec.get("status")
    if st != "finished":
        if st == "failed":
            raise HTTPException(
                status_code=424,  # Failed Dependency
                detail=rec.get("error") or "task failed",
            )
        raise HTTPException(status_code=409, detail=f"task not finished (status={st})")

    result = rec.get("result")
    if not result:
        raise HTTPException(status_code=500, detail="task finished but result missing")

    return result


# ✅ 신규 추가
@router.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str, request: Request):
    rec = TASKS.get(task_id)
    if not rec:
        raise HTTPException(status_code=404, detail="unknown task_id")

    if not rec.get("stream_mode", False):
        # non-stream 태스크는 /result 사용
        raise HTTPException(status_code=400, detail="non-stream task. Use /tasks/{task_id}/result")

    q = EVENT_HUB.subscribe(task_id)

    async def gen():
        try:
            # 최초 상태 스냅샷
            yield sse_bytes("status", {"status": rec["status"], "meta": rec.get("meta")})

            # 이미 종료된 경우 즉시 end/error
            if rec["status"] in ("finished", "failed"):
                if rec["status"] == "finished":
                    yield sse_bytes(
                        "end",
                        {
                            "saved_id": rec.get("saved_id"),
                            "title": (rec.get("result") or {}).get("title"),
                            "markdown": (rec.get("result") or {}).get("markdown"),
                        },
                    )
                else:
                    yield sse_bytes("error", {"message": rec.get("error")})
                return

            # 실시간 이벤트 소비
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=10.0)
                    yield sse_bytes(msg["type"], msg["data"])
                except asyncio.TimeoutError:
                    # keep-alive
                    yield b": ping\n\n"
        finally:
            EVENT_HUB.unsubscribe(task_id, q)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
