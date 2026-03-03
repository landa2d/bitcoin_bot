-- Migration 011: Add dual-audience columns for Impact Mode
-- Part of Phase 6: Builder/Impact toggle on web archive

-- Impact version of newsletter content
ALTER TABLE newsletters ADD COLUMN IF NOT EXISTS title_impact TEXT;
ALTER TABLE newsletters ADD COLUMN IF NOT EXISTS content_markdown_impact TEXT;

-- Subscribers table for email subscriptions with mode preference
CREATE TABLE IF NOT EXISTS subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    mode_preference TEXT DEFAULT 'impact',      -- 'builder', 'impact', 'both'
    status TEXT DEFAULT 'pending',              -- 'pending', 'active', 'unsubscribed'
    confirmation_token TEXT,
    confirmed_at TIMESTAMPTZ,
    unsubscribed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- Allow anonymous inserts for the subscribe form (anon key + RLS)
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public subscribe" ON subscribers FOR INSERT WITH CHECK (true);
-- Only service_role can read/update/delete subscribers
CREATE POLICY "Service role full access to subscribers" ON subscribers
    FOR ALL USING (auth.role() = 'service_role');
