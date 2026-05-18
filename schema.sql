-- Lumati Repurchase System — Supabase schema
-- Run this against any new Supabase project to recreate the database.

create table if not exists vendors (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  contact_name  text,
  contact_email text,
  contact_phone text,
  website       text,
  payment_terms text,
  currency      text default 'USD',
  notes         text,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

create index if not exists vendors_name_idx on vendors (name);

create table if not exists products (
  sku                 text primary key,
  name                text not null,
  category            text,
  vendor_id           uuid references vendors(id) on delete set null,
  unit_cost           numeric(10,2),
  moq                 integer default 1,
  target_cover_days   integer default 60,
  growth_factor       numeric(4,2) default 1.00,
  manual_override     boolean default false,
  active              boolean default true,
  notes               text,
  updated_at          timestamptz default now()
);

create index if not exists products_vendor_id_idx on products (vendor_id);
create index if not exists products_active_idx on products (active);

create table if not exists forecast_log (
  id              bigserial primary key,
  run_at          timestamptz default now(),
  sku             text references products(sku) on delete cascade,
  on_hand         integer,
  daily_velocity  numeric(8,3),
  days_of_supply  numeric(8,1),
  status          text,
  recommended_qty integer
);

create index if not exists forecast_log_sku_run_at_idx on forecast_log (sku, run_at desc);

create table if not exists settings (
  id                          integer primary key default 1,
  reorder_now_days            integer default 30,
  reorder_soon_days           integer default 45,
  slow_mover_threshold        numeric(4,2) default 0.10,
  dead_mover_days             integer default 60,
  insufficient_history_days   integer default 14,
  forecast_window_days        integer default 90,
  shopify_order_days          integer default 365,
  constraint single_row check (id = 1)
);

insert into settings (id) values (1)
on conflict (id) do nothing;
