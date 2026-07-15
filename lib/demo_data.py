"""Fictional Aura Wellness demo dataset for DEMO_MODE captures.

Deterministic (seeded): the same data renders on every run so portfolio
screenshots are repeatable. No real Lumati data appears anywhere.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from lib.reorder import Settings

_SEED = 7
_DAYS = 365
_CATEGORIES = {
    "Accessories": 60, "Devices": 25, "Supplements": 80, "Test Kits": 35,
}
_VENDORS = ["Halcyon Labs", "Meridian Supply Co.", "NordWell Distribution",
            "Pacifica Botanicals"]


def _products(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    n = 1
    for cat, count in _CATEGORIES.items():
        prefix = cat[:3].upper()
        for i in range(count):
            unit_cost = float(np.round(rng.uniform(4, 220), 2))
            rows.append({
                "sku": f"AW-{prefix}-{n:03d}",
                "name": f"{cat[:-1] if cat.endswith('s') else cat} {i + 1:02d}",
                "category": cat,
                "vendor_id": int(rng.integers(1, len(_VENDORS) + 1)),
                "unit_cost": unit_cost,
                "moq": int(rng.choice([10, 25, 50, 100])),
                "target_cover_days": 45,
                "growth_factor": 1.0,
                "manual_override": None,
                "active": True,
                "notes": None,
            })
            n += 1
    return pd.DataFrame(rows)


def _vendors() -> pd.DataFrame:
    return pd.DataFrame([
        {"id": i + 1, "name": v, "contact_name": None,
         "contact_email": f"orders@{v.split()[0].lower()}.example.com",
         "contact_phone": None, "website": None,
         "payment_terms": "Net 30", "currency": "USD", "notes": None}
        for i, v in enumerate(_VENDORS)
    ])


def _sales(products: pd.DataFrame, rng: np.random.Generator,
           today: pd.Timestamp) -> pd.DataFrame:
    dates = pd.date_range(end=today, periods=_DAYS, freq="D")
    rows = []
    for _, p in products.iterrows():
        base = rng.uniform(0.2, 6.0)          # avg daily units per SKU
        trend = rng.uniform(0.9, 1.35)        # gentle growth or decline
        price = p["unit_cost"] * rng.uniform(2.2, 3.2)
        weights = np.linspace(1, trend, _DAYS)
        active_days = rng.random(_DAYS) < min(base / 3.0, 0.95)
        for d, w, on in zip(dates, weights, active_days):
            if not on:
                continue
            units = int(rng.poisson(base * w)) or 1
            gross = round(units * price, 2)
            rows.append({
                "sku": p["sku"], "date": d, "units": units,
                "revenue": gross, "net_revenue": round(gross * 0.94, 2),
                "source": "shopify" if rng.random() < 0.8 else "square",
            })
    df = pd.DataFrame(rows)
    return (df.groupby(["sku", "date", "source"], as_index=False)
              [["units", "revenue", "net_revenue"]].sum())


def _shop_products(products: pd.DataFrame,
                   rng: np.random.Generator) -> pd.DataFrame:
    on_hand = rng.integers(0, 400, len(products))
    split = rng.random(len(products))
    clinic = (on_hand * split).astype(int)
    return pd.DataFrame({
        "sku": products["sku"],
        "variant_id": np.arange(1_000_001, 1_000_001 + len(products)),
        "product_id": np.arange(2_000_001, 2_000_001 + len(products)),
        "product_name": products["name"],
        "variant_title": "Default",
        "inventory_item_id": np.arange(3_000_001, 3_000_001 + len(products)),
        "on_hand_clinic": clinic,
        "on_hand_wsa": on_hand - clinic,
        "on_hand": on_hand,
        "image_url": "",
    })


def _purchase_log(products: pd.DataFrame, rng: np.random.Generator,
                  today: pd.Timestamp) -> pd.DataFrame:
    picks = products.sample(25, random_state=_SEED)
    rows = []
    for i, (_, p) in enumerate(picks.iterrows()):
        ordered = today - timedelta(days=int(rng.integers(5, 120)))
        rows.append({
            "id": i + 1,
            "ordered_at": ordered.isoformat(),
            "sku": p["sku"], "vendor_id": p["vendor_id"],
            "quantity": int(rng.choice([25, 50, 100, 200])),
            "unit_cost": p["unit_cost"],
            "expected_arrival": (ordered + timedelta(days=21)).date().isoformat(),
            "status": str(rng.choice(["placed", "received", "received"])),
            "notes": None,
            "created_at": ordered.isoformat(),
        })
    return pd.DataFrame(rows)


def load_all_data_demo() -> dict:
    rng = np.random.default_rng(_SEED)
    today = pd.Timestamp.now().normalize()
    products = _products(rng)
    sales = _sales(products, rng, today)
    adjustments = (sales.groupby(["date", "source"], as_index=False)
                        .agg(discounts=("revenue", lambda s: round(s.sum() * 0.03, 2)),
                             refunds=("revenue", lambda s: round(s.sum() * 0.02, 2))))
    return {
        "products": products,
        "vendors": _vendors(),
        "settings": Settings(),
        "purchase_log": _purchase_log(products, rng, today),
        "shop_products": _shop_products(products, rng),
        "sales": sales,
        "adjustments": adjustments,
        "loaded_at": datetime.now(),
    }
