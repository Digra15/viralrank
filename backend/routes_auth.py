"""Auth + account routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request

from backend import auth as A
from backend import db as DB
from backend.deps import auth_required

router = APIRouter(prefix="/api/auth")


@router.post("/register")
async def register(payload: dict):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if len(username) < 3 or len(password) < 4:
        return {"code": 1, "message": "Username >= 3 chars, password >= 4"}
    return A.user_register(username, password)


@router.post("/login")
async def login(payload: dict, request: Request):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    res = A.user_login(username, password, ip=ip, ua=ua)
    if res.get("code") == 0:
        DB.audit(None, "login", username, ip)
    return res


@router.post("/logout")
async def logout(authorization: str | None = Header(None)):
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    if token:
        A.session_invalidate(token)
    return {"code": 0}


@router.get("/me")
async def me(u: dict = Depends(auth_required)):
    return {"code": 0, "user": {"id": u["user_id"], "username": u["username"], "role": u["role"]}}


@router.get("/keys")
async def keys(u: dict = Depends(auth_required)):
    return A.api_key_list(u["user_id"])


@router.post("/keys")
async def key_create(payload: dict, u: dict = Depends(auth_required)):
    return A.api_key_create(u["user_id"], payload.get("name", ""), payload.get("scopes"))


@router.get("/settings")
async def settings(u: dict = Depends(auth_required)):
    return {"code": 0, "settings": DB.settings_all(mask_secret=True)}


@router.post("/favorites")
async def fav_add(payload: dict, u: dict = Depends(auth_required)):
    return DB.fav_add(u["user_id"], payload.get("kind", "ad"), payload.get("ref_id", ""), payload.get("payload"))


@router.get("/favorites")
async def fav_list(kind: str | None = None, u: dict = Depends(auth_required)):
    return {"code": 0, "items": DB.fav_list(u["user_id"], kind)}


@router.delete("/favorites/{fid}")
async def fav_del(fid: int, u: dict = Depends(auth_required)):
    return DB.fav_del(u["user_id"], fid)


@router.post("/alerts")
async def alert_add(payload: dict, u: dict = Depends(auth_required)):
    return DB.alert_add(u["user_id"], payload.get("kind", "ctr"), payload.get("label", ""), payload.get("rule", {}))


@router.get("/alerts")
async def alert_list(u: dict = Depends(auth_required)):
    return {"code": 0, "items": DB.alert_list(u["user_id"])}


@router.delete("/alerts/{aid}")
async def alert_del(aid: int, u: dict = Depends(auth_required)):
    return DB.alert_del(u["user_id"], aid)


@router.post("/notes")
async def note_add(payload: dict, u: dict = Depends(auth_required)):
    return DB.note_add(u["user_id"], payload.get("ref_id", ""), payload.get("body", ""))


@router.get("/notes")
async def note_list(ref_id: str | None = None, u: dict = Depends(auth_required)):
    return {"code": 0, "items": DB.note_list(u["user_id"], ref_id)}
