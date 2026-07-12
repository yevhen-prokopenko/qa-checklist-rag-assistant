-- Runs once against the pgvector container to create schema.
CREATE EXTENSION IF NOT EXISTS vector;

-- Knowledge base of past, verified checklists (RAG store).
CREATE TABLE IF NOT EXISTS knowledge (
    id            BIGSERIAL PRIMARY KEY,
    source_key    TEXT,                 -- Jira issue key this came from (e.g. QA-1234)
    domain        TEXT,                 -- e.g. 'wms-transfer', 'web-checkout'
    content       TEXT NOT NULL,        -- the checklist chunk text
    approved      BOOLEAN DEFAULT TRUE, -- quality gate: only approved entries feed retrieval
    embedding     VECTOR(1536),         -- keep dim in sync with config.EMBED_DIM
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- Cosine similarity index (ivfflat). Tune lists as corpus grows.
CREATE INDEX IF NOT EXISTS knowledge_embedding_idx
    ON knowledge USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
