import logging

from fastapi import FastAPI

from api.routes.collect import router as collect_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

app = FastAPI()


@app.get("/healthz", tags=["infra"])
async def health_check():
    return {"status": "ok"}


app.include_router(collect_router)
