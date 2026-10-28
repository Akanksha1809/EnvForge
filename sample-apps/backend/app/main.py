"""Sample Application A — a minimal FastAPI service with Postgres + Redis.

This is one of the three demo applications EnvForge provisions real
preview environments for (see docs/demo-guide.md). It deliberately stays
small: a health check that proves both dependencies are reachable, and one
CRUD-ish endpoint backed by Postgres plus a Redis-backed hit counter.
"""
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


class Item(BaseModel):
    name: str


class ItemOut(BaseModel):
    id: int
    name: str
    created_at: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    app.state.redis = redis.from_url(REDIS_URL, decode_responses=True)
    async with app.state.pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    yield
    await app.state.pool.close()
    await app.state.redis.aclose()


app = FastAPI(title="EnvForge Sample App A", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    db_ok, redis_ok = False, False
    try:
        async with app.state.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    try:
        await app.state.redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    status = "ok" if db_ok and redis_ok else "degraded"
    return {
        "status": status,
        "dependencies": {"postgres": db_ok, "redis": redis_ok},
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/api/items", response_model=list[ItemOut])
async def list_items() -> list[asyncpg.Record]:
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, created_at FROM items ORDER BY id DESC LIMIT 50")
    return rows


@app.post("/api/items", response_model=ItemOut, status_code=201)
async def create_item(item: Item) -> asyncpg.Record:
    async with app.state.pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO items (name) VALUES ($1) RETURNING id, name, created_at", item.name
        )
    if row is None:
        raise HTTPException(status_code=500, detail="insert failed")
    return row


@app.get("/api/hits")
async def hits() -> dict:
    count = await app.state.redis.incr("envforge:sample-backend:hits")
    return {"hits": count}
