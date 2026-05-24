-- Migration to support storing Quantitative Backtest Simulation results

create table backtest_runs (
  id uuid default gen_random_uuid() primary key,
  mode text not null,
  start_date date not null,
  check_days integer not null,
  win_rate numeric not null,
  avg_return numeric not null,
  total_picks integer not null,
  target_hits integer not null,
  stop_hits integer not null,
  held integer not null,
  index_return numeric not null,
  outperformance numeric not null,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

create table backtest_results (
  id uuid default gen_random_uuid() primary key,
  run_id uuid references backtest_runs(id) on delete cascade not null,
  rank integer not null,
  symbol text not null,
  name text,
  sector text,
  is_undervalued boolean not null default false,
  composite_score numeric not null,
  rsi numeric,
  macd numeric,
  entry_price numeric not null,
  target_price numeric not null,
  stop_loss numeric not null,
  exit_price numeric not null,
  exit_date date,
  return_pct numeric not null,
  outcome text not null,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Enable Row Level Security (RLS)
alter table backtest_runs enable row level security;
alter table backtest_results enable row level security;

-- Create policy to allow all operations for easy access
create policy "Allow all operations for backtest_runs" on backtest_runs for all using (true) with check (true);
create policy "Allow all operations for backtest_results" on backtest_results for all using (true) with check (true);
