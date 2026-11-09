"""9Router LLM layer — provider `ag` + Claude models, OpenAI-compatible.

Primary model: ag/claude-sonnet-4-6. Falls back down AI_MODELS when the
upstream provider is rate-limited (antigravity returns HTTP 403 with a
reset window, so a fallback chain is required for a usable UI).
"""
from __future__ import annotations

import json
import os
import re
import asyncio
from typing import Any

import httpx

import config
from backend.store import ai_cache_get, ai_cache_set

NR_BASE = os.environ.get("NINE_ROUTER_BASE", "http://localhost:20128/v1")
NR_KEY = os.environ.get("NINE_ROUTER_KEY", "")
AI_MODELS = [m.strip() for m in os.environ.get(
    "AI_MODELS",
    "ag/claude-sonnet-4-6,ag/claude-opus-4-6-thinking,ag/gemini-3.8-flash",
).split(",") if m.strip()]

SYSTEM = (
    "Kamu analis afiliasi TikTok Shop Indonesia. Jawab ringkas, tajam, dalam Bahasa "
    "Indonesia. Fokus: potensi produk, angle konten, target audiens, risiko. "
    "Pakai angka dari data yang dikirim. Jangan mengarang metrik yang tidak ada."
)


class AIError(RuntimeError):
    pass


def _key() -> str:
    key = NR_KEY or os.environ.get("NINE_ROUTER_KEY", "")
    if key:
        return key
    # admin-panel override (DB settings) — set at runtime from the web UI
    try:
        from backend import db as DB
        key = DB.setting_get("ai_gateway_key")
        if key:
            return key
    except Exception:  # noqa: BLE001
        pass
    # single-user host convenience: 9Router stores active keys locally
    try:
        import sqlite3
        c = sqlite3.connect("/root/.9router/db/data.sqlite")
        row = c.execute("SELECT key FROM apiKeys WHERE isActive=1 LIMIT 1").fetchone()
        if row:
            return row[0]
    except Exception:  # noqa: BLE001
        pass
    raise AIError("9Router API key missing — set NINE_ROUTER_KEY in .env")


def _base() -> str:
    try:
        from backend import db as DB
        v = DB.setting_get("ai_gateway_url")
        if v:
            return v.rstrip("/")
    except Exception:  # noqa: BLE001
        pass
    return NR_BASE


def _models() -> list[str]:
    try:
        from backend import db as DB
        v = DB.setting_get("ai_model_chain")
        if v:
            return [m.strip() for m in v.split(",") if m.strip()]
    except Exception:  # noqa: BLE001
        pass
    return AI_MODELS


async def chat(prompt: str, *, model: str | None = None, max_tokens: int = 1200,
               temperature: float = 0.4) -> dict:
    """Call 9Router. Tries requested model first, then AI_MODELS chain.

    9Router streams SSE chunks even when `stream` is not requested, so the
    response body may be `data: {...}` lines instead of one JSON object.
    """
    chain = _models()
    order = [model] if model else []
    order += [m for m in chain if m not in order]
    key = _key()
    last: str = ""
    attempts: dict[str, int] = {m: 0 for m in order}
    async with httpx.AsyncClient(timeout=180) as client:
        for candidate in order:
            try:
                r = await client.post(
                    f"{_base()}/chat/completions",
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {key}"},
                    json={
                        "model": candidate,
                        "messages": [
                            {"role": "system", "content": SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
            except httpx.HTTPError as exc:
                last = f"{candidate}: transport {exc}"
                continue
            if r.status_code != 200:
                # antigravity rate-limits: marks 403 with "reset after Ns".
                # Waiting out the window then retrying yields a success.
                err = f"{candidate}: http {r.status_code} {r.text[:160]}"
                wait = _reset_seconds(r.text)
                if wait is not None and attempts[candidate] < 1:
                    attempts[candidate] += 1
                    await asyncio.sleep(wait + 1)
                    continue
                last = err
                continue
            text = _extract_text(r.text)
            if not text:
                last = f"{candidate}: empty completion"
                continue
            return {"model": candidate, "text": text}
    raise AIError(f"all models failed — last: {last}")


def _reset_seconds(body: str) -> int | None:
    """Extract 'reset after Ns' from 9Router/antigravity error body, else None."""
    m = re.search(r"reset after (\d+)s", body or "")
    return int(m.group(1)) if m else None


def _extract_text(body: str) -> str:
    """Handle both plain JSON and 9Router's SSE chunk stream."""
    body = (body or "").strip()
    if not body:
        return ""
    # plain JSON path
    if body.startswith("{"):
        try:
            data = json.loads(body)
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception:  # noqa: BLE001 — fall through to SSE parsing
            pass
    # SSE path: concatenate every delta.content
    parts: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if not chunk or chunk == "[DONE]":
            continue
        try:
            data = json.loads(chunk)
        except ValueError:
            continue
        for ch in data.get("choices") or []:
            delta = ch.get("delta") or {}
            if delta.get("content"):
                parts.append(delta["content"])
            msg = ch.get("message") or {}
            if msg.get("content"):
                parts.append(msg["content"])
    return "".join(parts).strip()


def build_ads_prompt(ads: list[dict], region: str, period: int) -> str:
    slim = [
        {
            "title": a.get("title", "")[:90],
            "brand": a.get("brand", ""),
            "ctr": a.get("ctr", 0),
            "likes": a.get("likes", 0),
            "industry": a.get("industry", ""),
            "duration": a.get("duration", 0),
        }
        for a in ads[:25]
    ]
    return (
        f"Data {len(slim)} iklan TikTok teratas region {region} periode {period} hari:\n"
        f"{json.dumps(slim, ensure_ascii=False)}\n\n"
        "Hasilkan analisis dengan format markdown:\n"
        "## Ringkasan Pasar (2 kalimat)\n"
        "## 3 Peluang Terbaik (nomor + alasan berbasis CTR/likes)\n"
        "## Angle Konten (3 hook siap pakai)\n"
        "## Risiko & Catatan (2 poin)\n"
    )


async def analyze_ads(ads: list[dict], region: str, period: int,
                      model: str | None = None, use_cache: bool = True) -> dict:
    import hashlib
    raw = json.dumps([a.get("ad_id") for a in ads], sort_keys=True)
    key = hashlib.sha256(f"{region}:{period}:{model}:{raw}".encode()).hexdigest()[:32]
    if use_cache:
        hit = ai_cache_get(key)
        if hit:
            return {"model": hit["model"], "text": hit["result"], "cached": True}
    out = await chat(build_ads_prompt(ads, region, period), model=model)
    ai_cache_set(key, out["model"], out["text"])
    return {**out, "cached": False}