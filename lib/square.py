"""Square API client - daily sales pulled from completed orders.

Returns the same shape as lib/shopify.fetch_daily_sales so the two sources
can be concatenated:  columns = sku, date, units, revenue.

SKUs live on Catalog item variations, not on line items directly, so we
build a one-time catalog_object_id -> sku map before walking orders.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

API_BASE = "https://connect.squareup.com/v2"
SQUARE_VERSION = "2024-10-17"


def _is_configured() -> bool:
    """True if we have enough env vars to talk to Square."""
    return bool(os.environ.get("SQUARE_ACCESS_TOKEN")) and bool(os.environ.get("SQUARE_LOCATION_ID"))


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['SQUARE_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
        "Square-Version": SQUARE_VERSION,
    }


def _fetch_sku_map() -> dict[str, str]:
    """Build {catalog_object_id: sku} for every item variation in the catalog."""
    sku_map: dict[str, str] = {}
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"types": "ITEM_VARIATION"}
        if cursor:
            params["cursor"] = cursor
        resp = requests.get(f"{API_BASE}/catalog/list", headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for obj in data.get("objects", []):
            sku = (obj.get("item_variation_data", {}) or {}).get("sku")
            if sku:
                sku_map[obj["id"]] = sku.strip()
        cursor = data.get("cursor")
        if not cursor:
            break
    return sku_map


def fetch_daily_sales(days_back: int = 365) -> pd.DataFrame:
    """Return daily units + revenue per SKU from Square completed orders.

    Columns: sku, date, units, revenue. Returns empty DataFrame if Square isn't configured.
    """
    cols = ["sku", "date", "units", "revenue"]
    if not _is_configured():
        return pd.DataFrame(columns=cols)

    location_id = os.environ["SQUARE_LOCATION_ID"]
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    sku_map = _fetch_sku_map()

    line_rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        body: dict[str, Any] = {
            "location_ids": [location_id],
            "query": {
                "filter": {
                    "state_filter": {"states": ["COMPLETED"]},
                    "date_time_filter": {"created_at": {"start_at": since}},
                },
            },
            "limit": 500,
        }
        if cursor:
            body["cursor"] = cursor

        resp = requests.post(f"{API_BASE}/orders/search", headers=_headers(), json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for order in data.get("orders", []):
            created = (order.get("created_at") or "")[:10]
            if not created:
                continue
            for li in order.get("line_items", []) or []:
                cat_id = li.get("catalog_object_id")
                sku = sku_map.get(cat_id, "") if cat_id else ""
                # Square sometimes also includes a `sku` field directly; prefer that if present
                sku = (li.get("sku") or sku or "").strip()
                if not sku:
                    continue
                try:
                    qty = int(li.get("quantity") or 0)
                except (TypeError, ValueError):
                    qty = 0
                if qty <= 0:
                    continue
                # gross_sales_money or total_money is line revenue; Square amounts are in cents
                money = (li.get("gross_sales_money") or li.get("total_money") or {})
                amount_cents = money.get("amount") or 0
                revenue = float(amount_cents) / 100.0
                line_rows.append({
                    "sku": sku,
                    "date": created,
                    "units": qty,
                    "revenue": revenue,
                })

        cursor = data.get("cursor")
        if not cursor:
            break

    if not line_rows:
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(line_rows)
    df["date"] = pd.to_datetime(df["date"])
    daily = df.groupby(["sku", "date"], as_index=False)[["units", "revenue"]].sum()
    return daily
