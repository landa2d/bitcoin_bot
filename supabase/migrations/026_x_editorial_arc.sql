-- Migration 026: X Editorial Arc — narrative-driven content planning
-- Shifts X distribution from reactive takes to arc-driven storytelling

CREATE TABLE IF NOT EXISTS x_editorial_arc (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz DEFAULT now(),
    pillar text NOT NULL CHECK (pillar IN ('economics', 'trust')),
    arc_title text NOT NULL,
    arc_thesis text NOT NULL,
    week_start date NOT NULL,
    status text NOT NULL DEFAULT 'planned' CHECK (status IN ('active', 'completed', 'planned')),
    post_sequence jsonb DEFAULT '[]'::jsonb,
    overarching_thesis text DEFAULT 'The agent economy is an economic system, not a technology trend. Its success depends on solving trust and cost — not capability.'
);

CREATE INDEX idx_x_editorial_arc_status ON x_editorial_arc (status);
CREATE INDEX idx_x_editorial_arc_week ON x_editorial_arc (week_start DESC);

ALTER TABLE x_editorial_arc ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON x_editorial_arc FOR ALL USING (true) WITH CHECK (true);

-- Add narrative_context field to x_content_candidates for arc linkage
ALTER TABLE x_content_candidates ADD COLUMN IF NOT EXISTS narrative_context text;
-- Add content category: narrative (arc-driven) vs opportunistic (trending + thesis)
ALTER TABLE x_content_candidates ADD COLUMN IF NOT EXISTS content_category text CHECK (content_category IN ('narrative', 'opportunistic'));
