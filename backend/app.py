"""Backend API — FastAPI routes for ViralRank."""
from __future__ import annotations

import os
import asyncio
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from scraper.creative_center import fetch_ads, normalize_ad
from scraper.tiktok_shop import search_products, product_list, order_list, ShopAPIError
from backend.store import cache_get, cache_set, ai_cache_get, ai_cache_set, snapshot_save, snapshot_list
from backend.auth import init_auth
from backend.db import init_app_db
from backend import db as DB


app = FastAPI(
    title="ViralRank API",
    description="TikTok Shop affiliate research tool — Creative Center + TikTok Shop + AI analysis",
    version="2.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATIC_DIR = os.path.join(config.APP_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def startup():
    from backend.store import init_db
    init_db()
    init_auth()
    init_app_db()


# ---------------------------------------------------------------------- include sub-routers
from backend.routes_auth import router as auth_router
from backend.routes_admin import router as admin_router

app.include_router(auth_router)
app.include_router(admin_router)


@app.get("/")
async def index():
    # Serve index.html (landing)
    return FileResponse(os.path.join(config.APP_DIR, "static", "index.html"))


@app.get("/app")
async def app_route():
    # Serve the main app shell
    return FileResponse(os.path.join(config.APP_DIR, "static", "app.html"))


@app.get("/admin")
async def admin_route():
    # Admin console
    return FileResponse(os.path.join(config.APP_DIR, "static", "admin.html"))


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "sources": {
            "creative_center": True,
            "tiktok_shop": bool(config.TTS_APP_KEY and config.TTS_APP_SECRET),
        },
        "cache": config.DB_PATH,
    }


@app.get("/api/filters")
async def api_filters(country_code: str = "ID"):
    """Real Creative Center filter taxonomy (cached 1h)."""
    ck = f"cc:filters:{country_code}"
    hit = cache_get(ck, 3600)
    if hit:
        return {"code": 0, "data": hit, "cached": True}
    async with httpx.AsyncClient(headers=config.CC_HEADERS, timeout=25) as client:
        r = await client.get(f"{config.CC_BASE}/top_ads/v2/filters", params={"country_code": country_code})
    try:
        payload = r.json()
    except ValueError:
        raise HTTPException(502, "filters: non-JSON response")
    data = payload.get("data") or {}
    if not data:
        raise HTTPException(502, f"filters: empty ({payload.get('code')} {payload.get('msg')})")
    shaped = {
        "industries": [{"id": i.get("id"), "name": i.get("label") or i.get("name")} for i in data.get("aggr_category_id", [])][:80],
        "objectives": [{"id": i.get("id"), "name": i.get("label") or i.get("name")} for i in data.get("objective", [])][:30],
        "languages": [{"id": i.get("id"), "name": i.get("label") or i.get("name")} for i in data.get("ad_language", [])][:40],
    }
    cache_set(ck, shaped)
    return {"code": 0, "data": shaped, "cached": False}


@app.get("/api/ads")
async def api_ads(
    period: int = Query(7, ge=1, le=180),
    region: str = Query("ID"),
    page: int = 1,
    limit: int = Query(20, ge=1, le=30),
    order_by: str = Query("ctr", description="ctr | like | cost"),
    industry_id: str | None = None,
    keyword: str | None = None,
    only_ps: bool = Query(False, description="filter product_sales only"),
):
    """Top ads list from Creative Center (anonymous, keyless)."""
    items = await fetch_ads(
        period=period, region=region, page=page, limit=limit,
        order_by=order_by, keyword=keyword, only_ps=only_ps
    )
    if items.get("items"):
        cache_set(f"ads:{period}:{region}:{page}:{limit}:{order_by}:{keyword}:{only_ps}", items["items"])
        snapshot_save(region, period, items["items"])
    return {"code": 0, "items": items.get("items", []), "source": items.get("source", "creative_center"), "cached": items.get("cached", False)}


