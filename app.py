"""Lumati Repurchase System — Streamlit dashboard entrypoint."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import altair as alt
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

LOGO_URL = "https://shop.lumati.com/cdn/shop/files/lumatllogo_black_nt_hor-500.png?v=1768746788&width=280"
st.logo(LOGO_URL, size="large")

# Override primary button color in the sidebar only (used for active nav item).
# Keeps the rose primary color for form buttons in the main content area.
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] button[kind="primary"] {
        background-color: #F0F0F0;
        color: #1E3A5F;
        border-color: transparent;
        font-weight: 600;
    }
    section[data-testid="stSidebar"] button[kind="primary"]:hover {
        background-color: #E5E5E5;
        border-color: transparent;
        color: #1E3A5F;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Data loading (cached for session) ----------
@st.cache_resource
def _get_supabase_client():
    """Cached Supabase client. cache_resource handles unpicklable objects like DB connections."""
    return supabase_io.get_client()


@st.cache_data(ttl=3600, show_spinner="Loading data from Shopify and Supabase...")
def load_all_data() -> dict[str, Any]:
    """Pull everything we need for a dashboard session. Returns a dict of DataFrames + Settings."""
    client = _get_supabase_client()
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

    # Filter to active products only (defaults true if column missing)
    if "active" in products.columns:
        products = products[products["active"].fillna(True).astype(bool)]
        if products.empty:
            return pd.DataFrame()

    today = datetime.now().date()

    merged = products.merge(
        shop[["sku", "on_hand", "on_hand_clinic", "on_hand_wsa", "product_name"]],
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
            "on_hand_clinic": int(p["on_hand_clinic"]),
            "on_hand_wsa": int(p["on_hand_wsa"]),
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
# Material Symbols render as black outlined icons by default.
NAV_ITEMS = [
    ("Reorder Alerts",  ":material/notifications_active:"),
    ("Forecast Detail", ":material/trending_up:"),
    ("Purchase Log",    ":material/receipt_long:"),
    ("Vendors",         ":material/store:"),
    ("All Products",    ":material/inventory_2:"),
]
PAGES = [label for label, _ in NAV_ITEMS]

if "page" not in st.session_state:
    st.session_state.page = "Reorder Alerts"

with st.sidebar:
    for label, icon in NAV_ITEMS:
        is_active = st.session_state.page == label
        if st.button(
            label,
            key=f"nav_{label}",
            type="primary" if is_active else "secondary",
            icon=icon,
            use_container_width=True,
        ):
            st.session_state.page = label
            st.rerun()
    st.divider()
    if st.button("Refresh data", icon=":material/refresh:", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

page = st.session_state.page


# ---------- Load + status bar ----------
data = load_all_data()
recs = build_recommendations(data)

if not recs.empty:
    rows = recs[["sku", "on_hand", "daily_velocity", "days_of_supply", "status", "recommended_qty"]].to_dict("records")
    try:
        supabase_io.write_forecast_log(_get_supabase_client(), rows)
    except Exception as e:
        st.warning(f"Could not write forecast log: {e}")

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

            mid = st.columns(5)
            mid[0].metric("Clinic", r["on_hand_clinic"])
            mid[1].metric("WSA", r["on_hand_wsa"])
            mid[2].metric("Velocity (units/day)", f"{r['daily_velocity']:.2f}")
            mid[3].metric("Days of supply", f"{r['days_of_supply']:.1f}" if r["days_of_supply"] is not None else "∞")
            mid[4].metric("Recommended qty", r["recommended_qty"])

            cost = r.get("recommended_cost")
            cost_str = f"${cost:,.2f}" if pd.notna(cost) else "—"
            vendor_str = vendor_name or "_no vendor set_"
            st.markdown(f"💰 Est. cost: **{cost_str}**  •  🏷️ Vendor: **{vendor_str}**")

            st.divider()


def render_forecast_detail(recs: pd.DataFrame, data: dict) -> None:
    st.header("Forecast Detail")

    if recs.empty:
        st.info("No products to inspect.")
        return

    # Sort SKUs by status urgency then alphabetically for the picker
    status_order = {
        "reorder_now": 0,
        "reorder_soon": 1,
        "healthy": 2,
        "slow": 3,
        "insufficient_history": 4,
        "dead": 5,
        "manual_override": 6,
    }
    sku_options = (
        recs.assign(_o=recs["status"].map(status_order).fillna(99))
        .sort_values(["_o", "sku"])["sku"]
        .tolist()
    )
    name_by_sku = recs.set_index("sku")["name"].to_dict()
    sku = st.selectbox(
        "Pick a SKU",
        sku_options,
        format_func=lambda s: f"{s} — {name_by_sku.get(s, '')}",
    )
    row = recs[recs["sku"] == sku].iloc[0]

    st.subheader(f"{row['sku']} — {row['name']}")

    c = st.columns(5)
    c[0].metric("Status", row["status"])
    c[1].metric("Clinic", row["on_hand_clinic"])
    c[2].metric("WSA", row["on_hand_wsa"])
    c[3].metric("Velocity (units/day)", f"{row['daily_velocity']:.2f}")
    c[4].metric(
        "Days of supply",
        f"{row['days_of_supply']:.1f}" if row["days_of_supply"] is not None else "∞",
    )

    st.divider()
    st.subheader("Sales history (last 90 days) + forecast projection (next 60 days)")

    series = shopify.daily_sales_for_sku(data["sales"], sku, days_back=90)
    actual_df = pd.DataFrame({"date": series.index, "units": series.values, "kind": "actual"})

    # Project flat at current velocity. The model is a velocity model, not a daily-detail forecast.
    future_dates = pd.date_range(start=series.index[-1] + pd.Timedelta(days=1), periods=60, freq="D")
    forecast_df = pd.DataFrame(
        {"date": future_dates, "units": row["daily_velocity"], "kind": "forecast"}
    )

    combined = pd.concat([actual_df, forecast_df], ignore_index=True)

    chart = (
        alt.Chart(combined)
        .mark_line()
        .encode(
            x="date:T",
            y="units:Q",
            color=alt.Color(
                "kind:N",
                scale=alt.Scale(domain=["actual", "forecast"], range=["#1E3A5F", "#D4829A"]),
            ),
        )
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)

    st.divider()
    with st.expander("Math breakdown"):
        dos = row["days_of_supply"]
        dos_str = f"{dos:.1f}" if dos is not None else "infinite"
        st.markdown(
            f"""
