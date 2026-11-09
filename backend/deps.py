"""Auth dependencies — Bearer-token protection for FastAPI routes."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException

from backend import auth as A


def auth_required(
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Login required (Bearer token)")
    token = authorization.removeprefix("Bearer ").strip()
    res = A.session_validate(token)
    if res.get("code") != 0:
        raise HTTPException(401, res.get("message", "Invalid session"))
    return res


def admin_required(
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    u = auth_required(authorization)
    if u["role"] != "admin":
        raise HTTPException(403, "Admin only")
    return u
