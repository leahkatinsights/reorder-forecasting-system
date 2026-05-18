"""Lumati Repurchase System — Streamlit dashboard entrypoint."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from lib import shopify, supabase_io  # noqa: E402
from lib.forecast import calculate_velocity, history_metadata  # noqa: E402
from lib.reorder import ReorderRecommendation, Settings, compute_recommendation  # noqa: E402


# ---------- Streamlit config ----------
st.set_page_config(
    page_title="Lumati Repurchase",
    page_icon="📦",
    layout="wide",
)


# ---------- Data loading (cached for session) ----------
@st.cache_data(ttl=3600, show_spinner="Loading data from Shopify and Supabase...")
def load_all_data() -> dict[str, Any]:
    """Pull everything we need for a dashboard session. Returns a dict of DataFrames + Settings."""
    client = supabase_io.get_client()
    products = supabase_io.fetch_products(client)
    vendors = supabase_io.fetch_vendors(client)
    settings = supabase_io.fetch_settings(client)

    shop_products = shopify.fetch_products()      # sku, product_name, on_hand, ...
    sales = shopify.fetch_daily_sales(days_back=settings_window(settings))

    return {
        "products": products,
        "vendors": vendors,
        "settings": settings,
        "shop_products": shop_products,
        "sales": sales,
        "loaded_at": datetime.now(),
    }


def settings_window(settings: Settings) -> int:
    # forecast_window_days isn't on the Settings dataclass; default 90 is fine
    # but we pull 365 days of orders to allow per-SKU recency analysis.
    return 365


# ---------- Recommendations ----------
def build_recommendations(data: dict[str, Any]) -> pd.DataFrame:
    """Run forecast + reorder for every active SKU in `products` that exists in Shopify.

    Returns a DataFrame with one row per SKU.
    """
    products = data["products"]
    shop = data["shop_products"]
    sales = data["sales"]
    settings = data["settings"]

    if products.empty or shop.empty:
        return pd.DataFrame()

    today = datetime.now().date()

    merged = products.merge(
        shop[["sku", "on_hand", "product_name"]],
        on="sku",
        how="inner",
    )

    rows = []
    for _, p in merged.iterrows():
        sku = p["sku"]
        series = shopify.daily_sales_for_sku(sales, sku)
        velocity = calculate_velocity(
            series,
            window_days=90,
            growth_factor=float(p.get("growth_factor") or 1.0),
        )
        meta = history_metadata(series, today=today)

        rec = compute_recommendation(
            sku=sku,
            on_hand=int(p["on_hand"]),
            daily_velocity=velocity,
            days_since_first_sale=meta["days_since_first_sale"],
            days_since_last_sale=meta["days_since_last_sale"],
            moq=int(p.get("moq") or 1),
            target_cover_days=int(p.get("target_cover_days") or 60),
            manual_override=bool(p.get("manual_override") or False),
            settings=settings,
        )

        rows.append({
            "sku": sku,
            "name": p.get("name") or p["product_name"],
            "category": p.get("category"),
            "vendor_id": p.get("vendor_id"),
            "unit_cost": float(p["unit_cost"]) if p.get("unit_cost") is not None else None,
            "moq": int(p.get("moq") or 1),
            "on_hand": rec.on_hand,
            "daily_velocity": rec.daily_velocity,
            "days_of_supply": rec.days_of_supply,
            "status": rec.status,
            "recommended_qty": rec.recommended_qty,
        })

    df = pd.DataFrame(rows)
    df["recommended_cost"] = df.apply(
        lambda r: (r["recommended_qty"] * r["unit_cost"]) if pd.notna(r["unit_cost"]) else None,
        axis=1,
    )
    return df


# ---------- Sidebar nav ----------
PAGES = ["Reorder Alerts", "Forecast Detail", "Vendors", "All Products"]

with st.sidebar:
    st.markdown("## 📦 Lumati Repurchase")
    page = st.radio("Page", PAGES, label_visibility="collapsed")
    st.divider()
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()


# ---------- Load + status bar ----------
data = load_all_data()
recs = build_recommendations(data)

loaded_ago = (datetime.now() - data["loaded_at"]).seconds
st.caption(
    f"Last refreshed: {loaded_ago // 60} min ago  •  "
    f"365 days of orders  •  {len(recs)} SKUs tracked"
)


# ---------- Page routing ----------
def render_reorder_alerts(recs: pd.DataFrame, data: dict) -> None:
    st.header("Reorder Alerts")

    if recs.empty:
        st.info("No products loaded yet. Run `seed_products.py` first.")
        return

    alerts = recs[recs["status"].isin(["reorder_now", "reorder_soon"])].copy()
    alerts = alerts.sort_values(
        by=["status", "days_of_supply"],
        ascending=[True, True],  # reorder_now < reorder_soon alphabetically -> good
    )

    now_count = (alerts["status"] == "reorder_now").sum()
    soon_count = (alerts["status"] == "reorder_soon").sum()

    c1, c2 = st.columns(2)
    c1.metric("🔴 Reorder now", int(now_count))
    c2.metric("🟡 Reorder soon", int(soon_count))

    st.divider()

    if alerts.empty:
        st.success("Nothing needs reordering. Inventory looks healthy.")
        return

    vendors = data["vendors"].set_index("id") if not data["vendors"].empty else None

    for _, r in alerts.iterrows():
        icon = "🔴" if r["status"] == "reorder_now" else "🟡"
        label = "Reorder now" if r["status"] == "reorder_now" else "Reorder soon"

        vendor_name = None
        if vendors is not None and pd.notna(r["vendor_id"]) and r["vendor_id"] in vendors.index:
            v = vendors.loc[r["vendor_id"]]
            vendor_name = v["name"]

        with st.container(border=False):
            top = st.columns([1, 6, 3])
            top[0].markdown(f"### {icon}")
            top[1].markdown(f"**{r['sku']}**  \n{r['name']}")
            top[2].markdown(f"**{label}**")

            mid = st.columns(4)
            mid[0].metric("On hand", r["on_hand"])
            mid[1].metric("Velocity (units/day)", f"{r['daily_velocity']:.2f}")
            mid[2].metric("Days of supply", f"{r['days_of_supply']:.1f}" if r["days_of_supply"] is not None else "∞")
            mid[3].metric("Recommended qty", r["recommended_qty"])

            cost = r.get("recommended_cost")
            cost_str = f"${cost:,.2f}" if pd.notna(cost) else "—"
            vendor_str = vendor_name or "_no vendor set_"
            st.markdown(f"💰 Est. cost: **{cost_str}**  •  🏷️ Vendor: **{vendor_str}**")

            st.divider()


def render_forecast_detail(recs: pd.DataFrame, data: dict) -> None:
    st.header("Forecast Detail")
    st.write("_(coming in Task 13)_")


def render_vendors(recs: pd.DataFrame, data: dict) -> None:
    st.header("Vendors")
    st.write("_(coming in Task 14)_")


def render_all_products(recs: pd.DataFrame, data: dict) -> None:
    st.header("All Products")
    st.write("_(coming in Task 15)_")


if page == "Reorder Alerts":
    render_reorder_alerts(recs, data)
elif page == "Forecast Detail":
    render_forecast_detail(recs, data)
elif page == "Vendors":
    render_vendors(recs, data)
elif page == "All Products":
    render_all_products(recs, data)
