# src/infrastructure/db/database.py
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

DB_USER = os.getenv("PGUSER", "jobkorea")
DB_PASSWORD = os.getenv("PGPASSWORD", "jobkorea123")
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("PGDATABASE", "jobkorea_db")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def _as_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


SQLALCHEMY_ECHO = _as_bool(os.getenv("SQLALCHEMY_ECHO"), False)  # 기본 False


engine = create_async_engine(DATABASE_URL, echo=SQLALCHEMY_ECHO, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


# Dependency-style async generator (서비스 레이어에서 `async for` 패턴으로 사용)
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
