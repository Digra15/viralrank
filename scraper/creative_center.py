"""TikTok Creative Center client — live, no API key required.

Endpoint: https://ads.tiktok.com/creative_radar_api/v1/top_ads/v2/list
Browser-like headers required; server-side `objective` filter returns an
empty list, so the product-sales filter is applied client-side.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

import httpx

import config
from backend.store import cache_get, cache_set

CC_BASE = getattr(config, "CC_BASE", None) or "https://ads.tiktok.com/creative_radar_api/v1"
CC_TTL = int(os.environ.get("CC_TTL_SECONDS", "900"))

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


class CreativeCenterError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    # NOTE: the literal string "fake-user-id" is what the endpoint accepts —
    # random UUIDs come back code=40101 "no permission" (verified live).
    return {
        "Accept": "application/json, text/plain, */*",
        "anonymous-user-id": "fake-user-id",
        "Content-Type": "application/json",
        "User-Agent": _UA,
        "Referer": "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en",
        "Origin": "https://ads.tiktok.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Accept-Language": "en-US,en;q=0.9",
    }


def normalize_ad(m: dict) -> dict:
    """Normalize a Creative Center material into the unified schema."""
    vi = m.get("video_info") or {}
    vurl = vi.get("video_url") or {}
    if isinstance(vurl, dict):
        video_url = vurl.get("720p") or vurl.get("540p") or (next(iter(vurl.values())) if vurl else "")
    else:
        video_url = vurl
    obj = m.get("objective_key") or ""
    title = (m.get("ad_title") or "").strip()
    hashtags = [t.lstrip("#") for t in title.split() if t.startswith("#") and len(t) > 1]
    return {
        "id": m.get("id"),
        "ad_id": m.get("id"),
        "title": title,
        "brand_name": m.get("brand_name") or "",
        "brand": m.get("brand_name") or "",
        "objective_key": obj,
        "objective": obj.replace("campaign_objective_", ""),
        "product_sales": obj == "campaign_objective_product_sales",
        "ctr": m.get("ctr", 0) or 0,
        "like": m.get("like", 0) or 0,
        "likes": m.get("like", 0) or 0,
        "cost": m.get("cost", 0) or 0,
        "industry_key": m.get("industry_key") or "",
        "industry": m.get("industry_key") or "",
        "vid": vi.get("vid", ""),
        "cover": vi.get("cover", ""),
        "video_url": video_url,
        "duration": vi.get("duration", 0) or 0,
        "hashtags": hashtags,
        "source": "creative_center",
    }


async def top_ads(
    period: int = 7,
    region: str = "ID",
    page: int = 1,
    limit: int = 20,
    order_by: str = "ctr",
    keyword: str | None = None,
    industry_id: str | None = None,
    objective: str | None = None,
) -> list[dict]:
    """Raw API call -> normalized ad list."""
    params: dict[str, Any] = {
        "period": period,
        "page": page,
        "limit": limit,
        "order_by": order_by,
        "country_code": region,
        "sort_by": order_by,
    }
    if keyword:
        params["keyword"] = keyword
    if industry_id:
        params["industry_id"] = industry_id
    if objective:
        params["objective"] = objective

    async with httpx.AsyncClient(headers=_headers(), timeout=30) as client:
        r = await client.get(f"{CC_BASE}/top_ads/v2/list", params=params)
    try:
        payload = r.json()
    except ValueError as exc:
        raise CreativeCenterError(f"non-JSON response http={r.status_code}") from exc
    code = payload.get("code")
    if code not in (0, "0", None):
        raise CreativeCenterError(
            f"code={code} msg={payload.get('msg') or payload.get('message') or 'unknown'}"
        )
    data = payload.get("data") or payload
    mats = data.get("materials") or data.get("list") or data.get("items") or []
    return [normalize_ad(m) for m in mats]


async def fetch_ads(
    period: int = 7,
    region: str = "ID",
    page: int = 1,
    limit: int = 20,
    order_by: str = "ctr",
    keyword: str | None = None,
    only_ps: bool = False,
) -> dict:
    """Cached fetch. `only_ps` filters client-side (server-side returns empty)."""
    ck = f"cc:ads:{period}:{region}:{page}:{limit}:{order_by}:{keyword}:{only_ps}"
    hit = cache_get(ck, CC_TTL)
    if hit:
        return {"items": hit, "source": "creative_center", "cached": True}
    items = await top_ads(period=period, region=region, page=page, limit=limit,
                          order_by=order_by, keyword=keyword)
    if only_ps:
        items = [i for i in items if i["product_sales"]]
    if items:
        cache_set(ck, items)
    return {"items": items, "source": "creative_center", "cached": False}