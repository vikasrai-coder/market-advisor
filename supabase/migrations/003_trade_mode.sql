-- Add trade_mode to recommendations and trading_signals tables to support multiple trading modes
alter table recommendations add column if not exists trade_mode text default 'swing';
alter table trading_signals add column if not exists trade_mode text default 'swing';
