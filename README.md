# Lumati Repurchase System

Streamlit dashboard that surfaces reorder alerts for the lumati.life Shopify store.

## Setup

1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in real values
4. Apply schema: paste `schema.sql` into Supabase SQL editor and run
5. Seed products: `python seed_products.py`
6. Run: `streamlit run app.py`

## Structure

- `app.py` · Streamlit entry point and page routing
- `lib/shopify.py` · Shopify Admin API client
- `lib/supabase_io.py` · Supabase reads/writes
- `lib/forecast.py` · Weighted rolling average velocity model
- `lib/reorder.py` · Status logic and recommended quantity
- `lib/email_draft.py` · PO email body template
- `schema.sql` · Supabase Postgres schema
- `seed_products.py` · One-time SKU seeding from Shopify
- `tests/` · Unit tests for forecast and reorder
