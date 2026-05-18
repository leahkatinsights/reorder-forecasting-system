"""All Supabase reads and writes for the Lumati Repurchase System."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
from supabase import Client, create_client

from lib.reorder import Settings


def get_client() -> Client:
    """Build a Supabase client from env vars. Cached implicitly by Streamlit."""
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def fetch_products(client: Client) -> pd.DataFrame:
    """Return all rows from products as a DataFrame, indexed by sku."""
    resp = client.table("products").select("*").execute()
    df = pd.DataFrame(resp.data)
    if df.empty:
        return pd.DataFrame(columns=[
            "sku", "name", "category", "vendor_id", "unit_cost",
            "moq", "target_cover_days", "growth_factor",
            "manual_override", "active", "notes",
        ])
    return df


def fetch_vendors(client: Client) -> pd.DataFrame:
    resp = client.table("vendors").select("*").execute()
    df = pd.DataFrame(resp.data)
    if df.empty:
        return pd.DataFrame(columns=[
            "id", "name", "contact_name", "contact_email",
            "contact_phone", "website", "payment_terms",
            "currency", "notes",
        ])
    return df


def fetch_settings(client: Client) -> Settings:
    resp = client.table("settings").select("*").eq("id", 1).single().execute()
    s = resp.data
    return Settings(
        reorder_now_days=s["reorder_now_days"],
        reorder_soon_days=s["reorder_soon_days"],
        slow_mover_threshold=float(s["slow_mover_threshold"]),
        dead_mover_days=s["dead_mover_days"],
        insufficient_history_days=s["insufficient_history_days"],
    )


def insert_product(client: Client, sku: str, name: str, category: str | None = None) -> None:
    """Insert a product row with defaults if SKU not already present."""
    client.table("products").upsert(
        {"sku": sku, "name": name, "category": category},
        on_conflict="sku",
        ignore_duplicates=True,
    ).execute()


def write_forecast_log(client: Client, rows: list[dict]) -> None:
    """Append a batch of forecast log rows.

    Each row: {sku, on_hand, daily_velocity, days_of_supply, status, recommended_qty}.
    `days_of_supply` may be None (represents infinity); inserted as NULL.
    """
    if not rows:
        return
    enriched = []
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        enriched.append({
            "run_at": now,
            "sku": r["sku"],
            "on_hand": r["on_hand"],
            "daily_velocity": float(r["daily_velocity"]),
            "days_of_supply": float(r["days_of_supply"]) if r["days_of_supply"] is not None else None,
            "status": r["status"],
            "recommended_qty": r["recommended_qty"],
        })
    client.table("forecast_log").insert(enriched).execute()
