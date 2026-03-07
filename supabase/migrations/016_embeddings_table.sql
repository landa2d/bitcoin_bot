-- Embeddings table for pgvector semantic search
-- NOTE: pgvector extension (vector) already installed in public schema
-- NOTE: Table was created via Supabase dashboard/migration; this file captures the schema.

CREATE TABLE IF NOT EXISTS embeddings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table text NOT NULL,
    source_id uuid NOT NULL,
    chunk_index integer NOT NULL DEFAULT 0,
    content_text text NOT NULL,
    embedding vector(1536) NOT NULL,
    metadata jsonb DEFAULT '{}',
    edition_date date,
    edition_number integer,
    created_at timestamptz DEFAULT now(),
    CONSTRAINT uq_embeddings_source_chunk UNIQUE (source_table, source_id, chunk_index)
);

-- HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw ON embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_embeddings_source ON embeddings (source_table, source_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_edition ON embeddings (edition_number);

-- RLS
ALTER TABLE embeddings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on embeddings"
    ON embeddings FOR ALL
    USING (auth.role() = 'service_role');
