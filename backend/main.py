import logging
import sys

from fastapi import FastAPI

from api.routes.collect import router as collect_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

app = FastAPI()


@app.get("/healthz", tags=["infra"])
async def health_check():
    return {"status": "ok"}


app.include_router(collect_router)
