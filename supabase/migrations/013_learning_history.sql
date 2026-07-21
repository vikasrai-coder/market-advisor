-- Learning History: Logs every self-learning brain run for trend visualization
-- Tracks win rate, threshold, suppressed sectors/modes over time

CREATE TABLE IF NOT EXISTS learning_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  overall_win_rate numeric,
  sample_size int,
  min_composite_override int,
  suppressed_sectors jsonb DEFAULT '[]',
  suppressed_modes jsonb DEFAULT '[]',
  sector_win_rates jsonb DEFAULT '{}',
  mode_win_rates jsonb DEFAULT '{}',
  systemic_warning text,
  generated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learning_history_time ON learning_history(generated_at DESC);

ALTER TABLE learning_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read learning_history" ON learning_history FOR SELECT USING (true);
CREATE POLICY "service write learning_history" ON learning_history FOR ALL USING (true) WITH CHECK (true);
