-- Migration 022: Subscribe RPC function
-- SECURITY DEFINER bypasses RLS so anon can upsert subscribers
-- (PostgreSQL requires SELECT permission for ON CONFLICT, which anon doesn't have)

CREATE OR REPLACE FUNCTION subscribe(p_email TEXT, p_mode TEXT)
RETURNS void AS $$
BEGIN
    INSERT INTO subscribers (email, mode_preference, status)
    VALUES (p_email, p_mode, 'active')
    ON CONFLICT (email) DO UPDATE SET
        mode_preference = p_mode,
        status = 'active',
        unsubscribed_at = NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION subscribe(TEXT, TEXT) TO anon;
