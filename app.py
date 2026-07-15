"""Lumati Repurchase System · Streamlit dashboard entrypoint."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEMO_MODE = os.getenv("DEMO_MODE") == "1"

from lib import finance, shopify, square, supabase_io  # noqa: E402
from lib.forecast import calculate_velocity, history_metadata  # noqa: E402
from lib.reorder import ReorderRecommendation, Settings, compute_recommendation  # noqa: E402


# ---------- Altair institutional theme ----------
_LKI = {
    "ink": "#111111", "navy": "#1F2E45", "slate": "#8A93A2",
    "gold": "#B08D3E", "subtle": "#6B7280", "grid": "#E7E9ED",
}


@alt.theme.register("lki_institutional", enable=True)
def _lki_theme():
    return alt.theme.ThemeConfig({
        "config": {
            "font": "Inter",
            "range": {"category": [_LKI["navy"], _LKI["slate"], _LKI["gold"],
                                    "#4A5A75", "#B3BAC5"]},
            "axis": {"labelColor": _LKI["subtle"], "titleColor": _LKI["subtle"],
                     "gridColor": _LKI["grid"], "domainColor": _LKI["subtle"]},
            "legend": {"labelColor": _LKI["subtle"], "titleColor": _LKI["subtle"]},
            "view": {"stroke": None},
        }
    })


# ---------- Streamlit config ----------
# set_page_config MUST be the first Streamlit command; nothing st.* may run before it.
st.set_page_config(
    page_title="Aura Wellness Inventory" if DEMO_MODE else "Lumati Repurchase",
    page_icon="📦",
    layout="wide",
)

# Mirror Streamlit Cloud secrets into os.environ for code that reads via os.environ.
# Done AFTER set_page_config (st.secrets access counts as a Streamlit command).
# Wrapped in broad try/except so missing or unreadable secrets never crash the app.
try:
    _secrets_dict = dict(st.secrets) if st.secrets else {}
except Exception:
    _secrets_dict = {}
for _key, _value in _secrets_dict.items():
    try:
        os.environ.setdefault(str(_key), str(_value))
    except Exception:
        pass

LOGO_URL = "https://shop.lumati.com/cdn/shop/files/lumatllogo_black_nt_hor-500.png?v=1768746788&width=280"
if DEMO_MODE:
    st.sidebar.markdown(
        """
        <div style="text-align:center; padding: 18px 0 6px;">
          <div style="font-family:Inter,sans-serif; font-weight:800; font-size:30px;
                      letter-spacing:0.08em; color:#111111;">AURA</div>
          <div style="font-family:Inter,sans-serif; font-weight:500; font-size:15px;
                      letter-spacing:0.42em; color:#1F2E45;">WELLNESS</div>
          <div style="font-size:9px; letter-spacing:0.3em; color:#6B7280;
                      margin-top:6px;">RESTORATIVE CARE</div>
          <div style="font-size:8px; letter-spacing:0.2em; color:#8A93A2;
                      margin-top:4px;">NEW YORK &middot; LONDON &middot; PARIS</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.logo(LOGO_URL, size="large")

