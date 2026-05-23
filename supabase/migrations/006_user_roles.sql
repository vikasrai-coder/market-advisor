-- Migration 006: Create user roles and admin trade tracking tables
create table if not exists user_roles (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  email text not null,
  role text not null default 'user' check (role in ('admin', 'user')),
  permissions jsonb not null default '{"can_view_charts": true, "can_view_recommendations": true, "can_view_heatmap": true, "can_view_signals": true, "can_backtest": true, "can_use_portfolio": true}',
  created_at timestamptz default now(),
  unique (user_id)
);

create table if not exists admin_trades (
  id uuid primary key default gen_random_uuid(),
  symbol text not null references stocks(symbol) on delete cascade,
  shares_quantity numeric not null check (shares_quantity > 0),
  buy_price numeric not null check (buy_price >= 0),
  sell_price numeric,
  trade_status text not null default 'open' check (trade_status in ('open', 'closed')),
  profit_loss numeric,
  created_at timestamptz default now()
);

alter table user_roles enable row level security;
alter table admin_trades enable row level security;

create policy "public read user roles" on user_roles for select using (true);
create policy "service write user roles" on user_roles for all using (true) with check (true);

create policy "public read admin trades" on admin_trades for select using (true);
create policy "service write admin trades" on admin_trades for all using (true) with check (true);
