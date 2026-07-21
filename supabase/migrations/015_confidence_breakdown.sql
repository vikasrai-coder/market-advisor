-- Confidence Breakdown: Structured score explanation per recommendation
-- Stores breakdown of why a recommendation scored the way it did

ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS confidence_breakdown jsonb;

COMMENT ON COLUMN recommendations.confidence_breakdown IS 'Structured breakdown: trend_alignment, volume_confirmation, risk_reward_ratio, sector_momentum, brain_approval';
