"""One-time: pull active product variants from Shopify and insert into products table.

Run with the venv active:
    python seed_products.py

Idempotent — re-running won't duplicate or overwrite existing rows.
"""

from dotenv import load_dotenv

load_dotenv()

from lib.shopify import fetch_products  # noqa: E402
from lib.supabase_io import get_client, insert_product  # noqa: E402


def _category_from_name(name: str) -> str | None:
    n = name.lower()
    if "hydrogen" in n and ("bottle" in n or "inhal" in n or "immer" in n):
        return "Hydrogen Equipment"
    if "led" in n or "pbm" in n or "light" in n:
        return "Light Equipment"
    if "test" in n or "detect" in n:
        return "Detect Test"
    if any(w in n for w in ["red", "green", "gold", "stack", "supplement", "curcumin", "nootropic"]):
        return "Supplement"
    return None


def main() -> None:
    client = get_client()
    df = fetch_products()
    print(f"Fetched {len(df)} variants from Shopify.")

    inserted = 0
    for _, row in df.iterrows():
        sku = row["sku"]
        product_name = row["product_name"]
        variant_title = row.get("variant_title", "")
        display_name = product_name if not variant_title or variant_title == "Default Title" else f"{product_name} ({variant_title})"
        category = _category_from_name(display_name)

        insert_product(client, sku=sku, name=display_name, category=category)
        inserted += 1

    print(f"Upserted {inserted} products into Supabase (existing rows unchanged).")


if __name__ == "__main__":
    main()
