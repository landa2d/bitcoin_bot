ALTER TABLE newsletter_prepass_tracking
    ADD COLUMN headline_justification text,
    ADD COLUMN stale_cluster_flag boolean DEFAULT false;

COMMENT ON COLUMN newsletter_prepass_tracking.headline_justification IS 'Prepass explanation for why no headline was chosen over cluster (when cluster-based)';
COMMENT ON COLUMN newsletter_prepass_tracking.stale_cluster_flag IS 'True if the chosen cluster-sourced angle has avg_recency_days > 14';
