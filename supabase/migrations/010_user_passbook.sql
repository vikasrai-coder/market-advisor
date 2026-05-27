-- Migration 010: Create user passbook and add target/stop-loss columns to portfolios
alter table user_portfolios add column if not exists target_price numeric;
alter table user_portfolios add column if not exists stop_loss numeric;

create table if not exists user_passbook (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  symbol text not null,
  shares_quantity numeric not null check (shares_quantity > 0),
  buy_price numeric not null check (buy_price >= 0),
  sell_price numeric not null check (sell_price >= 0),
  profit_loss numeric not null,
  profit_loss_pct numeric not null,
  execution_type text not null, -- 'manual', 'target_trigger', 'stop_loss_trigger'
  created_at timestamptz default now()
);

alter table user_passbook enable row level security;
create policy "users read own passbook" on user_passbook for select using (true);
create policy "users write own passbook" on user_passbook for all using (true) with check (true);
