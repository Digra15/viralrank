"""TikTok Shop Partner Center client — official API, requires approved app credentials.

Every endpoint here needs TTS_APP_KEY / TTS_APP_SECRET. Without them the
backend surfaces a 400 with setup instructions instead of silently failing.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import httpx

import config


class ShopAPIError(RuntimeError):
    pass


def _sign(path: str, params: dict[str, Any], body: str, ts: int) -> str:
    """v2 sign: sha256_hex(path + sorted(params) + body + secret)."""
    base = path
    for k in sorted(params):
        base += f"{k}{params[k]}"
    base += body + config.TTS_APP_SECRET
    return hmac.new(config.TTS_APP_SECRET.encode(), base.encode(), hashlib.sha256).hexdigest()


async def _call(path: str, body: dict | None = None, extra_params: dict | None = None) -> dict:
    if not (config.TTS_APP_KEY and config.TTS_APP_SECRET):
        raise ShopAPIError(
            "TikTok Shop credentials missing. Set TTS_APP_KEY and TTS_APP_SECRET "
            "in .env (apply at https://partner.tiktokshop.com/openpage/codelist)."
        )
    ts = int(time.time())
    params: dict[str, Any] = {
        "app_key": config.TTS_APP_KEY,
        "timestamp": ts,
        **(extra_params or {}),
    }
    body_str = __import__("json").dumps(body) if body is not None else ""
    sign = _sign(path, params, body_str, ts)
    params["sign"] = sign
    if config.TTS_SHOP_CIPHER:
        params["shop_cipher"] = config.TTS_SHOP_CIPHER
    url = f"{config.TTS_BASE}{path}?{urlencode(params)}"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers={"Content-Type": "application/json"},
                              content=body_str or None, timeout=30)
    try:
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        raise ShopAPIError(f"non-json http={r.status_code}") from exc
    # tiktok shop: code 0 == ok
    if data.get("code") not in (0, "0", None):
        raise ShopAPIError(f"code={data.get('code')} msg={data.get('message')}")
    return data.get("data") or {}


async def search_products(keyword: str | None = None, page: int = 1,
                          page_size: int = 20) -> dict:
    """GET /product/202309/products/search"""
    q = {"page_number": page, "page_size": page_size}
    if keyword:
        q["keyword"] = keyword
    return await _call("/product/202309/products/search", extra_params=q)


async def product_list(sku_status: str | None = None, page: int = 1,
                       page_size: int = 20) -> dict:
    """POST /product/202309/products/search (filter by status)."""
    body: dict[str, Any] = {"page_number": page, "page_size": page_size}
    if sku_status:
        body["sku_status"] = sku_status
    return await _call("/product/202309/products/search", body=body)


async def order_list(shop_cipher: str | None = None, page: int = 1,
                     page_size: int = 20, create_after: int | None = None) -> dict:
    """POST /order/202407/orders/search"""
    body: dict[str, Any] = {"page_number": page, "page_size": page_size}
    if create_after:
        body["create_time_from"] = create_after
    return await _call("/order/202407/orders/search", body=body)
