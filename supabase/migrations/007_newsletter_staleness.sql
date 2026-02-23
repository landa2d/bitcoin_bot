-- Migration 007: Newsletter staleness tracking fields on opportunities table
-- Adds three columns to track how many times an opportunity has been featured
-- in the newsletter and when, enabling the staleness decay in prepare_newsletter_data().

DO $$
BEGIN
    -- newsletter_appearances: how many times this opportunity has been in the newsletter
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'opportunities' AND column_name = 'newsletter_appearances'
    ) THEN
        ALTER TABLE opportunities ADD COLUMN newsletter_appearances INTEGER DEFAULT 0;
    END IF;

    -- last_featured_at: when the opportunity was most recently featured
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'opportunities' AND column_name = 'last_featured_at'
    ) THEN
        ALTER TABLE opportunities ADD COLUMN last_featured_at TIMESTAMPTZ;
    END IF;

    -- first_featured_at: when the opportunity was first featured
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'opportunities' AND column_name = 'first_featured_at'
    ) THEN
        ALTER TABLE opportunities ADD COLUMN first_featured_at TIMESTAMPTZ;
    END IF;

    -- last_reviewed_at: when the Analyst last reviewed this opportunity
    -- (used for the "reviewed since last featured" bonus in staleness calc)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'opportunities' AND column_name = 'last_reviewed_at'
    ) THEN
        ALTER TABLE opportunities ADD COLUMN last_reviewed_at TIMESTAMPTZ;
    END IF;

    -- review_count: how many analyst review cycles this opportunity has been through
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'opportunities' AND column_name = 'review_count'
    ) THEN
        ALTER TABLE opportunities ADD COLUMN review_count INTEGER DEFAULT 0;
    END IF;

    -- analyst_reasoning: reasoning chain from the Analyst's last review
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'opportunities' AND column_name = 'analyst_reasoning'
    ) THEN
        ALTER TABLE opportunities ADD COLUMN analyst_reasoning TEXT;
    END IF;

    -- analyst_confidence_notes: downgrade factors etc. from analyst
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'opportunities' AND column_name = 'analyst_confidence_notes'
    ) THEN
        ALTER TABLE opportunities ADD COLUMN analyst_confidence_notes TEXT;
    END IF;

    -- signal_sources: which pipelines contributed signal for this opportunity
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'opportunities' AND column_name = 'signal_sources'
    ) THEN
        ALTER TABLE opportunities ADD COLUMN signal_sources JSONB;
    END IF;
END $$;

-- Index to support prepare_newsletter_data staleness sort
CREATE INDEX IF NOT EXISTS idx_opportunities_appearances
    ON opportunities(newsletter_appearances ASC, confidence_score DESC);

CREATE INDEX IF NOT EXISTS idx_opportunities_last_featured
    ON opportunities(last_featured_at DESC NULLS FIRST);
