-- Migration 019: Email delivery log + subscriber upsert support
--
-- 1. email_log table — tracks every email sent (welcome + newsletter)
-- 2. Upsert-friendly conflict handling so re-subscribing updates mode_preference

-- ─── Email log table ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id UUID REFERENCES subscribers(id) ON DELETE SET NULL,
    email TEXT NOT NULL,
    email_type TEXT NOT NULL,          -- 'welcome', 'newsletter'
    subject TEXT,
    mode TEXT,                         -- 'builder', 'impact', or NULL for welcome
    edition_number INT,                -- NULL for welcome emails
    resend_id TEXT,                    -- Resend API response ID for cross-ref
    status TEXT DEFAULT 'sent',        -- 'sent', 'failed'
    error_message TEXT,                -- populated on failure
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_email_log_subscriber ON email_log(subscriber_id);
CREATE INDEX idx_email_log_type ON email_log(email_type);
CREATE INDEX idx_email_log_created ON email_log(created_at DESC);

ALTER TABLE email_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access to email_log" ON email_log
    FOR ALL USING (auth.role() = 'service_role');

-- ─── Subscriber upsert support ──────────────────────────────────────────────
-- Allow the anon INSERT policy to handle ON CONFLICT by also allowing UPDATE
-- on re-subscribe (changes mode_preference, reactivates if unsubscribed)
DROP POLICY IF EXISTS "Allow public subscribe" ON subscribers;
CREATE POLICY "Allow public subscribe" ON subscribers
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public resubscribe update" ON subscribers
    FOR UPDATE USING (true) WITH CHECK (true);
