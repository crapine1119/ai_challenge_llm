import logging
import os
import sys

from fastapi import FastAPI

from api.routes import api_router
from infrastructure.db.database import get_session
from infrastructure.db.seed.apply import apply_all_seeds
from infrastructure.db.seed.registry import load_seed_bundles

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

# verbose한 서브 로거 조절
for name in ["sqlalchemy", "sqlalchemy.engine", "sqlalchemy.pool", "sqlalchemy.dialects"]:
    logging.getLogger(name).setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI()


@app.get("/healthz", tags=["infra"])
async def health_check():
    return {"status": "ok"}


@app.on_event("startup")
async def _auto_seed_on_startup():
    if os.getenv("AUTO_SEED", "0") not in ("1", "true", "TRUE"):
        return
    async for session in get_session():
        bundles = list(load_seed_bundles())
        applied = await apply_all_seeds(session, bundles, force=False)
        if applied:
            print(f"[startup] seeded bundles: {applied}")


app.include_router(api_router, prefix="/api")
