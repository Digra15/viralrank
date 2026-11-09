"""Admin routes — admin role required."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend import auth as A
from backend import db as DB
from backend.deps import admin_required
from backend.store import snapshot_list

router = APIRouter(prefix="/api/admin")


@router.get("/stats")
async def admin_stats(u: dict = Depends(admin_required)):
    from backend.store import _conn as store_conn
    with store_conn() as c:
        total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_sessions = c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        total_api_keys = c.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
        total_ads_fetched = c.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        latest_snapshot = c.execute("SELECT created_at,total_ads,avg_ctr FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "code": 0,
        "users": total_users,
        "sessions": total_sessions,
        "api_keys": total_api_keys,
        "ads_fetched": total_ads_fetched,
        "latest_snapshot": dict(latest_snapshot) if latest_snapshot else None,
    }


@router.get("/users")
async def list_users(u: dict = Depends(admin_required)):
    from backend.store import _conn as store_conn
    with store_conn() as c:
        rows = c.execute(
            "SELECT id,username,role,created_at,last_login FROM users ORDER BY id"
        ).fetchall()
    return {"code": 0, "users": [dict(r) for r in rows]}


@router.post("/users")
async def create_user(payload: dict, u: dict = Depends(admin_required)):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    role = payload.get("role", "user")
    if role not in ("user", "admin"):
        return {"code": 1, "message": "role must be user or admin"}
    if len(username) < 3 or len(password) < 4:
        return {"code": 1, "message": "username >= 3, password >= 4"}
    res = A.user_register(username, password)
    if res.get("code") == 0:
        from backend.store import _conn as store_conn
        with store_conn() as c:
            c.execute("UPDATE users SET role=? WHERE username=?", (role, username))
    return res


@router.patch("/users/{uid}/role")
async def update_role(uid: int, payload: dict, u: dict = Depends(admin_required)):
    role = payload.get("role", "user")
    if role not in ("user", "admin"):
        return {"code": 1, "message": "invalid role"}
    from backend.store import _conn as store_conn
    with store_conn() as c:
        c.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
    DB.audit(u["user_id"], "update_role", f"user_id={uid} role={role}")
    return {"code": 0}


@router.delete("/users/{uid}")
async def delete_user(uid: int, u: dict = Depends(admin_required)):
    if uid == u["user_id"]:
        return {"code": 1, "message": "cannot delete self"}
    from backend.store import _conn as store_conn
    with store_conn() as c:
        c.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
        c.execute("DELETE FROM users WHERE id=?", (uid,))
    DB.audit(u["user_id"], "delete_user", f"user_id={uid}")
    return {"code": 0}


# ---------------------------------------------------------------- settings management
@router.get("/settings")
async def admin_settings(u: dict = Depends(admin_required)):
    return {"code": 0, "settings": DB.settings_all(mask_secret=True)}


@router.post("/settings/put")
async def save_setting(payload: dict, u: dict = Depends(admin_required)):
    key = payload.get("key", "")
    value = payload.get("value", "")
    if not key:
        return {"code": 1, "message": "key required"}
    DB.setting_set(key, value)
    DB.audit(u["user_id"], "setting_update", f"{key}={value}")
    return {"code": 0}


@router.post("/settings/test-connection")
async def test_connection(payload: dict, u: dict = Depends(admin_required)):
    import httpx, os
    provider = payload.get("provider", "")
    base_url = payload.get("base_url", "")
    api_key = payload.get("api_key", "")
    test_url = payload.get("test_url", "")

    if not base_url or not test_url:
        return {"code": 1, "message": "base_url and test_url required"}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(base_url.rstrip("/") + test_url, headers=headers)
        return {"code": 0, "status": r.status_code, "body": r.text[:300]}
    except Exception as e:
        return {"code": 1, "message": str(e)}


# ---------------------------------------------------------------- snapshots & audit
@router.get("/snapshots")
async def admin_snapshots(limit: int = 100, u: dict = Depends(admin_required)):
    return {"code": 0, "items": snapshot_list(limit)}


@router.get("/audit")
async def admin_audit(limit: int = 200, u: dict = Depends(admin_required)):
    return {"code": 0, "items": DB.audit_list(limit)}
