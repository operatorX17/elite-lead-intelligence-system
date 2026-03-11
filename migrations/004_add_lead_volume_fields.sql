-- Migration 004: Add volume signal fields to leads table
-- Date: 2026-02-22
-- Purpose: Store reviews_count and rating directly in leads table for volume scoring

-- Add reviews_count column
ALTER TABLE leads
ADD COLUMN IF NOT EXISTS reviews_count INTEGER;

-- Add rating column
ALTER TABLE leads
ADD COLUMN IF NOT EXISTS rating NUMERIC(3, 2);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_leads_reviews_count ON leads(reviews_count);
CREATE INDEX IF NOT EXISTS idx_leads_rating ON leads(rating);

-- Add comment
COMMENT ON COLUMN leads.reviews_count IS 'Number of Google Maps reviews (volume indicator)';
COMMENT ON COLUMN leads.rating IS 'Google Maps rating (1.0-5.0)';
