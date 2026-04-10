-- 028: Allow web visitors to read newsletters in 'preview' or 'published' status.
-- The 'preview' status lets operators review on the web before distribution.

DROP POLICY IF EXISTS "Public read published newsletters" ON newsletters;
DROP POLICY IF EXISTS newsletters_anon_read ON newsletters;

CREATE POLICY newsletters_anon_read ON newsletters
    FOR SELECT TO anon
    USING (status IN ('published', 'preview'));
