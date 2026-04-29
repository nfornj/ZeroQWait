-- Migration 003: pgvector extension + semantic search support
-- Adds vector(384) embedding column to conversation_history so the
-- SearchCustomerContext agent tool can perform cosine-similarity lookup.
--
-- Run once against the target database:
--   psql $DATABASE_URL -f backend/sql/003_pgvector.sql

-- Enable pgvector extension (requires postgresql-pgvector package on host)
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to conversation_history (384 dims = all-MiniLM-L6-v2)
ALTER TABLE conversation_history
    ADD COLUMN IF NOT EXISTS embedding vector(384);

-- IVFFlat cosine index for efficient approximate nearest-neighbour search.
-- Build after the column is populated; harmless if table is empty.
CREATE INDEX IF NOT EXISTS ix_conv_history_embedding
    ON conversation_history
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Allow the FastAPI app user to update the column (grant if using restricted roles).
-- Adjust role name to match your PostgreSQL user.
-- GRANT UPDATE (embedding) ON conversation_history TO fastcuts_user;