- Forecast window: last **90 days**
- Weights: linear ramp from **0.5** (oldest) to **1.5** (most recent)
- Final velocity: **{row['daily_velocity']:.3f} units/day**
- Days of supply = on_hand ({row['on_hand']}) / velocity ({row['daily_velocity']:.3f}) = **{dos_str}**
- Recommended qty = max(MOQ, target_cover_days × velocity) = **{row['recommended_qty']} units**
            """
        )


def render_purchase_log(recs: pd.DataFrame, data: dict) -> None:
    st.header("Purchase Log")

    if recs.empty:
        st.info("No products loaded yet.")
        return

    # Add new purchase form
    with st.expander("➕ Log a new purchase", expanded=False):
        with st.form("new_purchase", clear_on_submit=True):
            c1, c2 = st.columns(2)
            ordered_at = c1.date_input("Date ordered", value=datetime.now().date())
            expected_arrival = c2.date_input("Expected arrival (optional)", value=None)

            sku_options = recs.sort_values("sku")["sku"].tolist()
            name_by_sku = recs.set_index("sku")["name"].to_dict()
            sku = st.selectbox(
                "SKU",
                sku_options,
                format_func=lambda s: f"{s} — {name_by_sku.get(s, '')}",
            )

            vendor_options = [None] + (data["vendors"]["id"].tolist() if not data["vendors"].empty else [])
            vendor_name_by_id = (
                data["vendors"].set_index("id")["name"].to_dict() if not data["vendors"].empty else {}
            )
            vendor_id = st.selectbox(
                "Vendor",
                vendor_options,
                format_func=lambda v: "(none)" if v is None else vendor_name_by_id.get(v, str(v)),
            )

            c3, c4 = st.columns(2)
            quantity = c3.number_input("Quantity", min_value=1, value=1, step=1)
            unit_cost = c4.number_input("Unit cost ($) — optional", min_value=0.0, value=0.0, step=0.01)
            notes = st.text_area("Notes (optional)", "")

            submitted = st.form_submit_button("Log purchase", type="primary")
            if submitted:
                try:
                    supabase_io.insert_purchase_log(
                        _get_supabase_client(),
                        ordered_at=ordered_at.isoformat(),
                        sku=sku,
                        vendor_id=vendor_id,
                        quantity=int(quantity),
                        unit_cost=unit_cost if unit_cost > 0 else None,
                        expected_arrival=expected_arrival.isoformat() if expected_arrival else None,
                        notes=notes if notes.strip() else None,
                    )
                    st.success(f"Logged: {sku} × {int(quantity)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not save: {e}")

    st.divider()
    st.subheader("History")

    log = supabase_io.fetch_purchase_log(_get_supabase_client())
    if log.empty:
        st.info("No purchases logged yet. Use the form above to add one.")
        return

    # Filters
    fc1, fc2 = st.columns(2)
    status_filter = fc1.multiselect("Status", sorted(log["status"].dropna().unique()), default=[])
    sku_search = fc2.text_input("Filter by SKU", "")
    if status_filter:
        log = log[log["status"].isin(status_filter)]
    if sku_search:
        log = log[log["sku"].str.contains(sku_search, case=False, na=False)]

    # Join readable names
    vmap = data["vendors"].set_index("id")["name"].to_dict() if not data["vendors"].empty else {}
    log["vendor"] = log["vendor_id"].map(vmap).fillna("—")
    nmap = recs.set_index("sku")["name"].to_dict()
    log["product"] = log["sku"].map(nmap).fillna("—")

    display_cols = [
        "ordered_at", "sku", "product", "vendor",
        "quantity", "unit_cost", "expected_arrival", "status", "notes",
    ]
    display = log[display_cols].copy()
    display["unit_cost"] = display["unit_cost"].apply(lambda v: f"${v:,.2f}" if pd.notna(v) else "—")
    display["expected_arrival"] = display["expected_arrival"].fillna("—")
    display["notes"] = display["notes"].fillna("—")
    st.dataframe(display, hide_index=True, use_container_width=True)

    st.caption(f"{len(display)} entries shown")
    _supabase_edit_link("purchase_log")


def render_vendors(recs: pd.DataFrame, data: dict) -> None:
    st.header("Vendors")

    vendors = data["vendors"]
    if vendors.empty:
        st.info("No vendors yet. Add some in Supabase's Table Editor under the `vendors` table.")
        _supabase_edit_link("vendors")
        return

    search = st.text_input("Search vendor name", "")
    filtered = vendors[vendors["name"].str.contains(search, case=False, na=False)] if search else vendors

    # SKUs per vendor for quick context
    skus_per_vendor = recs.groupby("vendor_id")["sku"].count() if not recs.empty else pd.Series(dtype=int)

    for _, v in filtered.iterrows():
        sku_count = int(skus_per_vendor.get(v["id"], 0))
        with st.expander(f"{v['name']}  •  {sku_count} SKUs"):
            c1, c2 = st.columns(2)
            c1.markdown(f"**Contact:** {v.get('contact_name') or '—'}  \n"
                        f"**Email:** {v.get('contact_email') or '—'}  \n"
                        f"**Phone:** {v.get('contact_phone') or '—'}")
            c2.markdown(f"**Payment terms:** {v.get('payment_terms') or '—'}  \n"
                        f"**Currency:** {v.get('currency') or 'USD'}  \n"
                        f"**Website:** {v.get('website') or '—'}")
            if v.get("notes"):
                st.markdown(f"**Notes:** {v['notes']}")

            if sku_count > 0:
                sku_df = recs[recs["vendor_id"] == v["id"]][["sku", "name", "status", "on_hand_clinic", "on_hand_wsa", "days_of_supply", "recommended_qty"]]
                st.dataframe(sku_df, hide_index=True, use_container_width=True)

    st.divider()
    _supabase_edit_link("vendors")


def _supabase_edit_link(table: str) -> None:
    """Render a button-link that opens the Supabase table editor in a new tab."""
    project_url = os.environ.get("SUPABASE_URL", "")
    if not project_url:
        return
    # Project URL is like https://abc123.supabase.co — extract the project ref
    ref = project_url.replace("https://", "").split(".")[0]
    edit_url = f"https://supabase.com/dashboard/project/{ref}/editor"
    st.link_button(f"Edit {table} in Supabase →", edit_url)


def render_all_products(recs: pd.DataFrame, data: dict) -> None:
    st.header("All Products")

    if recs.empty:
        st.info("No products loaded.")
        return

    # Filters
    c1, c2, c3, c4 = st.columns(4)
    categories = sorted([c for c in recs["category"].dropna().unique()])
    statuses = sorted([s for s in recs["status"].dropna().unique()])

    selected_cat = c1.multiselect("Category", categories, default=[])
    selected_status = c2.multiselect("Status", statuses, default=[])
    selected_vendor_id = c3.selectbox(
        "Vendor",
        options=[None] + (data["vendors"]["id"].tolist() if not data["vendors"].empty else []),
        format_func=lambda x: "All vendors" if x is None else
            (data["vendors"].set_index("id").loc[x, "name"] if not data["vendors"].empty else x),
    )
    search = c4.text_input("Search SKU or name", "")

    filtered = recs.copy()
    if selected_cat:
        filtered = filtered[filtered["category"].isin(selected_cat)]
    if selected_status:
        filtered = filtered[filtered["status"].isin(selected_status)]
    if selected_vendor_id is not None:
        filtered = filtered[filtered["vendor_id"] == selected_vendor_id]
    if search:
        mask = filtered["sku"].str.contains(search, case=False, na=False) | filtered["name"].str.contains(search, case=False, na=False)
        filtered = filtered[mask]

    display_cols = ["sku", "name", "category", "status", "on_hand_clinic", "on_hand_wsa", "daily_velocity", "days_of_supply", "moq", "recommended_qty"]
    display = filtered[display_cols].copy()
    display["daily_velocity"] = display["daily_velocity"].round(2)
    display["days_of_supply"] = display["days_of_supply"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "∞")

    st.caption(f"Showing {len(display)} of {len(recs)} SKUs")
    st.dataframe(display, hide_index=True, use_container_width=True)

    _supabase_edit_link("products")


if page == "Reorder Alerts":
    render_reorder_alerts(recs, data)
elif page == "Forecast Detail":
    render_forecast_detail(recs, data)
elif page == "Purchase Log":
    render_purchase_log(recs, data)
elif page == "Vendors":
    render_vendors(recs, data)
elif page == "All Products":
    render_all_products(recs, data)
