-- Migration 012: Add sentiment_gate to recommendations and trading_signals, and target_price, stop_loss, source_alert_id to admin_trades
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS sentiment_gate TEXT DEFAULT 'passed';
ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS sentiment_gate TEXT DEFAULT 'passed';

ALTER TABLE admin_trades ADD COLUMN IF NOT EXISTS target_price NUMERIC;
ALTER TABLE admin_trades ADD COLUMN IF NOT EXISTS stop_loss NUMERIC;
ALTER TABLE admin_trades ADD COLUMN IF NOT EXISTS source_alert_id UUID;
