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


def fetch_purchase_log(client: Client) -> pd.DataFrame:
    """Return all purchase_log rows, most recent first."""
    resp = client.table("purchase_log").select("*").order("ordered_at", desc=True).order("id", desc=True).execute()
    df = pd.DataFrame(resp.data)
    if df.empty:
        return pd.DataFrame(columns=[
            "id", "ordered_at", "sku", "vendor_id", "quantity",
            "unit_cost", "expected_arrival", "status", "notes", "created_at",
        ])
    return df


def insert_purchase_log(
    client: Client,
    ordered_at: str,
    sku: str,
    vendor_id: str | None,
    quantity: int,
    unit_cost: float | None,
    expected_arrival: str | None,
    notes: str | None,
    status: str = "placed",
) -> None:
    """Insert a single purchase log row."""
    payload = {
        "ordered_at": ordered_at,
        "sku": sku,
        "vendor_id": vendor_id,
        "quantity": int(quantity),
        "status": status,
    }
    if unit_cost is not None:
        payload["unit_cost"] = float(unit_cost)
    if expected_arrival:
        payload["expected_arrival"] = expected_arrival
    if notes:
        payload["notes"] = notes
    client.table("purchase_log").insert(payload).execute()


def update_purchase_log_status(client: Client, row_id: int, status: str) -> None:
    client.table("purchase_log").update({"status": status}).eq("id", row_id).execute()


def write_forecast_log(client: Client, rows: list[dict]) -> None:
    """Append a batch of forecast log rows.

    Each row: {sku, on_hand, daily_velocity, days_of_supply, status, recommended_qty}.
    `days_of_supply` may be None/NaN (represents infinity); inserted as NULL.
    """
    if not rows:
        return

    def _num_or_none(v):
        return None if pd.isna(v) else float(v)

    enriched = []
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        enriched.append({
            "run_at": now,
            "sku": r["sku"],
            "on_hand": int(r["on_hand"]) if not pd.isna(r["on_hand"]) else 0,
            "daily_velocity": _num_or_none(r["daily_velocity"]) or 0.0,
            "days_of_supply": _num_or_none(r["days_of_supply"]),
            "status": r["status"],
            "recommended_qty": int(r["recommended_qty"]) if not pd.isna(r["recommended_qty"]) else 0,
        })
    client.table("forecast_log").insert(enriched).execute()
