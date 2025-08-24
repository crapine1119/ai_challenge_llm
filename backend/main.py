import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes.llm_queue import init_llm_queue_runtime, shutdown_llm_queue_runtime
from infrastructure.db.seed.apply import apply_all_seeds
from infrastructure.db.seed.registry import load_seed_bundles
from src.api.routes import api_router
from src.infrastructure.db.database import get_session

# -------------------------------
# Logging 설정
# -------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# verbose한 서브로거 조절
for name in [
    "sqlalchemy",
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    "sqlalchemy.dialects",
]:
    logging.getLogger(name).setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# -------------------------------
# FastAPI Lifespan 설정
# -------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # === STARTUP ===
    await init_llm_queue_runtime()

    if os.getenv("AUTO_SEED", "0") in ("1", "true", "TRUE"):
        async for session in get_session():
            bundles = list(load_seed_bundles())
            applied = await apply_all_seeds(session, bundles, force=False)
            if applied:
                print(f"[startup] seeded bundles: {applied}")

    yield

    # === SHUTDOWN ===
    await shutdown_llm_queue_runtime()


# -------------------------------
# FastAPI 앱 초기화
# -------------------------------

app = FastAPI(lifespan=lifespan)


# 헬스체크
@app.get("/healthz", tags=["infra"])
async def health_check():
    return {"status": "ok"}


# 라우터 등록
app.include_router(api_router, prefix="/api")