@app.get("/api/fastmoss/rank/topSelling")
async def api_fm_rank(
    region: str = "ID",
    date_type: str = Query("day", description="day | week | month"),
    date_value: str = Query(..., description="YYYY-MM-DD (day) or YYYY-MM"),
    category_id: int | None = None,
    page: int = 1,
    pagesize: int = Query(10, ge=1, le=100),
):
    """FastMoss top-selling products (requires FM_API_KEY)."""
    key = DB.setting_get("fm_api_key") or os.environ.get("FM_API_KEY", "")
    if not key:
        raise HTTPException(
            400,
            detail="FastMoss API key belum diset. Isi di Admin Panel → Konfigurasi API.",
        )
    base = DB.setting_get("fm_base_url") or config.FM_BASE
    body = {
        "filter": {"region": region, "date_info": {"type": date_type, "value": date_value}},
        "orderby": [{"field": "units_sold", "order": "desc"}],
        "page": page, "pagesize": pagesize,
    }
    if category_id:
        body["filter"]["category_id"] = category_id
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{base}/product/v1/rank/topSelling",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            json=body,
            timeout=30,
        )
    try:
        d = r.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"fastmoss non-json http={r.status_code}") from exc
    if d.get("code") not in (0, "0"):
        raise HTTPException(502, f"fastmoss err {d.get('code')}: {d.get('message')}")
    return {"code": 0, "data": d.get("data")}


@app.get("/api/tiktok/shop/products")
async def api_tts_products(
    keyword: str | None = None,
    sku_status: str | None = None,
    page: int = 1,
    page_size: int = Query(20, ge=1, le=50),
):
    """TikTok Shop product search (requires TTS_APP_KEY + TTS_APP_SECRET)."""
    if not (config.TTS_APP_KEY and config.TTS_APP_SECRET):
        raise HTTPException(
            400,
            detail="TTS_APP_KEY and TTS_APP_SECRET required. Apply at https://partner.tiktokshop.com/openpage/codelist",
        )
    try:
        if keyword:
            data = await search_products(keyword=keyword, page=page, page_size=page_size)
        else:
            data = await product_list(sku_status=sku_status, page=page, page_size=page_size)
        return {"code": 0, "data": data}
    except ShopAPIError as e:
        raise HTTPException(400, detail=str(e)) from e


@app.get("/api/tiktok/shop/orders")
async def api_tts_orders(
    create_after: int | None = None,
    page: int = 1,
    page_size: int = Query(20, ge=1, le=50),
):
    """TikTok Shop order list (requires TTS_APP_KEY + TTS_APP_SECRET)."""
    if not (config.TTS_APP_KEY and config.TTS_APP_SECRET):
        raise HTTPException(
            400,
            detail="TTS_APP_KEY and TTS_APP_SECRET required. Apply at https://partner.tiktokshop.com/openpage/codelist",
        )
    try:
        data = await order_list(create_after=create_after, page=page, page_size=page_size)
        return {"code": 0, "data": data}
    except ShopAPIError as e:
        raise HTTPException(400, detail=str(e)) from e


@app.get("/api/snapshots")
async def api_snapshots(limit: int = Query(20, ge=1, le=100)):
    """List recent snapshots saved by /api/ads calls."""
    rows = snapshot_list(limit)
    return {"code": 0, "data": rows}


# ---------------------------------------------------------------- derived analytics
def _aggregate(items: list[dict], key: str) -> list[dict]:
    buckets: dict[str, dict] = {}
    for it in items:
        k = (it.get(key) or "").strip() or "(unknown)"
        b = buckets.setdefault(k, {"name": k, "ads": 0, "ctr_sum": 0.0, "likes": 0, "spend_ads": 0})
        b["ads"] += 1
        b["ctr_sum"] += float(it.get("ctr") or 0)
        b["likes"] += int(it.get("like") or 0)
        if it.get("cost"):
            b["spend_ads"] += 1
    out = []
    for b in buckets.values():
        out.append({
            "name": b["name"], "ads": b["ads"],
            "avg_ctr": round(b["ctr_sum"] / max(b["ads"], 1), 4),
            "likes": b["likes"],
            "momentum": round((b["ctr_sum"] / max(b["ads"], 1)) * 100 * min(b["ads"], 5) / 5, 2),
        })
    return sorted(out, key=lambda x: (x["avg_ctr"], x["ads"]), reverse=True)