# Load Inter (body/UI) and Source Serif 4 (page headers)
st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Source+Serif+4:opsz,wght@8..60,600..700&display=swap" rel="stylesheet">
    """,
    unsafe_allow_html=True,
)

# Override primary button color in the sidebar only (used for active nav item).
# Keeps the institutional navy primary color for form buttons in the main content area.
# Also hides the top-right toolbar and tightens top padding on each page.
st.markdown(
    """
    <style>
    /* ---- Sidebar nav: link-style menu (no borders, clean text links) ---- */
    /* All sidebar buttons strip borders + background by default */
    section[data-testid="stSidebar"] [data-testid="stButton"] > button,
    section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 5px 12px !important;
        justify-content: flex-start !important;
        text-align: left !important;
        color: #555 !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        border-radius: 6px !important;
        min-height: 0 !important;
        line-height: 1.3 !important;
    }
    /* Tighten gap between nav buttons */
    section[data-testid="stSidebar"] [data-testid="stButton"] {
        margin-bottom: 2px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0px !important;
    }
    /* Streamlit gives sidebar markdown containers margin-bottom: -1rem to offset its
       default 1rem flex gap; with the gap forced to 0 above, that negative margin made
       the brand block's last line underlap the nav (hidden behind the active pill on
       the Overview page). Neutralize it so the brand block keeps its full height. */
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        margin-bottom: 0 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
        background: #F4F4F6 !important;
        color: #111 !important;
    }
    /* Active (primary type) button: subtle grey background + bold dark text */
    section[data-testid="stSidebar"] button[kind="primary"] {
        background: #F0F0F0 !important;
        color: #111 !important;
        font-weight: 700 !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"]:hover {
        background: #E8E8E8 !important;
        color: #111 !important;
    }
    /* Material Symbols icons in sidebar buttons: larger and lighter weight */
    section[data-testid="stSidebar"] [data-testid="stButton"] > button [data-testid="stIconMaterial"],
    section[data-testid="stSidebar"] [data-testid="stButton"] > button .material-symbols {
        font-size: 22px !important;
        margin-right: 6px !important;
        color: #666 !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"] [data-testid="stIconMaterial"] {
        color: #111 !important;
    }
    /* Hide Streamlit's default top-right menu + deploy button */
    #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"] { visibility: hidden; height: 0; }
    /* Prevent button labels (like MTD / YTD / 30D) from wrapping in narrow columns */
    .stButton > button p {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    /* Reduce top padding so headers sit higher on every page */
    .block-container { padding-top: 1.5rem !important; }

    /* ---- Page headers: serif display (Source Serif 4), institutional ---- */
    h1, h2, h3, h4, h5, h6,
    [data-testid="stHeading"] h1,
    [data-testid="stHeading"] h2,
    [data-testid="stHeading"] h3,
    [data-testid="stHeading"] h4,
    [data-testid="stHeading"] h5,
    [data-testid="stHeading"] h6,
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4,
    [data-testid="stMarkdownContainer"] h5,
    [data-testid="stMarkdownContainer"] h6 {
        font-family: 'Source Serif 4', Georgia, serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
        line-height: 1.12 !important;
        color: #111 !important;
    }
    h1, [data-testid="stHeading"] h1 { font-size: 48px !important; margin-bottom: 6px !important; }
    h2, [data-testid="stHeading"] h2 { font-size: 36px !important; margin-bottom: 6px !important; }
    h3, [data-testid="stHeading"] h3 { font-size: 24px !important; margin-bottom: 4px !important; }
    h4, [data-testid="stHeading"] h4 { font-size: 20px !important; margin-bottom: 4px !important; }
    h5, [data-testid="stHeading"] h5 { font-size: 17px !important; margin-bottom: 4px !important; }
    h6, [data-testid="stHeading"] h6 { font-size: 14px !important; margin-bottom: 4px !important; }

    /* ---- Reorder Alerts dashboard ---- */
    .kpi-row { padding: 4px 0; }
    .kpi-tile { padding: 6px 0 14px 0; }
    /* Hairline divider between adjacent KPI tiles inside a row */
    .main [data-testid="stHorizontalBlock"] > [data-testid="column"]:not(:first-child) .kpi-tile {
        border-left: 1px solid #ececee;
        padding-left: 22px;
    }
    .kpi-label {
        font-size: 10.5px; font-weight: 600; letter-spacing: 0.10em;
        text-transform: uppercase; color: #8a8a90; margin-bottom: 8px;
    }
    .kpi-value {
        font-size: 32px; font-weight: 700; color: #111;
        line-height: 1; letter-spacing: -0.02em;
    }
    .kpi-sub { font-size: 12px; color: #8a8a90; margin-top: 6px; }
    .kpi-section-divider {
        border: none; border-top: 1px solid #ececee; margin: 18px 0 6px 0;
    }

    .alert-th {
        font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
        text-transform: uppercase; color: #6b6b6b; padding: 6px 0;
    }
    .alert-th-right { text-align: right; }
    .alert-row-divider {
        border: none; border-top: 1px solid #e5e5e5; margin: 0;
    }

    .alert-status { font-size: 14px; color: #111; padding-top: 8px; }
    .alert-dot {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        margin-right: 8px; vertical-align: middle;
    }
    .alert-dot-now  { background: #111; }
    .alert-dot-soon { background: transparent; border: 1.5px solid #111; }
    .alert-status-now  { font-weight: 600; color: #111; }
    .alert-status-soon { font-weight: 400; color: #6b6b6b; }

    .alert-sku  { font-size: 14px; font-weight: 600; color: #111; padding-top: 6px; }
    .alert-name { font-size: 12px; color: #6b6b6b; margin-top: 2px; }
    .alert-cell { font-size: 14px; color: #111; padding-top: 8px; text-align: right; }

    .alert-detail {
        font-size: 13px; color: #555; padding: 6px 0 10px 0;
        margin-left: 0; line-height: 1.6;
    }

    /* Quiet the chevron toggle button in alert rows */
    .main div[data-testid="column"]:last-child button[kind="secondary"] {
        background: transparent !important; border: none !important;
        color: #6b6b6b !important; padding: 2px 6px !important;
        min-height: 0 !important; font-size: 16px !important; box-shadow: none !important;
    }
    .main div[data-testid="column"]:last-child button[kind="secondary"]:hover {
        color: #111 !important; background: transparent !important;
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


# SKU prefixes to exclude from the entire dashboard (services, not physical products)
EXCLUDED_SKU_PREFIXES: tuple[str, ...] = ("LUM-SS-", "LUM-SER-")


def _exclude_skus(df: pd.DataFrame, sku_col: str = "sku") -> pd.DataFrame:
    """Drop rows whose SKU starts with any of EXCLUDED_SKU_PREFIXES."""
    if df.empty or sku_col not in df.columns:
        return df
    mask = df[sku_col].apply(
        lambda s: isinstance(s, str) and any(s.startswith(p) for p in EXCLUDED_SKU_PREFIXES)
    )
    return df[~mask].copy()


@st.cache_data(ttl=3600, show_spinner="Loading data...")
def load_all_data() -> dict[str, Any]:
    """Pull everything we need for a dashboard session. Returns a dict of DataFrames + Settings."""
    if DEMO_MODE:
        from lib import demo_data
        return demo_data.load_all_data_demo()

    client = _get_supabase_client()
    products = supabase_io.fetch_products(client)
    vendors = supabase_io.fetch_vendors(client)
    settings = supabase_io.fetch_settings(client)
    purchase_log = supabase_io.fetch_purchase_log(client)

    shop_products = shopify.fetch_products()      # sku, product_name, on_hand, ...

    # Combined sales: Shopify + Square (each tagged with `source` column)
    days = settings_window(settings)
    shopify_sales = shopify.fetch_daily_sales(days_back=days)
    if not shopify_sales.empty:
        shopify_sales["source"] = "shopify"
    try:
        square_sales = square.fetch_daily_sales(days_back=days)
    except Exception:
        square_sales = pd.DataFrame(columns=["sku", "date", "units", "revenue"])
    if not square_sales.empty:
        square_sales["source"] = "square"

    if shopify_sales.empty and square_sales.empty:
        sales = pd.DataFrame(columns=["sku", "date", "units", "revenue", "source"])
    else:
        sales = pd.concat(
            [df for df in (shopify_sales, square_sales) if not df.empty],
            ignore_index=True,
        )

    # Order-level adjustments (discounts + refunds) for net-revenue KPI
    shopify_adj = shopify.fetch_daily_adjustments(days_back=days)
    if not shopify_adj.empty:
        shopify_adj["source"] = "shopify"
    try:
        square_adj = square.fetch_daily_adjustments(days_back=days)
    except Exception:
        square_adj = pd.DataFrame(columns=["date", "discounts", "refunds"])
    if not square_adj.empty:
        square_adj["source"] = "square"

    if shopify_adj.empty and square_adj.empty:
        adjustments = pd.DataFrame(columns=["date", "discounts", "refunds", "source"])
    else:
        adjustments = pd.concat(
            [df for df in (shopify_adj, square_adj) if not df.empty],
            ignore_index=True,
        )

    # Exclude service / non-product SKUs everywhere
    products = _exclude_skus(products)
    shop_products = _exclude_skus(shop_products)
    sales = _exclude_skus(sales)

    return {
        "products": products,
        "vendors": vendors,
        "settings": settings,
        "purchase_log": purchase_log,
        "shop_products": shop_products,
        "sales": sales,
        "adjustments": adjustments,
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

    # SKUs with an outstanding purchase order (placed or shipped — not received/cancelled)
    purchase_log = data.get("purchase_log", pd.DataFrame())
    on_order_skus: set[str] = set()
    if not purchase_log.empty and "status" in purchase_log.columns and "sku" in purchase_log.columns:
        outstanding = purchase_log[purchase_log["status"].isin(["placed", "shipped"])]
        on_order_skus = set(outstanding["sku"].dropna().tolist())

    merge_cols = ["sku", "on_hand", "on_hand_clinic", "on_hand_wsa", "product_name"]
    if "image_url" in shop.columns:
        merge_cols.append("image_url")
    merged = products.merge(
        shop[merge_cols],
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

        # Override reorder_now/reorder_soon with "on_order" if there's an outstanding PO.
        # Healthy/slow/dead/etc. are unaffected — they don't need a reorder regardless.
        status = rec.status
        if sku in on_order_skus and status in ("reorder_now", "reorder_soon"):
            status = "on_order"

        rows.append({
            "sku": sku,
            "name": p.get("name") or p["product_name"],
            "category": p.get("category"),
            "vendor_id": p.get("vendor_id"),
            "unit_cost": float(p["unit_cost"]) if p.get("unit_cost") is not None else None,
            "moq": int(p.get("moq") or 1),
            "image_url": p.get("image_url") or "",
            "on_hand": rec.on_hand,
            "on_hand_clinic": int(p["on_hand_clinic"]),
            "on_hand_wsa": int(p["on_hand_wsa"]),
            "daily_velocity": rec.daily_velocity,
            "days_of_supply": rec.days_of_supply,
            "status": status,
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
    ("Overview",          ":material/dashboard:"),
    ("Reorder Alerts",    ":material/notifications_active:"),
    ("All Products",      ":material/inventory_2:"),
    ("Forecast Detail",   ":material/trending_up:"),
    ("Purchase Log",      ":material/receipt_long:"),
    ("Vendors",           ":material/store:"),
]
PAGES = [label for label, _ in NAV_ITEMS]

if "page" not in st.session_state:
    st.session_state.page = "Overview"

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

if not recs.empty and not DEMO_MODE:
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
_ROW_COL_WIDTHS = [1.3, 4.0, 1.1, 1.1, 1.1, 1.3, 0.7]


def _kpi_tile(label: str, value: str, subline: str | None = None) -> str:
    sub = f"<div class='kpi-sub'>{subline}</div>" if subline else ""
    return (
        f"<div class='kpi-tile'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value'>{value}</div>"
        f"{sub}"
        f"</div>"
    )


def _product_cell_html(r: pd.Series) -> str:
    img_url = r.get("image_url") or ""
    if img_url:
        img_html = (
            f"<img src='{img_url}' "
            f"style='width:40px;height:40px;object-fit:cover;border-radius:4px;flex-shrink:0;'/>"
        )
    else:
        img_html = (
            "<div style='width:40px;height:40px;border-radius:4px;"
            "background:#f2f2f2;flex-shrink:0;'></div>"
        )
    return (
        f"<div style='display:flex;gap:12px;align-items:center;'>"
        f"{img_html}"
        f"<div>"
        f"<div class='alert-sku'>{r['sku']}</div>"
        f"<div class='alert-name'>{r['name']}</div>"
        f"</div>"
        f"</div>"
    )


def _render_alert_row(r: pd.Series, vendors, expanded_key: str) -> None:
    is_now = r["status"] == "reorder_now"
    dot_class = "alert-dot-now" if is_now else "alert-dot-soon"
    label_class = "alert-status-now" if is_now else "alert-status-soon"
    label = "Now" if is_now else "Soon"

    days = r["days_of_supply"]
    days_str = f"{days:.1f} d" if pd.notna(days) else "∞"

    is_expanded = st.session_state.get(expanded_key, False)
    chevron = "▾" if is_expanded else "▸"

    cost = r.get("recommended_cost")
    cost_str = f"${cost:,.0f}" if pd.notna(cost) else "-"

    cols = st.columns(_ROW_COL_WIDTHS, vertical_alignment="center")
    cols[0].markdown(
        f"<div class='alert-status'>"
        f"<span class='alert-dot {dot_class}'></span>"
        f"<span class='{label_class}'>{label}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    cols[1].markdown(_product_cell_html(r), unsafe_allow_html=True)
    cols[2].markdown(f"<div class='alert-cell'>{int(r['on_hand'])}</div>", unsafe_allow_html=True)
    cols[3].markdown(f"<div class='alert-cell'>{days_str}</div>", unsafe_allow_html=True)
    cols[4].markdown(f"<div class='alert-cell'>{int(r['recommended_qty'])}</div>", unsafe_allow_html=True)
    cols[5].markdown(f"<div class='alert-cell'>{cost_str}</div>", unsafe_allow_html=True)
    if cols[6].button(chevron, key=f"toggle_{r['sku']}", type="secondary"):
        st.session_state[expanded_key] = not is_expanded
        st.rerun()

    if is_expanded:
        vendor_name = None
        if vendors is not None and pd.notna(r["vendor_id"]) and r["vendor_id"] in vendors.index:
            vendor_name = vendors.loc[r["vendor_id"], "name"]
        vendor_str = vendor_name or "-"
        unit_cost = r.get("unit_cost")
        unit_cost_str = f"${unit_cost:,.2f}" if pd.notna(unit_cost) else "-"
        velocity = r["daily_velocity"]
        velocity_str = f"{velocity:.2f}" if pd.notna(velocity) else "-"
        days = r["days_of_supply"]
        days_str = f"{days:.1f}" if pd.notna(days) else "∞"

        detail_cols = st.columns(_ROW_COL_WIDTHS)
        detail_cols[1].markdown(
            f"<div class='alert-detail'>"
            f"<b>Inventory</b>: Clinic {int(r['on_hand_clinic'])}  ·  WSA {int(r['on_hand_wsa'])}  ·  Total {int(r['on_hand'])}<br>"
            f"<b>Velocity</b>: {velocity_str} units/day  ·  <b>Days of supply</b>: {days_str}<br>"
            f"<b>Cost math</b>: {int(r['recommended_qty'])} units × {unit_cost_str} = {cost_str}<br>"
            f"<b>Vendor</b>: {vendor_str}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr class='alert-row-divider'>", unsafe_allow_html=True)


STATUS_COLORS = {
    "reorder_now":          "#C44757",
    "reorder_soon":         "#E0A53B",
    "healthy":              "#5A9A6E",
    "slow":                 "#9A9AA0",
    "dead":                 "#6B6B70",
    "insufficient_history": "#C0C0C5",
    "manual_override":      "#888888",
    "on_order":             "#6FA3D4",  # calm blue - outstanding PO is being handled
}

# Institutional categorical palette used across dashboard charts
PASTEL_PALETTE = [
    "#1F2E45",  # navy
    "#8A93A2",  # slate
    "#B08D3E",  # gold
    "#4A5A75",  # steel
    "#8C4A4A",  # brick
    "#6B7A92",  # blue-slate
    "#C9A96A",  # muted gold
    "#A3ABB8",  # cool gray
]

# Fixed category-to-color map. Keeps Hydrogen Equipment as navy always.
# Unknown categories fall back to the rest of PASTEL_PALETTE in deterministic order.
CATEGORY_COLORS: dict[str, str] = {
    "Hydrogen Equipment": "#1F2E45",  # navy (locked per user request)
    "Supplement":         "#8A93A2",  # slate
    "Light Equipment":    "#B08D3E",  # gold
    "Detect Test":        "#4A5A75",  # steel
}


def _category_color_scale(categories_in_data) -> "alt.Scale":
    """Build an Altair scale with consistent colors for known categories."""
    seen_colors = set(CATEGORY_COLORS.values())
    fallback = [c for c in PASTEL_PALETTE if c not in seen_colors]
    domain: list[str] = []
    range_colors: list[str] = []
    fb_idx = 0
    for cat in sorted(categories_in_data):
        if not isinstance(cat, str):
            continue
        domain.append(cat)
        if cat in CATEGORY_COLORS:
            range_colors.append(CATEGORY_COLORS[cat])
        else:
            range_colors.append(fallback[fb_idx % len(fallback)])
            fb_idx += 1
    return alt.Scale(domain=domain, range=range_colors)


def _fmt_compact(n: float, prefix: str = "") -> str:
    """Compact number format: 12500 -> '12.5K', 2_500_000 -> '2.5M', 999 -> '999'."""
    if n is None:
        return f"{prefix}0"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return f"{prefix}0"
    abs_n = abs(n)
    if abs_n >= 1_000_000_000:
        return f"{prefix}{n/1_000_000_000:.1f}B"
    if abs_n >= 1_000_000:
        return f"{prefix}{n/1_000_000:.1f}M"
    if abs_n >= 1_000:
        return f"{prefix}{n/1_000:.1f}K"
    return f"{prefix}{n:,.0f}"


def _delta_html(delta_pct: float | None, font_size: str = "clamp(11px,1vw,13px)") -> str:
    """Render a colored % delta indicator. Green for up, red for down."""
    if delta_pct is None:
        return ""
    if delta_pct >= 0:
        arrow, color = "↑", "#16A34A"
    else:
        arrow, color = "↓", "#DC2626"
    return (
        f'<span style="color:{color};font-size:{font_size};font-weight:700;'
        f'margin-left:10px;vertical-align:middle;white-space:nowrap;">'
        f'{arrow}&nbsp;{abs(delta_pct):.1f}%</span>'
    )


def _kpi_card(
    label: str,
    value: str,
    sub: str | None = None,
    bg: str = "#F4F4F6",
    large: bool = False,
    secondary_label: str | None = None,
    secondary_value: str | None = None,
    delta_pct: float | None = None,
    corner_text: str | None = None,
    secondary_corner_text: str | None = None,
) -> str:
    """Render a KPI as a styled card. Returns HTML string for st.markdown(unsafe_allow_html=True).

    The HTML is intentionally NOT indented · Streamlit's CommonMark parser would otherwise
    treat 4-space-indented HTML as a code block.
    Font sizes use clamp() so text scales smoothly when the card is narrow.
    Pass `large=True` for a hero/featured card with a much bigger value.
    """
    sub_html = (
        f'<div style="font-size:clamp(9px,0.7vw,11px);color:#888;margin-top:4px;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{sub}</div>'
        if sub else ''
    )
    if large:
        padding = "16px 20px"
        label_size = "clamp(10px,0.75vw,12px)"
        value_size = "clamp(28px,3vw,44px)"
        secondary_label_size = "clamp(9px,0.7vw,11px)"
        secondary_value_size = "clamp(14px,1.4vw,20px)"
    else:
        padding = "14px 16px"
        label_size = "clamp(9px,0.7vw,11px)"
        value_size = "clamp(18px,2vw,28px)"
        secondary_label_size = "clamp(8px,0.6vw,10px)"
        secondary_value_size = "clamp(11px,1.1vw,15px)"

    # Header row: label left-aligned, optional corner text top-right (e.g., margin %)
    corner_html = (
        f'<span style="font-size:clamp(9px,0.7vw,11px);font-weight:400;color:#888;'
        f'letter-spacing:0.02em;">{corner_text}</span>'
        if corner_text else ''
    )
    label_row_html = (
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;">'
        f'<span style="font-size:{label_size};font-weight:700;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:#6b6b73;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label}</span>'
        f'{corner_html}'
        f'</div>'
    )

    secondary_html = ""
    if secondary_label and secondary_value:
        sec_corner_html = (
            f'<span style="font-size:clamp(9px,0.7vw,11px);font-weight:400;color:#888;'
            f'letter-spacing:0.02em;">{secondary_corner_text}</span>'
            if secondary_corner_text else ''
        )
        # Top-right corner of the secondary section (so it pairs with the secondary value/label)
        secondary_html = (
            f'<div style="margin-top:10px;padding-top:8px;border-top:1px solid #E2E2E5;">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
            f'<span style="font-size:{secondary_label_size};font-weight:700;letter-spacing:0.08em;'
            f'text-transform:uppercase;color:#6b6b73;">{secondary_label}</span>'
            f'{sec_corner_html}'
            f'</div>'
            f'<div style="font-size:{secondary_value_size};font-weight:800;color:#111;'
            f"font-family:'Inter',sans-serif;letter-spacing:-0.01em;margin-top:2px;"
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{secondary_value}</div>'
            f'</div>'
        )

    delta_font = "clamp(12px,1.1vw,15px)" if large else "clamp(10px,0.9vw,12px)"
    delta_html = _delta_html(delta_pct, font_size=delta_font)

    return (
        f'<div style="background:{bg};border-radius:10px;padding:{padding};min-width:0;">'
        f'{label_row_html}'
        f'<div style="font-size:{value_size};font-weight:900;color:#111;line-height:1.05;'
        f"letter-spacing:-0.02em;font-family:'Inter',sans-serif;"
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
        f'<span style="vertical-align:middle;">{value}</span>{delta_html}'
        f'</div>'
        f'{sub_html}'
        f'{secondary_html}'
        f'</div>'
    )


def _date_range_picker(key_prefix: str = "overview", default_days: int = 90) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calendar + quick-preset date range picker. Returns (start, end) Timestamps."""
    from datetime import date as _date

    today = datetime.now().date()
    cal_key = f"{key_prefix}_calendar"
    if cal_key not in st.session_state:
        st.session_state[cal_key] = (today - timedelta(days=default_days), today)

    # Quick presets: rolling windows | to-date windows
    _q_start_month = ((today.month - 1) // 3) * 3 + 1
    presets = [
        ("7D",  lambda: (today - timedelta(days=7),   today)),
        ("30D", lambda: (today - timedelta(days=30),  today)),
        ("60D", lambda: (today - timedelta(days=60),  today)),
        ("90D", lambda: (today - timedelta(days=90),  today)),
        ("MTD", lambda: (_date(today.year, today.month, 1), today)),
        ("QTD", lambda: (_date(today.year, _q_start_month, 1), today)),
        ("YTD", lambda: (_date(today.year, 1, 1),     today)),
    ]
    # 8 columns: 4 rolling, thin divider, 3 to-date
    chip_cols = st.columns([1, 1, 1, 1, 0.18, 1, 1, 1])
    btn_cols = [chip_cols[0], chip_cols[1], chip_cols[2], chip_cols[3],
                chip_cols[5], chip_cols[6], chip_cols[7]]
    chip_cols[4].markdown(
        "<div style='border-left:1px solid #d4d4d8;height:32px;margin:4px auto 0;'></div>",
        unsafe_allow_html=True,
    )
    for i, (label, getter) in enumerate(presets):
        if btn_cols[i].button(label, key=f"{key_prefix}_p_{label}", use_container_width=True):
            st.session_state[cal_key] = getter()
            st.rerun()

    # Calendar
    custom = st.date_input(
        "Or pick a range",
        max_value=today,
        key=cal_key,
        format="MM/DD/YYYY",
    )

    if isinstance(custom, tuple) and len(custom) == 2 and custom[0] and custom[1]:
        start, end = custom
    elif isinstance(custom, tuple) and len(custom) == 1:
        start, end = custom[0], today
    else:
        start, end = today - timedelta(days=default_days), today

    return pd.Timestamp(start), pd.Timestamp(end)


def _hover_line_chart(
    df: pd.DataFrame,
    x_field: str = "date",
    y_field: str = "revenue",
    y_format: str = "$,.0f",
    height: int = 200,
    color: str = "#111",
    tooltip_extra: list | None = None,
    x_format: str | None = None,
    x_tick_count: str | int | None = None,
) -> "alt.LayerChart":
    """Interactive Altair line chart with hover guideline + dot + value label.

    df must have x_field (temporal) and y_field (quantitative).
    x_format: D3 format string for x-axis tick labels (e.g. "%b" -> "Jan, Feb").
    x_tick_count: "month", "week", "year", or an int.
    """
    nearest = alt.selection_point(nearest=True, on="pointerover", fields=[x_field], empty=False)

    x_axis_kwargs: dict[str, Any] = {"title": None, "labelAngle": 0}
    if x_format:
        x_axis_kwargs["format"] = x_format
    if x_tick_count is not None:
        x_axis_kwargs["tickCount"] = x_tick_count

    base = alt.Chart(df).encode(x=alt.X(f"{x_field}:T", axis=alt.Axis(**x_axis_kwargs)))

    line = base.mark_line(color=color, strokeWidth=2.5).encode(
        y=alt.Y(f"{y_field}:Q", axis=alt.Axis(title=None, format=y_format)),
    )

    # Invisible wide selection layer for easier hover targeting
    selectors = base.mark_point().encode(opacity=alt.value(0)).add_params(nearest)

    points = line.mark_point(size=90, color=color, filled=True).encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0))
    )

    tooltip_list = [
        alt.Tooltip(f"{x_field}:T", title="Date", format="%b %d, %Y"),
        alt.Tooltip(f"{y_field}:Q", title=y_field.title(), format=y_format),
    ]
    if tooltip_extra:
        tooltip_list.extend(tooltip_extra)
    elif "units" in df.columns and y_field != "units":
        tooltip_list.append(alt.Tooltip("units:Q", title="Units"))

    hover_points = line.mark_point(size=120, color=color, filled=True, opacity=0).encode(
        opacity=alt.condition(nearest, alt.value(0.001), alt.value(0)),
        tooltip=tooltip_list,
    )

    text = line.mark_text(align="left", dx=8, dy=-12, color="#111", fontSize=12, fontWeight=600).encode(
        text=alt.condition(nearest, alt.Text(f"{y_field}:Q", format=y_format), alt.value(" "))
    )

    rules = base.mark_rule(color="#bbb").encode().transform_filter(nearest)

    # Extra left padding: Vega measures y-axis label widths before the Inter
    # webfont applies, so wide currency labels (e.g. "$5,000,000") otherwise
    # get their leading characters clipped at the chart's left edge.
    return alt.layer(line, selectors, points, hover_points, rules, text).properties(
        height=height, padding={"left": 16, "top": 5, "right": 5, "bottom": 5}
    )


def render_dashboard(recs: pd.DataFrame, data: dict) -> None:
    st.header("Overview")

    # Apply any pending state changes from a previous-run click event,
    # BEFORE the multiselect widget with the same key is instantiated.
    if "ov_cat_pending" in st.session_state:
        st.session_state["ov_cat"] = st.session_state.pop("ov_cat_pending")

    if recs.empty:
        st.info("No products loaded yet. Run `seed_products.py` first.")
        return

    sales = data.get("sales", pd.DataFrame())
    has_revenue = (not sales.empty) and ("revenue" in sales.columns)

    # ----------------------------------------------------------------
    # TOP SECTION: filters on the left, KPI cards on the right
    # ----------------------------------------------------------------
    vendors_df = data.get("vendors", pd.DataFrame())
    vendor_options = vendors_df["id"].tolist() if not vendors_df.empty else []
    vendor_names = vendors_df.set_index("id")["name"].to_dict() if not vendors_df.empty else {}
    name_by_sku = recs.set_index("sku")["name"].to_dict()
    all_categories = sorted([c for c in recs["category"].dropna().unique()])

    top_left, top_right = st.columns([5, 4])

    with top_left:
        range_start, range_end = _date_range_picker(key_prefix="overview", default_days=90)
        source_col, toggle_col = st.columns([3, 3])
        with source_col:
            source = st.radio(
                "Sales source",
                ["Both", "Shopify", "Square"],
                horizontal=True,
                key="ov_source",
            )
        with toggle_col:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            exclude_high = st.toggle(
                "Exclude products over $1,000",
                value=False,
                key="ov_exclude_high",
            )

        fr = st.columns(3)
        with fr[0]:
            selected_cats = st.multiselect(
                "Category",
                all_categories,
                placeholder="All",
                key="ov_cat",
            )
        with fr[1]:
            selected_vendor_ids = st.multiselect(
                "Vendor",
                vendor_options,
                format_func=lambda v: vendor_names.get(v, str(v)),
                placeholder="All",
                key="ov_vendor",
            )
        with fr[2]:
            selected_skus = st.multiselect(
                "Product",
                sorted(recs["sku"].tolist()),
                format_func=lambda s: f"{s} · {name_by_sku.get(s, '')}",
                placeholder="All",
                key="ov_sku",
            )

    range_label = f"{range_start.strftime('%b %d, %Y')} – {range_end.strftime('%b %d, %Y')}"

    # ----------------------------------------------------------------
    # APPLY FILTERS
    # ----------------------------------------------------------------
    filt_recs = recs.copy()
    if selected_cats:
        filt_recs = filt_recs[filt_recs["category"].isin(selected_cats)]
    if selected_vendor_ids:
        filt_recs = filt_recs[filt_recs["vendor_id"].isin(selected_vendor_ids)]
    if selected_skus:
        filt_recs = filt_recs[filt_recs["sku"].isin(selected_skus)]

    if has_revenue:
        filt_sales = sales[(sales["date"] >= range_start) & (sales["date"] <= range_end)].copy()
        # Source filter (Shopify / Square / Both)
        if "source" in filt_sales.columns and source != "Both":
            filt_sales = filt_sales[filt_sales["source"] == source.lower()]
        # Restrict sales to SKUs that pass the rec-side filters (vendor/sku, EXCLUDING category for now)
        if selected_vendor_ids or selected_skus:
            recs_for_vs = recs.copy()
            if selected_vendor_ids:
                recs_for_vs = recs_for_vs[recs_for_vs["vendor_id"].isin(selected_vendor_ids)]
            if selected_skus:
                recs_for_vs = recs_for_vs[recs_for_vs["sku"].isin(selected_skus)]
            filt_sales = filt_sales[filt_sales["sku"].isin(set(recs_for_vs["sku"].tolist()))]
        # Exclude high-ticket if requested
        if exclude_high and not filt_sales.empty:
            sku_tot = filt_sales.groupby("sku", as_index=False)[["units", "revenue"]].sum()
            sku_tot["avg"] = sku_tot["revenue"] / sku_tot["units"].clip(lower=1)
            excluded_skus = set(sku_tot.loc[sku_tot["avg"] > 1000, "sku"])
            filt_sales = filt_sales[~filt_sales["sku"].isin(excluded_skus)]

        # filt_sales NOW reflects everything EXCEPT category filter — perfect for the
        # proportional category bar so all categories stay clickable.
        filt_sales_all_cats = filt_sales

        # Apply the category filter to produce the final filt_sales used by line / top products / etc.
        if selected_cats:
            allowed_with_cat = set(filt_recs["sku"].tolist())
            filt_sales = filt_sales[filt_sales["sku"].isin(allowed_with_cat)]
    else:
        filt_sales = pd.DataFrame()
        filt_sales_all_cats = pd.DataFrame()
        excluded_skus = set()

    # ----------------------------------------------------------------
    # KPI CARDS (rendered in top_right column, 3x2 grid)
    # ----------------------------------------------------------------
    total_revenue = float(filt_sales["revenue"].sum()) if not filt_sales.empty else 0.0
    total_units = int(filt_sales["units"].sum()) if not filt_sales.empty else 0
    days_in_range = max(1, (range_end - range_start).days + 1)
    avg_daily_rev = total_revenue / days_in_range
    now_count = int((filt_recs["status"] == "reorder_now").sum())
    soon_count = int((filt_recs["status"] == "reorder_soon").sum())

    # ---- Net revenue (per-line, respects ALL filters including category) ----
    # filt_sales has a `net_revenue` column populated per line item by fetch_daily_sales:
    # Shopify net = gross - per-line discount allocations - per-line refunds
    # Square net  = gross - per-line discount
    if not filt_sales.empty and "net_revenue" in filt_sales.columns:
        net_revenue = float(filt_sales["net_revenue"].sum())
    else:
        # Fallback to order-level adjustments only when per-line data unavailable
        adjustments = data.get("adjustments", pd.DataFrame())
        total_discounts = 0.0
        total_refunds = 0.0
        if not adjustments.empty:
            adj = adjustments[
                (adjustments["date"] >= range_start) & (adjustments["date"] <= range_end)
            ]
            if "source" in adj.columns and source != "Both":
                adj = adj[adj["source"] == source.lower()]
            if not adj.empty:
                total_discounts = float(adj["discounts"].sum())
                total_refunds = float(adj["refunds"].sum())
        net_revenue = max(0.0, total_revenue - total_discounts - total_refunds)

    # ---- Profit margin = (revenue - COGS) / revenue ----
    # COGS = sum of (units * unit_cost) per line item, looked up from products table.
    total_cogs = 0.0
    if not filt_sales.empty:
        cost_lookup = recs.set_index("sku")["unit_cost"].to_dict() if "unit_cost" in recs.columns else {}
        cogs_series = filt_sales.apply(
            lambda r: (r["units"] * cost_lookup.get(r["sku"], 0)) if cost_lookup.get(r["sku"]) is not None else 0,
            axis=1,
        )
        total_cogs = float(cogs_series.sum())
    gross_margin_pct = ((total_revenue - total_cogs) / total_revenue * 100) if total_revenue > 0 else None
    net_margin_pct = ((net_revenue - total_cogs) / net_revenue * 100) if net_revenue > 0 else None

    # ---- Prior-period comparison (same length, immediately before current range) ----
    prior_end = range_start - pd.Timedelta(days=1)
    prior_start = prior_end - pd.Timedelta(days=days_in_range - 1)
    prior_revenue = 0.0
    prior_units = 0
    if has_revenue:
        prior_sales = sales[(sales["date"] >= prior_start) & (sales["date"] <= prior_end)].copy()
        if "source" in prior_sales.columns and source != "Both":
            prior_sales = prior_sales[prior_sales["source"] == source.lower()]
        if selected_cats or selected_vendor_ids or selected_skus:
            allowed = set(filt_recs["sku"].tolist())
            prior_sales = prior_sales[prior_sales["sku"].isin(allowed)]
        if exclude_high and not prior_sales.empty:
            # Use the same set of excluded SKUs identified for the current period
            prior_sales = prior_sales[~prior_sales["sku"].isin(excluded_skus)]
        if not prior_sales.empty:
            prior_revenue = float(prior_sales["revenue"].sum())
            prior_units = int(prior_sales["units"].sum())
    prior_avg_daily = prior_revenue / days_in_range

    def _pct(curr: float, prior: float) -> float | None:
        if prior <= 0:
            return None
        return (curr - prior) / prior * 100

    rev_delta = _pct(total_revenue, prior_revenue)
    units_delta = _pct(total_units, prior_units)
    avg_delta = _pct(avg_daily_rev, prior_avg_daily)

    # Clean dollar values, margin lives in the top-right corner of each section
    gross_display = _fmt_compact(total_revenue, "$")
    net_value_display = _fmt_compact(net_revenue, "$")
    gross_margin_text = f"{gross_margin_pct:.0f}% margin" if (gross_margin_pct is not None and total_cogs > 0) else None
    net_margin_text = f"{net_margin_pct:.0f}% margin" if (net_margin_pct is not None and total_cogs > 0) else None

    with top_right:
        # Hero Revenue card: margin % in top-right of each section (gross + net)
        st.markdown(
            _kpi_card(
                "Revenue",
                gross_display,
                large=True,
                secondary_label="Net",
                secondary_value=net_value_display,
                delta_pct=rev_delta,
                corner_text=gross_margin_text,
                secondary_corner_text=net_margin_text,
            ),
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        # 4 supporting cards in a 2x2 grid
        r2 = st.columns(2, gap="small")
        r2[0].markdown(_kpi_card("Units sold",  _fmt_compact(total_units),        delta_pct=units_delta), unsafe_allow_html=True)
        r2[1].markdown(_kpi_card("Avg daily $", _fmt_compact(avg_daily_rev, "$"), delta_pct=avg_delta),   unsafe_allow_html=True)
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        r3 = st.columns(2, gap="small")
        r3[0].markdown(_kpi_card("SKUs in scope", _fmt_compact(len(filt_recs))), unsafe_allow_html=True)
        r3[1].markdown(_kpi_card("Reorder Now",   _fmt_compact(now_count)),      unsafe_allow_html=True)

    if exclude_high and excluded_skus:
        st.caption(f"Excluding {len(excluded_skus)} SKU(s) with avg sale price over $1,000")

    st.divider()

    # ----------------------------------------------------------------
    # SINGLE-PRODUCT CONTEXT (only when exactly 1 SKU selected)
    # ----------------------------------------------------------------
    if len(selected_skus) == 1 and not filt_recs.empty:
        p = filt_recs.iloc[0]
        hc = st.columns([1, 5])
        if p.get("image_url"):
            hc[0].image(p["image_url"], width=110)
        hc[1].markdown(
            f"""<div style="padding-top:8px;">
                <div style="font-family:'Source Serif 4',Georgia,serif;font-size:24px;font-weight:600;
                            letter-spacing:-0.01em;color:#111;line-height:1.1;">{p['name']}</div>
                <div style="color:#888;font-size:11px;letter-spacing:1px;text-transform:uppercase;
                            font-family:'SF Mono','Menlo',monospace;margin-top:6px;">SKU&nbsp;·&nbsp;{p['sku']}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        st.divider()

    # ----------------------------------------------------------------
    # SECTION: Single line chart with Revenue / Units toggle
    # ----------------------------------------------------------------
    title_row = st.columns([3, 2])
    title_row[0].markdown("##### Sales Trend")
    with title_row[1]:
        metric = st.radio(
            "Metric",
            ["Revenue", "Units"],
            horizontal=True,
            key="ov_trend_metric",
            label_visibility="collapsed",
        )
    # Auto-pick granularity based on range
    if days_in_range > 60:
        gran_freq, gran_label = "MS", "month"
    elif days_in_range > 21:
        gran_freq, gran_label = "W-MON", "week"
    else:
        gran_freq, gran_label = None, "day"
    st.caption(f"{range_label} · grouped by {gran_label}")

    if filt_sales.empty:
        st.info("No sales data for the selected filters / range.")
    else:
        # ---- Proportional category map (clickable to filter) ----
        # Use the version WITHOUT category filter so all categories stay in the bar
        sales_cat = filt_sales_all_cats.merge(recs[["sku", "category"]], on="sku", how="left").dropna(subset=["category"])
        cat_rev = sales_cat.groupby("category", as_index=False)["revenue"].sum()
        if not cat_rev.empty and cat_rev["revenue"].sum() > 0:
            cat_rev["pct"] = (cat_rev["revenue"] / cat_rev["revenue"].sum() * 100).round(1)
            cat_rev["pct_label"] = cat_rev["pct"].astype(str) + "%"
            cat_rev["_y"] = "Total"
            cat_rev = cat_rev.sort_values("revenue", ascending=False)

            cat_area_sel = alt.selection_point(fields=["category"], on="click", name="area_cat_click")

            area = (
                alt.Chart(cat_rev)
                .mark_bar(cursor="pointer", stroke="white", strokeWidth=2)
                .encode(
                    x=alt.X("revenue:Q", stack="zero", axis=None),
                    y=alt.Y("_y:N", axis=None),
                    color=alt.Color(
                        "category:N",
                        scale=_category_color_scale(cat_rev["category"].unique()),
                        legend=alt.Legend(
                            orient="bottom",
                            title=None,
                            columns=6,
                            symbolSize=180,
                            labelFontSize=12,
                            labelFontWeight=600,
                        ),
                    ),
                    opacity=(
                        alt.condition(
                            alt.FieldOneOfPredicate(field="category", oneOf=list(selected_cats)),
                            alt.value(1.0),
                            alt.value(0.35),
                        ) if selected_cats else alt.condition(cat_area_sel, alt.value(1.0), alt.value(0.45))
                    ),
                    tooltip=[
                        alt.Tooltip("category:N", title="Category"),
                        alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                        alt.Tooltip("pct_label:N", title="Share"),
                    ],
                )
                .add_params(cat_area_sel)
                .properties(height=160)
            )

            area_event = st.altair_chart(
                area,
                use_container_width=True,
                on_select="rerun",
                key="ov_area_cat",
            )
            if area_event and getattr(area_event, "selection", None):
                clicked = area_event.selection.get("area_cat_click", [])
                clicked_cats = (
                    [c.get("category") for c in clicked if isinstance(c, dict) and c.get("category")]
                    if isinstance(clicked, list) else []
                )
                # Only react to NON-EMPTY clicks — Streamlit also fires on_select with an empty
                # selection on rerun when the chart redraws with no internal state, which would
                # incorrectly clear the filter. Deselect via the "× Clear" button.
                if clicked_cats and sorted(clicked_cats) != sorted(selected_cats):
                    st.session_state["ov_cat_pending"] = clicked_cats
                    st.rerun()

            # Caption + explicit Clear button when a category is currently selected
            cap_col, btn_col = st.columns([4, 1])
            cap_col.caption("Click a category segment above to filter. Click again (or use Clear) to undo.")
            if selected_cats:
                if btn_col.button("× Clear category", key="ov_clear_cat", use_container_width=True):
                    st.session_state["ov_cat_pending"] = []
                    st.rerun()

        # ---- Line chart ----
        try:
            df_for_group = filt_sales.copy()
            df_for_group["date"] = pd.to_datetime(df_for_group["date"])
            if gran_freq:
                grouped = (
                    df_for_group.groupby(pd.Grouper(key="date", freq=gran_freq))[["units", "revenue"]]
                    .sum()
                    .reset_index()
                )
            else:
                grouped = (
                    df_for_group.groupby("date")[["units", "revenue"]]
                    .sum()
                    .reset_index()
                )
            grouped = grouped[grouped["date"].notna()].sort_values("date")
        except Exception as e:
            st.error(f"Failed to group sales: {e}")
            grouped = pd.DataFrame()

        if grouped.empty:
            st.info("No sales data after grouping.")
        else:
            y_field = "revenue" if metric == "Revenue" else "units"
            y_format = "$,.0f" if metric == "Revenue" else ",.0f"
            # Source-aware line color: navy when Both or Revenue, steel for Units-only
            if source == "Both" or metric == "Revenue":
                color = _LKI["navy"]
            else:
                color = "#4A5A75"  # steel
            # X-axis label format based on aggregation
            if gran_label == "month":
                # Use "Jan 2026" if range spans multiple years, else just "Jan"
                multi_year = (range_end.year - range_start.year) > 0
                x_format = "%b %Y" if multi_year else "%b"
                x_tick_count = "month"
            elif gran_label == "week":
                x_format = "%b %d"
                x_tick_count = "week"
            else:
                x_format = "%b %d"
                x_tick_count = None
            try:
                chart = _hover_line_chart(
                    grouped,
                    y_field=y_field,
                    y_format=y_format,
                    color=color,
                    height=260,
                    x_format=x_format,
                    x_tick_count=x_tick_count,
                )
                st.altair_chart(chart, use_container_width=True)
            except Exception as e:
                st.error(f"Chart render failed: {e}")
                st.dataframe(grouped, use_container_width=True)

    st.divider()

    # ----------------------------------------------------------------
    # SECTION: Top Products by Revenue (full width)
    # ----------------------------------------------------------------
    st.markdown("##### Top Products by Revenue")
    st.caption(range_label)
    if filt_sales.empty:
        st.info("No sales.")
    else:
        # Aggregate units, gross revenue, and net revenue (gracefully default net_revenue=revenue if missing)
        agg_cols = ["units", "revenue"]
        if "net_revenue" in filt_sales.columns:
            agg_cols.append("net_revenue")
        top = (
            filt_sales.groupby("sku", as_index=False)[agg_cols]
            .sum()
            .sort_values("revenue", ascending=False)
            .head(15)
        )
        if "net_revenue" not in top.columns:
            top["net_revenue"] = top["revenue"]
        top["name"] = top["sku"].map(name_by_sku).fillna("-")
        image_by_sku = recs.set_index("sku")["image_url"].to_dict() if "image_url" in recs.columns else {}
        top["image_url"] = top["sku"].map(image_by_sku).fillna("")
        top["revenue"] = top["revenue"].round(2)
        top["net_revenue"] = top["net_revenue"].round(2)
        top["avg_price"] = (top["revenue"] / top["units"].clip(lower=1)).round(2)
        disp = top[["image_url", "sku", "name", "units", "avg_price", "revenue", "net_revenue"]].copy()
        disp.columns = ["Image", "SKU", "Product", "Units", "Avg $", "Revenue", "Net Revenue"]
        st.dataframe(
            disp,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Image": st.column_config.ImageColumn("Image", width="small"),
                "Avg $": st.column_config.NumberColumn(format="$%.2f"),
                "Revenue": st.column_config.NumberColumn(format="$%.0f"),
                "Net Revenue": st.column_config.NumberColumn(format="$%.0f"),
            },
        )

    st.divider()

    # ----------------------------------------------------------------
    # SECTION: Current Inventory Value by Category (full width)
    # ----------------------------------------------------------------
    st.markdown("##### Current Inventory Value by Category")
    st.caption("Current snapshot · does not change with date range")
    recs_inv = filt_recs.copy()
    recs_inv["inv_value"] = recs_inv["unit_cost"] * (recs_inv["on_hand_clinic"] + recs_inv["on_hand_wsa"])
    cat_value = (
        recs_inv.dropna(subset=["category"])
        .groupby("category", as_index=False)["inv_value"]
        .sum()
        .sort_values("inv_value", ascending=True)
    )
    if cat_value.empty or cat_value["inv_value"].sum() == 0:
        st.info("No unit_cost data yet · fill in the products table.")
    else:
        bar_inv = (
            alt.Chart(cat_value)
            .mark_bar()
            .encode(
                y=alt.Y("category:N", sort="-x", axis=alt.Axis(title=None)),
                x=alt.X("inv_value:Q", axis=alt.Axis(title=None, format="$,.0f")),
                color=alt.Color("category:N", scale=_category_color_scale(cat_value["category"].unique()), legend=None),
                tooltip=["category:N", alt.Tooltip("inv_value:Q", format="$,.0f")],
            )
            .properties(height=260)
        )
        st.altair_chart(bar_inv, use_container_width=True)

    st.divider()

    # ----------------------------------------------------------------
    # SECTION: Top 10 Most Urgent (always current state, ignores filters)
    # ----------------------------------------------------------------
    st.markdown("##### Top 10 Most Urgent")
    st.caption("Current state · ignores filters above")
    urgent = recs[recs["status"].isin(["reorder_now", "reorder_soon"])].copy()
    urgent = urgent.sort_values(["status", "days_of_supply"], ascending=[True, True]).head(10)

    if urgent.empty:
        st.success("Nothing needs reordering right now.")
    else:
        for i, (_, r) in enumerate(urgent.iterrows()):
            bg = "#F4F4F6" if i % 2 == 0 else "#FFFFFF"
            status_label = "Reorder Now" if r["status"] == "reorder_now" else "Reorder Soon"
            status_color = STATUS_COLORS.get(r["status"], "#888")
            dos = f"{r['days_of_supply']:.1f}" if r["days_of_supply"] is not None else "∞"
            total = int(r["on_hand_clinic"]) + int(r["on_hand_wsa"])
            img_html = (
                f'<img src="{r["image_url"]}" style="width:50px;height:50px;object-fit:cover;border-radius:6px;">'
                if r.get("image_url") else '<div style="width:50px;height:50px;background:#E5E5E7;border-radius:6px;"></div>'
            )

            st.markdown(
                f"""
                <div style="
                    display:grid;
                    grid-template-columns: 70px minmax(0, 1fr) 160px 90px 90px 90px;
                    align-items:center;
                    gap:18px;
                    padding:12px 18px;
                    background:{bg};
                    border-radius:6px;
                    margin-bottom:2px;
                ">
                    <div>{img_html}</div>
                    <div style="min-width:0;">
                        <div style="font-weight:700;color:#111;font-size:14px;letter-spacing:-0.01em;">{r['sku']}</div>
                        <div style="color:#666;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{r['name']}</div>
                    </div>
                    <div style="font-size:13px;color:#222;">
                        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{status_color};margin-right:8px;vertical-align:middle;"></span>
                        <span style="vertical-align:middle;">{status_label}</span>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.08em;">On hand</div>
                        <div style="font-size:22px;font-weight:800;color:#111;line-height:1.2;">{total}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.08em;">Days left</div>
                        <div style="font-size:22px;font-weight:800;color:#111;line-height:1.2;">{dos}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.08em;">Rec qty</div>
                        <div style="font-size:22px;font-weight:800;color:#111;line-height:1.2;">{int(r['recommended_qty'])}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_reorder_alerts(recs: pd.DataFrame, data: dict) -> None:
    st.header("Reorder Alerts")

    if recs.empty:
        st.info("No products loaded yet. Run `seed_products.py` first.")
        return

    # ---- Financial KPI tiles ----
    inv_value, inv_excluded = finance.inventory_value(recs)
    po_value = finance.open_po_value(data.get("purchase_log", pd.DataFrame()))
    reorder = finance.reorder_needed(recs)
    dead_value, dead_count = finance.dead_stock_value(recs)

    inv_sub = f"{inv_excluded} excluded · no cost" if inv_excluded else None
    reorder_sub = f"Now ${reorder['now']:,.0f} · Soon ${reorder['soon']:,.0f}"
    dead_sub = f"{dead_count} SKUs" if dead_count else None

    fc = st.columns(4)
    fc[0].markdown(_kpi_tile("INVENTORY ON HAND", f"${inv_value:,.0f}", inv_sub), unsafe_allow_html=True)
    fc[1].markdown(_kpi_tile("OPEN POs", f"${po_value:,.0f}"), unsafe_allow_html=True)
    fc[2].markdown(_kpi_tile("REORDER NEEDED", f"${reorder['total']:,.0f}", reorder_sub), unsafe_allow_html=True)
    fc[3].markdown(_kpi_tile("DEAD STOCK", f"${dead_value:,.0f}", dead_sub), unsafe_allow_html=True)

    st.markdown("<hr class='kpi-section-divider'>", unsafe_allow_html=True)

    # ---- Count tiles ----
    total_count = len(recs)
    now_count = int((recs["status"] == "reorder_now").sum())
    soon_count = int((recs["status"] == "reorder_soon").sum())
    healthy_count = int((recs["status"] == "healthy").sum())

    cc = st.columns(4)
    cc[0].markdown(_kpi_tile("TOTAL SKUS", str(total_count)), unsafe_allow_html=True)
    cc[1].markdown(_kpi_tile("REORDER NOW", str(now_count)), unsafe_allow_html=True)
    cc[2].markdown(_kpi_tile("REORDER SOON", str(soon_count)), unsafe_allow_html=True)
    cc[3].markdown(_kpi_tile("HEALTHY", str(healthy_count)), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:32px;'></div>", unsafe_allow_html=True)

    # ---- Alerts table ----
    alerts = recs[recs["status"].isin(["reorder_now", "reorder_soon"])].copy()
    alerts = alerts.sort_values(by=["status", "days_of_supply"], ascending=[True, True])

    if alerts.empty:
        st.success("Nothing needs reordering. Inventory looks healthy.")
        return

    header_cols = st.columns(_ROW_COL_WIDTHS)
    header_cols[0].markdown("<div class='alert-th'>STATUS</div>", unsafe_allow_html=True)
    header_cols[1].markdown("<div class='alert-th'>SKU</div>", unsafe_allow_html=True)
    header_cols[2].markdown("<div class='alert-th alert-th-right'>ON HAND</div>", unsafe_allow_html=True)
    header_cols[3].markdown("<div class='alert-th alert-th-right'>DAYS LEFT</div>", unsafe_allow_html=True)
    header_cols[4].markdown("<div class='alert-th alert-th-right'>NEED</div>", unsafe_allow_html=True)
    header_cols[5].markdown("<div class='alert-th alert-th-right'>EST. COST</div>", unsafe_allow_html=True)
    st.markdown("<hr class='alert-row-divider'>", unsafe_allow_html=True)

    vendors = data["vendors"].set_index("id") if not data["vendors"].empty else None

    for _, r in alerts.iterrows():
        _render_alert_row(r, vendors, expanded_key=f"alert_expanded_{r['sku']}")


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

    requested_sku = st.session_state.pop("fd_selected_sku", None)
    if requested_sku in sku_options:
        st.session_state.fd_sku_picker = requested_sku

    sku = st.selectbox(
        "Pick a SKU",
        sku_options,
        format_func=lambda s: f"{s} · {name_by_sku.get(s, '')}",
        key="fd_sku_picker",
    )
    row = recs[recs["sku"] == sku].iloc[0]

    header_cols = st.columns([1, 5])
    if row.get("image_url"):
        header_cols[0].image(row["image_url"], width=140)
    header_cols[1].markdown(
        f"""
        <div style="padding-top: 12px;">
            <div style="
                color: #111;
                font-family: 'Inter', sans-serif;
                font-size: 32px;
                font-weight: 900;
                letter-spacing: -0.025em;
                line-height: 1.1;
                margin: 0 0 6px 0;
            ">{row['name']}</div>
            <div style="
                color: #8A8A8A;
                font-size: 12px;
                letter-spacing: 1px;
                text-transform: uppercase;
                font-family: 'SF Mono', 'Menlo', 'Monaco', monospace;
            ">SKU&nbsp;·&nbsp;{row['sku']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Status banner ----
    STATUS_DISPLAY = {
        "reorder_now":          ("Reorder Now",                  "#FCE4E4", "#8A2A2A"),
        "reorder_soon":         ("Reorder Soon",                 "#FFF3D6", "#7A5A0E"),
        "on_order":             ("On Order",                     "#DCE7F2", "#1E3A5F"),
        "healthy":              ("Healthy",                      "#E4F4E4", "#1F5A2A"),
        "slow":                 ("Slow Mover",                   "#F0F0F0", "#444444"),
        "dead":                 ("Inactive · No Recent Sales",   "#F0F0F0", "#444444"),
        "insufficient_history": ("New SKU · Limited History",    "#F0F0F0", "#444444"),
        "manual_override":      ("Manual Override",              "#F0F0F0", "#444444"),
    }
    label, bg, fg = STATUS_DISPLAY.get(row["status"], (row["status"], "#F0F0F0", "#444444"))
    st.markdown(
        f"""<div style="
            background-color: {bg};
            color: {fg};
            padding: 14px 18px;
            border-radius: 8px;
            margin: 8px 0 20px 0;
            font-size: 16px;
            font-weight: 600;
        ">{label}</div>""",
        unsafe_allow_html=True,
    )

    # ---- Two-column layout: Inventory | Sales Forecast ----
    inv_col, fc_col = st.columns(2, gap="medium")

    with inv_col:
        with st.container(border=True):
            st.markdown("##### Available Inventory")
            i1, i2, i3 = st.columns(3)
            i1.metric("Clinic", int(row["on_hand_clinic"]))
            i2.metric("WSA", int(row["on_hand_wsa"]))
            i3.metric("Total", int(row["on_hand_clinic"]) + int(row["on_hand_wsa"]))

    with fc_col:
        with st.container(border=True):
            st.markdown("##### Forecast Metrics")
            f1, f2, f3 = st.columns(3)
            f1.metric("Velocity (units/day)", f"{row['daily_velocity']:.2f}")
            dos = row["days_of_supply"]
            f2.metric("Days of supply", f"{dos:.1f}" if dos is not None else "∞")
            f3.metric("Recommended qty", int(row["recommended_qty"]))

    st.divider()
    st.subheader("Sales history (last 90 days) + forecast projection (next 60 days)")

    series = shopify.daily_sales_for_sku(data["sales"], sku, days_back=90)
    actual_df = pd.DataFrame({"date": series.index, "units": series.values, "kind": "actual"})

    # Project flat at current velocity. The model is a velocity model, not a daily-detail forecast.
    velocity = float(row["daily_velocity"])
    hist_std = float(series.std()) if len(series) > 1 else 0.0
    future_dates = pd.date_range(start=series.index[-1] + pd.Timedelta(days=1), periods=60, freq="D")
    forecast_df = pd.DataFrame(
        {"date": future_dates, "units": velocity, "kind": "forecast"}
    )
    # Confidence band: +/- 1 std of historical daily sales (roughly 68% prediction interval).
    # Lower bound clamped at 0 (no negative sales).
    band_df = pd.DataFrame({
        "date": future_dates,
        "lo": max(0.0, velocity - hist_std),
        "hi": velocity + hist_std,
    })

    combined = pd.concat([actual_df, forecast_df], ignore_index=True)

    nearest = alt.selection_point(nearest=True, on="pointerover", fields=["date"], empty=False)

    base = alt.Chart(combined).encode(x=alt.X("date:T", axis=alt.Axis(title=None)))

    # Confidence band (drawn first so it sits behind everything)
    band = (
        alt.Chart(band_df)
        .mark_area(opacity=0.20, color="#9A9AA0")
        .encode(
            x=alt.X("date:T", axis=alt.Axis(title=None)),
            y=alt.Y("lo:Q", axis=alt.Axis(title="Units")),
            y2="hi:Q",
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%b %d, %Y"),
                alt.Tooltip("lo:Q", title="Low (-1σ)", format=".2f"),
                alt.Tooltip("hi:Q", title="High (+1σ)", format=".2f"),
            ],
        )
    )
    lines = base.mark_line(strokeWidth=2.5).encode(
        y=alt.Y("units:Q", axis=alt.Axis(title="Units")),
        color=alt.Color(
            "kind:N",
            scale=alt.Scale(domain=["actual", "forecast"], range=["#111", "#9A9AA0"]),
            legend=alt.Legend(orient="top-right", title=None),
        ),
    )
    selectors = base.mark_point().encode(opacity=alt.value(0)).add_params(nearest)
    points = lines.mark_point(size=90, filled=True).encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0))
    )
    hover_points = lines.mark_point(size=120, filled=True, opacity=0).encode(
        opacity=alt.condition(nearest, alt.value(0.001), alt.value(0)),
        tooltip=[
            alt.Tooltip("date:T", title="Date", format="%b %d, %Y"),
            alt.Tooltip("units:Q", title="Units", format=".2f"),
            alt.Tooltip("kind:N", title="Series"),
        ],
    )
    text = lines.mark_text(align="left", dx=8, dy=-12, color="#111", fontSize=12, fontWeight=600).encode(
        text=alt.condition(nearest, alt.Text("units:Q", format=".2f"), alt.value(" "))
    )
    rules = base.mark_rule(color="#bbb").encode().transform_filter(nearest)

    chart = alt.layer(band, lines, selectors, points, hover_points, rules, text).properties(height=300)
    st.altair_chart(chart, use_container_width=True)
    st.caption(f"Shaded band = ±1 std of historical daily sales (~68% range). σ = {hist_std:.2f} units/day")

    st.divider()
    with st.expander("Math breakdown", expanded=True):
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
                format_func=lambda s: f"{s} · {name_by_sku.get(s, '')}",
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
            unit_cost = c4.number_input("Unit cost ($) · optional", min_value=0.0, value=0.0, step=0.01)
            notes = st.text_area("Notes (optional)", "")

            submitted = st.form_submit_button("Log purchase", type="primary")
            if submitted:
                if DEMO_MODE:
                    st.info("Demo mode: writes disabled")
                    st.stop()
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

    log = data["purchase_log"] if DEMO_MODE else supabase_io.fetch_purchase_log(_get_supabase_client())
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
    log["vendor"] = log["vendor_id"].map(vmap).fillna("-")
    nmap = recs.set_index("sku")["name"].to_dict()
    log["product"] = log["sku"].map(nmap).fillna("-")

    display_cols = [
        "ordered_at", "sku", "product", "vendor",
        "quantity", "unit_cost", "expected_arrival", "status", "notes",
    ]
    display = log[display_cols].copy()
    display["unit_cost"] = display["unit_cost"].apply(lambda v: f"${v:,.2f}" if pd.notna(v) else "-")
    display["expected_arrival"] = display["expected_arrival"].fillna("-")
    display["notes"] = display["notes"].fillna("-")

    log_event = st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="multi-row",
        key="purchase_log_table",
    )
    st.caption(f"{len(display)} entries shown · check rows to update status")

    selected_rows = log_event.selection.rows if log_event and log_event.selection else []
    if selected_rows:
        # log was filtered same order as display, so iloc on log preserves alignment
        selected_ids = log.iloc[selected_rows]["id"].tolist()
        n = len(selected_ids)

        st.divider()
        st.markdown(f"#### {n} entr{'y' if n == 1 else 'ies'} selected")

        ac = st.columns([1, 1, 1, 3])

        def _bulk_update(new_status: str) -> None:
            if DEMO_MODE:
                st.info("Demo mode: writes disabled")
                st.stop()
            client = _get_supabase_client()
            for row_id in selected_ids:
                supabase_io.update_purchase_log_status(client, int(row_id), new_status)

        if ac[0].button("Mark Shipped", key="po_mark_shipped", use_container_width=True):
            _bulk_update("shipped")
            st.success(f"Marked {n} as shipped")
            st.rerun()
        if ac[1].button("Mark Received", key="po_mark_received", type="primary", use_container_width=True):
            _bulk_update("received")
            st.success(f"Marked {n} as received")
            st.rerun()
        if ac[2].button("Mark Cancelled", key="po_mark_cancelled", use_container_width=True):
            _bulk_update("cancelled")
            st.success(f"Marked {n} as cancelled")
            st.rerun()

    _supabase_edit_link("purchase_log")


def render_vendors(recs: pd.DataFrame, data: dict) -> None:
    st.header("Vendors")

    vendors = data["vendors"]
    if vendors.empty:
        st.info("No vendors yet. Add some under the `vendors` table.")
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
            c1.markdown(f"**Contact:** {v.get('contact_name') or '-'}  \n"
                        f"**Email:** {v.get('contact_email') or '-'}  \n"
                        f"**Phone:** {v.get('contact_phone') or '-'}")
            c2.markdown(f"**Payment terms:** {v.get('payment_terms') or '-'}  \n"
                        f"**Currency:** {v.get('currency') or 'USD'}  \n"
                        f"**Website:** {v.get('website') or '-'}")
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
    # Project URL is like https://abc123.supabase.co · extract the project ref
    ref = project_url.replace("https://", "").split(".")[0]
    edit_url = f"https://supabase.com/dashboard/project/{ref}/editor"
    st.link_button(f"Edit {table} →", edit_url)


def render_all_products(recs: pd.DataFrame, data: dict) -> None:
    st.header("All Products")

    if recs.empty:
        st.info("No products loaded.")
        return

    # ---- Status filter cards (single source of truth: ap_status_multi) ----
    if "ap_status_multi" not in st.session_state:
        st.session_state.ap_status_multi = []

    total_count = len(recs)
    now_count = int((recs["status"] == "reorder_now").sum())
    soon_count = int((recs["status"] == "reorder_soon").sum())
    healthy_count = int((recs["status"] == "healthy").sum())

    card_cols = st.columns(4)
    card_defs = [
        ("all",          "All",          total_count,   []),
        ("reorder_now",  "Reorder Now",  now_count,     ["reorder_now"]),
        ("reorder_soon", "Reorder Soon", soon_count,    ["reorder_soon"]),
        ("healthy",      "Healthy",      healthy_count, ["healthy"]),
    ]
    for col, (key, label, count, new_value) in zip(card_cols, card_defs):
        with col:
            if st.button(
                f"**{label}**\n\n{count}",
                key=f"ap_card_{key}",
                use_container_width=True,
            ):
                st.session_state.ap_status_multi = new_value
                st.rerun()

    # ---- Other filters ----
    c1, c2, c3, c4 = st.columns(4)
    categories = sorted([c for c in recs["category"].dropna().unique()])
    statuses = sorted([s for s in recs["status"].dropna().unique()])

    selected_cat = c1.multiselect("Category", categories, default=[])
    selected_status = c2.multiselect("Status", statuses, key="ap_status_multi")
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

    display_cols = ["image_url", "sku", "name", "category", "status", "on_hand_clinic", "on_hand_wsa", "daily_velocity", "days_of_supply", "moq", "recommended_qty"]
    display_cols = [c for c in display_cols if c in filtered.columns]
    display = filtered[display_cols].copy()
    if "daily_velocity" in display.columns:
        display["daily_velocity"] = display["daily_velocity"].round(2)
    if "days_of_supply" in display.columns:
        display["days_of_supply"] = display["days_of_supply"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "∞")

    # ---- Mode toggle: click-to-detail vs bulk-select for PO ----
    if "ap_bulk_mode" not in st.session_state:
        st.session_state.ap_bulk_mode = False

    tb_left, tb_right = st.columns([6, 2])
    if st.session_state.ap_bulk_mode:
        tb_left.caption(f"Showing {len(display)} of {len(recs)} SKUs · Bulk-select mode: check rows to create a purchase order.")
        if tb_right.button("← Exit bulk select", key="ap_bulk_exit", use_container_width=True):
            st.session_state.ap_bulk_mode = False
            st.rerun()
    else:
        tb_left.caption(f"Showing {len(display)} of {len(recs)} SKUs · Click a row to open its forecast detail.")
        if tb_right.button("Bulk select for PO →", key="ap_bulk_enter", use_container_width=True):
            st.session_state.ap_bulk_mode = True
            st.rerun()

    event = st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="multi-row" if st.session_state.ap_bulk_mode else "single-row",
        column_config={
            "image_url": st.column_config.ImageColumn("Image", width="small"),
        },
    )

    selected_rows = event.selection.rows if event and event.selection else []

    # ---- Default mode: single-row click jumps to Forecast Detail ----
    if not st.session_state.ap_bulk_mode:
        if selected_rows:
            idx = selected_rows[0]
            sku = display.iloc[idx]["sku"]
            st.session_state.fd_selected_sku = sku
            st.session_state.page = "Forecast Detail"
            st.rerun()
        _supabase_edit_link("products")
        return

    # ---- Bulk-select mode: show PO form below table ----
    if selected_rows:
        selected_skus_df = filtered.iloc[selected_rows].copy()
        n = len(selected_skus_df)

        st.divider()
        st.markdown(f"### {n} SKU{'s' if n != 1 else ''} selected")

        with st.expander(f"📋 Create purchase order for these {n} SKU{'s' if n != 1 else ''}", expanded=True):
            with st.form(f"bulk_po_form_{n}"):
                dc1, dc2 = st.columns(2)
                ordered_at = dc1.date_input("Date ordered", value=datetime.now().date(), key="bulk_po_date")
                expected_arrival = dc2.date_input("Expected arrival (optional)", value=None, key="bulk_po_arrival")

                vendors_df = data["vendors"]
                vendor_name_by_id = vendors_df.set_index("id")["name"].to_dict() if not vendors_df.empty else {}
                unique_vendors = selected_skus_df["vendor_id"].dropna().unique().tolist()
                if len(unique_vendors) > 1:
                    st.info(f"Selected SKUs span {len(unique_vendors)} vendors · each line uses its own vendor.")
                elif len(unique_vendors) == 0:
                    st.warning("None of the selected SKUs have a vendor set. The PO will be logged with no vendor attached.")

                st.markdown("**Line items**")
                st.caption("Quantity defaults to recommended qty; unit cost defaults to the value in products.")

                line_items = []
                for _, sku_row in selected_skus_df.iterrows():
                    sku_val = sku_row["sku"]
                    cols = st.columns([3, 2, 1, 1])
                    cols[0].markdown(
                        f"**{sku_val}**  \n<span style='color:#666;font-size:13px;'>{sku_row['name']}</span>",
                        unsafe_allow_html=True,
                    )
                    vid = sku_row.get("vendor_id")
                    vname = vendor_name_by_id.get(vid, "(none)") if pd.notna(vid) else "(none)"
                    cols[1].markdown(
                        f"<span style='color:#666;font-size:13px;'>{vname}</span>",
                        unsafe_allow_html=True,
                    )

                    default_qty = int(sku_row.get("recommended_qty") or 1) or 1
                    qty = cols[2].number_input(
                        "Qty",
                        min_value=1,
                        value=default_qty,
                        key=f"bulk_qty_{sku_val}",
                        label_visibility="collapsed",
                    )
                    default_cost = float(sku_row["unit_cost"]) if pd.notna(sku_row.get("unit_cost")) else 0.0
                    unit_cost = cols[3].number_input(
                        "Cost",
                        min_value=0.0,
                        value=default_cost,
                        step=0.01,
                        key=f"bulk_cost_{sku_val}",
                        label_visibility="collapsed",
                    )
                    line_items.append({
                        "sku": sku_val,
                        "vendor_id": vid if pd.notna(vid) else None,
                        "quantity": qty,
                        "unit_cost": unit_cost,
                    })

                notes = st.text_area("Notes (optional, applied to all rows)", "", key="bulk_po_notes")
                submitted = st.form_submit_button("Log purchase order", type="primary")

                if submitted:
                    if DEMO_MODE:
                        st.info("Demo mode: writes disabled")
                        st.stop()
                    client = _get_supabase_client()
                    inserted = 0
                    errors = []
                    for item in line_items:
                        try:
                            supabase_io.insert_purchase_log(
                                client,
                                ordered_at=ordered_at.isoformat(),
                                sku=item["sku"],
                                vendor_id=item["vendor_id"],
                                quantity=int(item["quantity"]),
                                unit_cost=item["unit_cost"] if item["unit_cost"] > 0 else None,
                                expected_arrival=expected_arrival.isoformat() if expected_arrival else None,
                                notes=notes if notes.strip() else None,
                            )
                            inserted += 1
                        except Exception as e:
                            errors.append(f"{item['sku']}: {e}")
                    if errors:
                        for err in errors:
                            st.error(err)
                    if inserted:
                        st.success(f"Logged {inserted} purchase order line(s) · visible in Purchase Log.")
                        st.rerun()

    _supabase_edit_link("products")


if page == "Overview":
    render_dashboard(recs, data)
elif page == "Reorder Alerts":
    render_reorder_alerts(recs, data)
elif page == "Forecast Detail":
    render_forecast_detail(recs, data)
elif page == "Purchase Log":
    render_purchase_log(recs, data)
elif page == "Vendors":
    render_vendors(recs, data)
elif page == "All Products":
    render_all_products(recs, data)
