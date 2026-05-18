"""Shopify Admin API client — products, inventory, and orders.

We use the REST Admin API directly (no SDK) for transparency and minimal deps.
All functions return clean pandas DataFrames.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

import pandas as pd
import requests

API_VERSION = "2025-01"


def _api_base() -> str:
    domain = os.environ["SHOPIFY_STORE_DOMAIN"]
    return f"https://{domain}/admin/api/{API_VERSION}"


def _headers() -> dict[str, str]:
    return {
        "X-Shopify-Access-Token": os.environ["SHOPIFY_ADMIN_TOKEN"],
        "Content-Type": "application/json",
    }


def _get(path: str, params: dict | None = None) -> requests.Response:
    """GET with rate-limit handling. Sleeps and retries on 429."""
    url = f"{_api_base()}{path}"
    for attempt in range(5):
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "2"))
            time.sleep(retry_after)
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError(f"Shopify rate-limited 5 times on {url}")


def _paginate(path: str, params: dict | None = None) -> Iterator[dict]:
    """Walk all pages of a list endpoint via the Link header."""
    url = f"{_api_base()}{path}"
    while url:
        for attempt in range(5):
            resp = requests.get(url, headers=_headers(), params=params, timeout=30)
            if resp.status_code == 429:
                time.sleep(float(resp.headers.get("Retry-After", "2")))
                continue
            resp.raise_for_status()
            break
        else:
            raise RuntimeError(f"Shopify rate-limited 5 times on {url}")

        payload = resp.json()
        key = next(iter(payload.keys()))
        for item in payload[key]:
            yield item

        # On subsequent pages, params are encoded in the Link header URL itself.
        params = None
        link = resp.headers.get("Link", "")
        url = _next_page_url(link)


def _next_page_url(link_header: str) -> str | None:
    """Parse a Shopify Link header to find the next-page URL, or None."""
    if not link_header:
        return None
    parts = [p.strip() for p in link_header.split(",")]
    for p in parts:
        if 'rel="next"' in p:
            url_part = p.split(";")[0].strip()
            return url_part.strip("<>")
    return None


def fetch_products() -> pd.DataFrame:
    """Return all active product variants as a DataFrame.

    Columns: sku, variant_id, product_id, product_name, variant_title, inventory_item_id, on_hand
    """
    rows: list[dict[str, Any]] = []
    inventory_item_ids: list[int] = []

    for product in _paginate("/products.json", params={"limit": 250, "status": "active"}):
        for v in product.get("variants", []):
            sku = (v.get("sku") or "").strip()
            if not sku:
                continue
            rows.append({
                "sku": sku,
                "variant_id": v["id"],
                "product_id": product["id"],
                "product_name": product["title"],
                "variant_title": v.get("title", ""),
                "inventory_item_id": v.get("inventory_item_id"),
            })
            if v.get("inventory_item_id"):
                inventory_item_ids.append(v["inventory_item_id"])

    df = pd.DataFrame(rows)
    if df.empty:
        df["on_hand"] = pd.Series(dtype=int)
        return df

    # Inventory levels (chunked — Shopify caps inventory_item_ids per request at 50)
    on_hand_map: dict[int, int] = {}
    for chunk_start in range(0, len(inventory_item_ids), 50):
        chunk = inventory_item_ids[chunk_start:chunk_start + 50]
        ids_param = ",".join(str(i) for i in chunk)
        resp = _get("/inventory_levels.json", params={"inventory_item_ids": ids_param, "limit": 250})
        for level in resp.json().get("inventory_levels", []):
            item_id = level["inventory_item_id"]
            on_hand_map[item_id] = on_hand_map.get(item_id, 0) + (level.get("available") or 0)

    df["on_hand"] = df["inventory_item_id"].map(on_hand_map).fillna(0).astype(int)
    return df


def fetch_daily_sales(days_back: int = 365) -> pd.DataFrame:
    """Return daily units sold per SKU for the last `days_back` days.

    Columns: sku, date, units. One row per (sku, day) for days with sales.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    line_rows: list[dict[str, Any]] = []
    params = {
        "status": "any",
        "limit": 250,
        "created_at_min": since,
        "fields": "created_at,line_items,financial_status,cancelled_at",
    }

    for order in _paginate("/orders.json", params=params):
        if order.get("cancelled_at"):
            continue
        if order.get("financial_status") in ("refunded", "voided"):
            continue
        created = order["created_at"][:10]  # YYYY-MM-DD
        for li in order.get("line_items", []):
            sku = (li.get("sku") or "").strip()
            qty = li.get("quantity") or 0
            if not sku or qty <= 0:
                continue
            line_rows.append({"sku": sku, "date": created, "units": qty})

    if not line_rows:
        return pd.DataFrame(columns=["sku", "date", "units"])

    df = pd.DataFrame(line_rows)
    df["date"] = pd.to_datetime(df["date"])
    daily = df.groupby(["sku", "date"], as_index=False)["units"].sum()
    return daily


def daily_sales_for_sku(daily_df: pd.DataFrame, sku: str, days_back: int = 365) -> pd.Series:
    """Return a complete daily Series (one row per day, zero-filled) for one SKU."""
    end = pd.Timestamp(datetime.now(timezone.utc).date())
    start = end - pd.Timedelta(days=days_back - 1)
    full_index = pd.date_range(start=start, end=end, freq="D")

    sku_df = daily_df[daily_df["sku"] == sku]
    if sku_df.empty:
        return pd.Series([0] * len(full_index), index=full_index, name="units")

    series = sku_df.set_index("date")["units"].reindex(full_index, fill_value=0)
    series.name = "units"
    return series
