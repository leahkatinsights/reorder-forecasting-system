"""Financial KPIs for the Reorder Alerts dashboard.

Pure functions over the recs and purchase_log DataFrames.
No Streamlit imports here · easy to unit-test.
"""

from __future__ import annotations

import pandas as pd


def inventory_value(recs: pd.DataFrame) -> tuple[float, int]:
    """Total $ value of on-hand inventory across all SKUs.

    Returns (total_value, skus_excluded_for_missing_cost).
    SKUs without a unit_cost are excluded from the sum and counted.
    """
    if recs.empty:
        return 0.0, 0

    on_hand = pd.to_numeric(recs["on_hand"], errors="coerce").fillna(0)
    cost = pd.to_numeric(recs["unit_cost"], errors="coerce")

    valued_mask = cost.notna() & (on_hand > 0)
    excluded = int(((cost.isna()) & (on_hand > 0)).sum())
    total = float((on_hand[valued_mask] * cost[valued_mask]).sum())
    return total, excluded


def open_po_value(purchase_log: pd.DataFrame) -> float:
    """$ committed to POs not yet received.

    Sums quantity * unit_cost for rows with status in ('placed', 'shipped').
    Rows missing unit_cost contribute 0 (we don't know what was paid).
    """
    if purchase_log.empty:
        return 0.0

    open_rows = purchase_log[purchase_log["status"].isin(["placed", "shipped"])]
    if open_rows.empty:
        return 0.0

    qty = pd.to_numeric(open_rows["quantity"], errors="coerce").fillna(0)
    cost = pd.to_numeric(open_rows["unit_cost"], errors="coerce").fillna(0)
    return float((qty * cost).sum())


def reorder_needed(recs: pd.DataFrame) -> dict:
    """$ needed to act on every reorder alert.

    Returns {'total': float, 'now': float, 'soon': float}.
    Uses recommended_cost from recs (already computed as recommended_qty * unit_cost).
    """
    if recs.empty:
        return {"total": 0.0, "now": 0.0, "soon": 0.0}

    cost = pd.to_numeric(recs["recommended_cost"], errors="coerce").fillna(0)
    now = float(cost[recs["status"] == "reorder_now"].sum())
    soon = float(cost[recs["status"] == "reorder_soon"].sum())
    return {"total": now + soon, "now": now, "soon": soon}


def dead_stock_value(recs: pd.DataFrame) -> tuple[float, int]:
    """$ tied up in SKUs with status='dead'.

    Returns (total_value, dead_sku_count).
    """
    if recs.empty:
        return 0.0, 0

    dead = recs[recs["status"] == "dead"]
    if dead.empty:
        return 0.0, 0

    on_hand = pd.to_numeric(dead["on_hand"], errors="coerce").fillna(0)
    cost = pd.to_numeric(dead["unit_cost"], errors="coerce").fillna(0)
    total = float((on_hand * cost).sum())
    return total, int(len(dead))
