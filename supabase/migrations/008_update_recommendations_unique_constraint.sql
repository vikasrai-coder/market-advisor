-- Migration 008: Update unique constraint on recommendations table to include trade_mode.
-- This allows different trading modes (e.g., intraday, swing, longterm) to store recommendations
-- for the same date simultaneously.

-- Drop the old unique constraint
ALTER TABLE recommendations DROP CONSTRAINT IF EXISTS recommendations_signal_date_rank_action_key;

-- Add the new unique constraint that includes trade_mode
ALTER TABLE recommendations ADD CONSTRAINT recommendations_signal_date_rank_action_trade_mode_key UNIQUE (signal_date, rank, action, trade_mode);
