"""SQLite cache layer — TTL'd storage for scraped ads + LLM analysis results."""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

import config


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS ads_cache (
            key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS ai_analysis (
            key TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            result TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            period INTEGER NOT NULL,
            total_ads INTEGER NOT NULL,
            avg_ctr REAL NOT NULL,
            payload TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )""")


def cache_get(key: str, ttl: int | None = None) -> Any | None:
    ttl = ttl if ttl is not None else config.CACHE_TTL_SECONDS
    with _conn() as c:
        row = c.execute("SELECT payload, updated_at FROM ads_cache WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    if time.time() - row["updated_at"] > ttl:
        return None
    return json.loads(row["payload"])


def cache_set(key: str, payload: Any) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO ads_cache (key, payload, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (key, json.dumps(payload), int(time.time())),
        )


def ai_cache_get(key: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT model, result, updated_at FROM ai_analysis WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    return {"model": row["model"], "result": row["result"], "updated_at": row["updated_at"]}


def ai_cache_set(key: str, model: str, result: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO ai_analysis (key, model, result, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET model=excluded.model, result=excluded.result, "
            "updated_at=excluded.updated_at",
            (key, model, result, int(time.time())),
        )


def snapshot_save(region: str, period: int, ads: list[dict]) -> int:
    ctrs = [a.get("ctr") or 0 for a in ads]
    avg_ctr = sum(ctrs) / len(ctrs) if ctrs else 0.0
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO snapshots (region, period, total_ads, avg_ctr, payload, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (region, period, len(ads), avg_ctr, json.dumps(ads), int(time.time())),
        )
        return cur.lastrowid


def snapshot_list(limit: int = 20) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, region, period, total_ads, avg_ctr, created_at FROM snapshots "
            "ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


init_db()
