-- Migration: Add entry timing, visual tiers, and sizing helper columns to recommendations
-- Prompt 3 of 3: System Accuracy & Precision Upgrade

ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS entry_type TEXT DEFAULT 'immediate';
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS ideal_entry_price DOUBLE PRECISION;
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS entry_note TEXT;
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS trade_tier TEXT DEFAULT 'B';
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS position_size_pct INT DEFAULT 50;
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS confirming_signals JSONB DEFAULT '[]';
