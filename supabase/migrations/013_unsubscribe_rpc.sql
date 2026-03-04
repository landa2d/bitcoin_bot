-- Migration 013: Unsubscribe RPC function
-- Called from the SPA via anon key. The subscriber UUID in the unsubscribe
-- link acts as a bearer token — only someone with the link can unsubscribe.

CREATE OR REPLACE FUNCTION unsubscribe(subscriber_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE subscribers
    SET status = 'unsubscribed',
        unsubscribed_at = NOW()
    WHERE id = subscriber_id
      AND status = 'active';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION unsubscribe(UUID) TO anon;