@app.get("/api/insights")
async def api_insights(
    period: int = Query(7, ge=1, le=180),
    region: str = "ID",
    pages: int = Query(2, ge=1, le=5),
    order_by: str = "ctr",
):
    """Aggregated brand / industry / hashtag insight from live ads."""
    items: list[dict] = []
    for p in range(1, pages + 1):
        r = await fetch_ads(period=period, region=region, page=p, limit=20, order_by=order_by)
        items.extend(r.get("items", []))
    seen, uniq = set(), []
    for it in items:
        if it.get("id") in seen:
            continue
        seen.add(it.get("id"))
        uniq.append(it)

    hashtags: list[dict] = []
    tag_counts: dict[str, int] = {}
    for it in uniq:
        for tag in (it.get("hashtags") or []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    for tag, n in sorted(tag_counts.items(), key=lambda x: -x[1])[:40]:
        hashtags.append({"name": "#" + tag, "ads": n})

    return {
        "code": 0,
        "total_ads": len(uniq),
        "brands": _aggregate(uniq, "brand_name")[:20],
        "industries": _aggregate(uniq, "industry_key")[:20],
        "hashtags": hashtags,
        "avg_ctr": round(sum(float(i.get("ctr") or 0) for i in uniq) / max(len(uniq), 1), 4),
        "avg_likes": int(sum(int(i.get("like") or 0) for i in uniq) / max(len(uniq), 1)),
    }


@app.get("/api/export/csv")
async def api_export_csv(
    period: int = Query(7, ge=1, le=180),
    region: str = "ID",
    pages: int = Query(2, ge=1, le=5),
    order_by: str = "ctr",
):
    """CSV export of the current ad set (browser download)."""
    import csv, io
    from fastapi.responses import StreamingResponse

    items: list[dict] = []
    for p in range(1, pages + 1):
        r = await fetch_ads(period=period, region=region, page=p, limit=20, order_by=order_by)
        items.extend(r.get("items", []))

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "title", "brand", "industry", "ctr", "likes", "cost", "duration", "objective", "hashtags", "video_url"])
    for it in items:
        w.writerow([
            it.get("id", ""), (it.get("title") or "").replace("\n", " "), it.get("brand_name", ""),
            it.get("industry_key", ""), it.get("ctr", ""), it.get("like", ""), it.get("cost", ""),
            it.get("duration", ""), it.get("objective_key", ""), " ".join(it.get("hashtags") or []),
            (it.get("video_url") or {}).get("720p", "") if isinstance(it.get("video_url"), dict) else it.get("video_url", ""),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.read()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="viralrank_{region}_{period}d.csv"'},
    )


@app.post("/api/ai/analyze")
async def api_ai_analyze(payload: dict[str, Any]):
    """LLM analysis of the current ad set via 9Router (provider ag, Claude)."""
    from backend.ai import analyze_ads, AIError

    ads = payload.get("ads") or []
    if not ads:
        raise HTTPException(400, detail="ads[] kosong — muat data dulu")
    region = payload.get("region", "ID")
    period = int(payload.get("period", 7))
    model = payload.get("model") or None
    try:
        out = await analyze_ads(ads, region, period, model=model)
    except AIError as exc:
        raise HTTPException(502, detail=str(exc)) from exc
    return {"code": 0, **out}


@app.get("/api/ai/models")
async def api_ai_models():
    """Expose the configured model chain + whether a key resolves."""
    from backend.ai import _models, _key, AIError
    try:
        _key()
        has_key = True
    except AIError:
        has_key = False
    return {"code": 0, "models": _models(), "key_present": has_key}
