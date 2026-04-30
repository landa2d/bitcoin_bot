CREATE TABLE newsletter_prepass_tracking (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_number integer NOT NULL,
    chosen_angle text NOT NULL,
    primary_entity text,
    angle_source text CHECK (angle_source IN ('headline', 'cluster', 'mixed', 'unknown')),
    created_at timestamptz DEFAULT now()
);

COMMENT ON TABLE newsletter_prepass_tracking IS 'Fix 3a monitoring: tracks editorial prepass angles for entity skew and headline-vs-cluster source analysis';
COMMENT ON COLUMN newsletter_prepass_tracking.primary_entity IS 'Primary named entity in chosen angle (e.g. Anthropic, OpenAI, Google, Amazon), or null if none';
COMMENT ON COLUMN newsletter_prepass_tracking.angle_source IS 'Whether angle came from a headline, cluster theme, or mixed';
