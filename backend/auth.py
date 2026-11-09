"""Auth layer — user + admin, SQLite-backed sessions."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from typing import Any

import config


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT CHECK(role IN ('user', 'admin')) NOT NULL DEFAULT 'user',
                created_at INTEGER NOT NULL,
                last_login INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at INTEGER NOT NULL,
                ip TEXT,
                user_agent TEXT,
                created_at INTEGER NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT,
                key TEXT UNIQUE NOT NULL,
                scopes TEXT,  -- JSON array: ["ads", "tiktok", "fm"]
                active INTEGER DEFAULT 1,
                created_at INTEGER NOT NULL
            )
        """)
        # seed admin if none
        row = c.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        if not row:
            pw = os.environ.get("ADMIN_PASSWORD", "admin123")
            h = hashlib.sha256(pw.encode()).hexdigest()
            t = int(time.time())
            c.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
                ("admin", h, "admin", t)
            )


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def user_register(username: str, password: str) -> dict[str, Any]:
    t = int(time.time())
    h = hash_password(password)
    with _conn() as c:
        try:
            c.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
                (username, h, "user", t)
            )
            return {"code": 0, "message": "User created"}
        except sqlite3.IntegrityError:
            return {"code": 1, "message": "Username taken"}


def user_login(username: str, password: str, ip: str = "", ua: str = "") -> dict[str, Any]:
    h = hash_password(password)
    with _conn() as c:
        row = c.execute(
            "SELECT id, role, last_login FROM users WHERE username=? AND password_hash=?",
            (username, h)
        ).fetchone()
        if not row:
            return {"code": 1, "message": "Invalid credentials"}
        token = secrets.token_urlsafe(32)
        t = int(time.time())
        c.execute(
            "INSERT INTO sessions (user_id, token, expires_at, ip, user_agent, created_at) VALUES (?,?,?,?,?,?)",
            (row["id"], token, t + 86400, ip, ua, t)
        )
        c.execute("UPDATE users SET last_login=? WHERE id=?", (t, row["id"]))
    return {"code": 0, "token": token, "role": row["role"], "user_id": row["id"]}


def session_validate(token: str) -> dict[str, Any]:
    with _conn() as c:
        row = c.execute(
            "SELECT s.user_id, u.username, u.role FROM sessions s "
            "JOIN users u ON s.user_id=u.id WHERE s.token=? AND s.expires_at>?",
            (token, int(time.time()))
        ).fetchone()
        if not row:
            return {"code": 1, "message": "Invalid/Expired token"}
        return {"code": 0, "user_id": row["user_id"], "username": row["username"], "role": row["role"]}


def session_invalidate(token: str) -> dict[str, Any]:
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (token,))
    return {"code": 0, "message": "Logged out"}


def api_key_create(user_id: int, name: str = "", scopes: list[str] | None = None) -> dict[str, Any]:
    scopes = scopes or ["ads"]
    key = "vrl-" + secrets.token_hex(16)
    t = int(time.time())
    with _conn() as c:
        c.execute(
            "INSERT INTO api_keys (user_id, name, key, scopes, active, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, name, key, json.dumps(scopes), 1, t)
        )
    return {"code": 0, "key": key, "scopes": scopes}


def api_key_list(user_id: int) -> dict[str, Any]:
    with _conn() as c:
        rows = c.execute("SELECT id, name, key, scopes, active, created_at FROM api_keys WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
    return {"code": 0, "keys": [dict(r) for r in rows]}
