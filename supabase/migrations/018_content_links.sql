-- Migration 018: Content Links — graph edges between corpus items
-- Used by corpus_probe.py for one-hop graph expansion during retrieval

CREATE TABLE IF NOT EXISTS content_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table TEXT NOT NULL,
    source_id UUID NOT NULL,
    target_table TEXT NOT NULL,
    target_id UUID NOT NULL,
    link_type TEXT NOT NULL,          -- predicts, confirms, refutes, updates, derived_from, supports
    confidence FLOAT DEFAULT 1.0,     -- link strength (0-1)
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source_table, source_id, target_table, target_id, link_type)
);

CREATE INDEX IF NOT EXISTS idx_content_links_source
    ON content_links(source_table, source_id);
CREATE INDEX IF NOT EXISTS idx_content_links_target
    ON content_links(target_table, target_id);
CREATE INDEX IF NOT EXISTS idx_content_links_type
    ON content_links(link_type);
