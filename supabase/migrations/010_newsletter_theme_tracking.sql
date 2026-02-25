-- Migration 010: Add primary_theme tracking for editorial diversity
-- Prevents consecutive newsletters from covering the same macro-theme.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'newsletters' AND column_name = 'primary_theme'
    ) THEN
        ALTER TABLE newsletters ADD COLUMN primary_theme TEXT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_newsletters_theme
    ON newsletters(primary_theme)
    WHERE primary_theme IS NOT NULL;
