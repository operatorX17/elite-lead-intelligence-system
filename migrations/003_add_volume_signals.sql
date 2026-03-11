-- Migration 003: Add Google Maps Volume Signals
-- Adds comprehensive volume and engagement signals from Google Maps

-- Add volume signals to enrichment_data table
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS popular_times_histogram JSONB;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS popular_times_live_text TEXT;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS people_typically_spend_here TEXT;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS peak_busyness INTEGER;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS avg_busyness INTEGER;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS busy_hours_count INTEGER;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS avg_visit_duration_min INTEGER;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS is_peak_busy BOOLEAN DEFAULT FALSE;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS is_above_average BOOLEAN DEFAULT FALSE;

-- Add additional Google Maps signals
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS opening_hours JSONB;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS reviews_distribution JSONB;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS questions_and_answers JSONB;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS web_results JSONB;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS table_reservation_links JSONB;
ALTER TABLE enrichment_data ADD COLUMN IF NOT EXISTS image_categories JSONB;

-- Add volume score to intent_data table
ALTER TABLE intent_data ADD COLUMN IF NOT EXISTS volume_score INTEGER DEFAULT 0;

-- Create index for volume queries
CREATE INDEX IF NOT EXISTS idx_enrichment_peak_busyness ON enrichment_data(peak_busyness);
CREATE INDEX IF NOT EXISTS idx_enrichment_busy_hours ON enrichment_data(busy_hours_count);
CREATE INDEX IF NOT EXISTS idx_intent_volume_score ON intent_data(volume_score);

-- Add comments
COMMENT ON COLUMN enrichment_data.popular_times_histogram IS 'Google Maps popular times data (hourly traffic by day)';
COMMENT ON COLUMN enrichment_data.peak_busyness IS 'Peak busyness level 0-100';
COMMENT ON COLUMN enrichment_data.avg_busyness IS 'Average busyness level 0-100';
COMMENT ON COLUMN enrichment_data.busy_hours_count IS 'Number of hours per week with >70% busyness';
COMMENT ON COLUMN enrichment_data.avg_visit_duration_min IS 'Average visit duration in minutes';
COMMENT ON COLUMN intent_data.volume_score IS 'Volume score 0-100 based on Google Maps signals';
