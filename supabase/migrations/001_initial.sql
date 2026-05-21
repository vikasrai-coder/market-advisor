-- Market Advisor: stocks, news, metrics, recommendations, signals

create table if not exists stocks (
  symbol text primary key,
  name text,
  sector text,
  industry text,
  market_cap bigint,
  pe_ratio numeric,
  dividend_yield numeric,
  beta numeric,
  fifty_two_week_high numeric,
  fifty_two_week_low numeric,
  updated_at timestamptz default now()
);

create table if not exists news_articles (
  id uuid primary key default gen_random_uuid(),
  symbol text references stocks(symbol) on delete cascade,
  title text not null,
  summary text,
  url text,
  source text,
  sentiment_label text,
  sentiment_score numeric,
  published_at timestamptz,
  fetched_at timestamptz default now()
);

create index if not exists idx_news_symbol on news_articles(symbol);
create index if not exists idx_news_published on news_articles(published_at desc);

create table if not exists stock_metrics (
  id uuid primary key default gen_random_uuid(),
  symbol text references stocks(symbol) on delete cascade,
  price numeric,
  change_pct numeric,
  volume bigint,
  rsi numeric,
  macd numeric,
  macd_signal numeric,
  sma_20 numeric,
  sma_50 numeric,
  trend_score numeric,
  volatility numeric,
  recorded_at timestamptz default now()
);

create index if not exists idx_metrics_symbol_time on stock_metrics(symbol, recorded_at desc);

create table if not exists analysis_runs (
  id uuid primary key default gen_random_uuid(),
  status text not null default 'running',
  stocks_analyzed int default 0,
  recommendations_count int default 0,
  error_message text,
  started_at timestamptz default now(),
  completed_at timestamptz
);

create table if not exists recommendations (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references analysis_runs(id) on delete set null,
  symbol text references stocks(symbol) on delete cascade,
  rank int not null check (rank between 1 and 10),
  action text not null default 'buy',
  composite_score numeric not null,
  trend_score numeric,
  news_score numeric,
  technical_score numeric,
  ai_confidence numeric,
  reasoning text,
  key_factors jsonb,
  signal_date date not null,
  trade_date date not null,
  created_at timestamptz default now(),
  unique (signal_date, rank, action)
);

create index if not exists idx_recommendations_trade on recommendations(trade_date desc);

create table if not exists trading_signals (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references analysis_runs(id) on delete set null,
  symbol text references stocks(symbol) on delete cascade,
  signal_type text not null check (signal_type in ('buy', 'sell', 'hold')),
  strength text check (strength in ('weak', 'moderate', 'strong')),
  price_at_signal numeric,
  target_price numeric,
  stop_loss numeric,
  rationale text,
  signal_date date not null,
  planned_trade_date date not null,
  created_at timestamptz default now()
);

create index if not exists idx_signals_planned on trading_signals(planned_trade_date, signal_type);

alter table stocks enable row level security;
alter table news_articles enable row level security;
alter table stock_metrics enable row level security;
alter table analysis_runs enable row level security;
alter table recommendations enable row level security;
alter table trading_signals enable row level security;

create policy "public read stocks" on stocks for select using (true);
create policy "public read news" on news_articles for select using (true);
create policy "public read metrics" on stock_metrics for select using (true);
create policy "public read runs" on analysis_runs for select using (true);
create policy "public read recommendations" on recommendations for select using (true);
create policy "public read signals" on trading_signals for select using (true);

create policy "service write stocks" on stocks for all using (true) with check (true);
create policy "service write news" on news_articles for all using (true) with check (true);
create policy "service write metrics" on stock_metrics for all using (true) with check (true);
create policy "service write runs" on analysis_runs for all using (true) with check (true);
create policy "service write recommendations" on recommendations for all using (true) with check (true);
create policy "service write signals" on trading_signals for all using (true) with check (true);
