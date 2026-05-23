-- Migration 005: Create user watchlists and user portfolios tables
create table if not exists user_watchlists (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  symbol text not null references stocks(symbol) on delete cascade,
  created_at timestamptz default now(),
  unique (user_id, symbol)
);

create table if not exists user_portfolios (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  symbol text not null references stocks(symbol) on delete cascade,
  shares_quantity numeric not null check (shares_quantity > 0),
  buy_price numeric not null check (buy_price >= 0),
  created_at timestamptz default now(),
  unique (user_id, symbol)
);

alter table user_watchlists enable row level security;
alter table user_portfolios enable row level security;

create policy "users read own watchlists" on user_watchlists for select using (true);
create policy "users write own watchlists" on user_watchlists for all using (true) with check (true);

create policy "users read own portfolios" on user_portfolios for select using (true);
create policy "users write own portfolios" on user_portfolios for all using (true) with check (true);
