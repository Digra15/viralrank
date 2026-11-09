"""App data layer — settings kv, favorites, alerts, notes, audit log."""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

import config


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_app_db() -> None:
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            k TEXT PRIMARY KEY, v TEXT NOT NULL, updated_at INTEGER NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            kind TEXT NOT NULL, ref_id TEXT NOT NULL, payload TEXT,
            created_at INTEGER NOT NULL, UNIQUE(user_id, kind, ref_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            kind TEXT NOT NULL, label TEXT NOT NULL, rule TEXT NOT NULL,
            active INTEGER DEFAULT 1, hits INTEGER DEFAULT 0, last_hit INTEGER,
            created_at INTEGER NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            ref_id TEXT NOT NULL, body TEXT NOT NULL, created_at INTEGER NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            action TEXT NOT NULL, detail TEXT, ip TEXT, created_at INTEGER NOT NULL)""")


# ---------------------------------------------------------------- settings
def setting_get(k: str, default: str = "") -> str:
    with conn() as c:
        row = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
    return row["v"] if row else default


def setting_set(k: str, v: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO settings (k,v,updated_at) VALUES (?,?,?) "
            "ON CONFLICT(k) DO UPDATE SET v=excluded.v, updated_at=excluded.updated_at",
            (k, v, int(time.time())))


def settings_all(mask_secret: bool = True) -> dict[str, str]:
    with conn() as c:
        rows = c.execute("SELECT k,v FROM settings").fetchall()
    out = {}
    for r in rows:
        v = r["v"]
        if mask_secret and any(s in r["k"] for s in ("key", "secret", "token", "password")):
            out[r["k"]] = mask(v)
        else:
            out[r["k"]] = v
    return out


def mask(v: str) -> str:
    if not v:
        return ""
    if len(v) <= 8:
        return "*" * len(v)
    return v[:4] + "*" * (len(v) - 8) + v[-4:]


# ---------------------------------------------------------------- favorites
def fav_add(user_id: int, kind: str, ref_id: str, payload: Any = None) -> dict:
    with conn() as c:
        try:
            c.execute(
                "INSERT INTO favorites (user_id,kind,ref_id,payload,created_at) VALUES (?,?,?,?,?)",
                (user_id, kind, ref_id, json.dumps(payload or {}), int(time.time())))
        except sqlite3.IntegrityError:
            return {"code": 1, "message": "already saved"}
    return {"code": 0}


def fav_list(user_id: int, kind: str | None = None) -> list[dict]:
    q = "SELECT id,kind,ref_id,payload,created_at FROM favorites WHERE user_id=?"
    args: list[Any] = [user_id]
    if kind:
        q += " AND kind=?"
        args.append(kind)
    q += " ORDER BY created_at DESC LIMIT 300"
    with conn() as c:
        rows = c.execute(q, args).fetchall()
    return [{**dict(r), "payload": json.loads(r["payload"] or "{}")} for r in rows]


def fav_del(user_id: int, fid: int) -> dict:
    with conn() as c:
        c.execute("DELETE FROM favorites WHERE id=? AND user_id=?", (fid, user_id))
    return {"code": 0}


# ---------------------------------------------------------------- alerts
def alert_add(user_id: int, kind: str, label: str, rule: dict) -> dict:
    with conn() as c:
        c.execute(
            "INSERT INTO alerts (user_id,kind,label,rule,active,created_at) VALUES (?,?,?,?,1,?)",
            (user_id, kind, label, json.dumps(rule), int(time.time())))
    return {"code": 0}


def alert_list(user_id: int) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT id,kind,label,rule,active,hits,last_hit,created_at FROM alerts "
            "WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
    return [{**dict(r), "rule": json.loads(r["rule"] or "{}")} for r in rows]


def alert_del(user_id: int, aid: int) -> dict:
    with conn() as c:
        c.execute("DELETE FROM alerts WHERE id=? AND user_id=?", (aid, user_id))
    return {"code": 0}


# ---------------------------------------------------------------- notes
def note_add(user_id: int, ref_id: str, body: str) -> dict:
    with conn() as c:
        c.execute("INSERT INTO notes (user_id,ref_id,body,created_at) VALUES (?,?,?,?)",
                  (user_id, ref_id, body, int(time.time())))
    return {"code": 0}


def note_list(user_id: int, ref_id: str | None = None) -> list[dict]:
    q = "SELECT id,ref_id,body,created_at FROM notes WHERE user_id=?"
    args: list[Any] = [user_id]
    if ref_id:
        q += " AND ref_id=?"
        args.append(ref_id)
    with conn() as c:
        rows = c.execute(q + " ORDER BY created_at DESC LIMIT 200", args).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- audit
def audit(user_id: int | None, action: str, detail: str = "", ip: str = "") -> None:
    with conn() as c:
        c.execute("INSERT INTO audit (user_id,action,detail,ip,created_at) VALUES (?,?,?,?,?)",
                  (user_id, action, detail, ip, int(time.time())))


def audit_list(limit: int = 200) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT a.id,a.user_id,u.username,a.action,a.detail,a.ip,a.created_at "
            "FROM audit a LEFT JOIN users u ON a.user_id=u.id ORDER BY a.id DESC LIMIT ?",
            (limit,)).fetchall()
    return [dict(r) for r in rows]
