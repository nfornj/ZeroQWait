-- Migration: Agent Memory Foundation (tenant-scoped)
-- Date: 2026-04-13

CREATE TABLE IF NOT EXISTS agent_memory (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL,
    user_id INTEGER NULL,
    memory_type VARCHAR(64) NOT NULL DEFAULT 'episodic',
    content TEXT NOT NULL,
    source VARCHAR(128) NULL,
    importance_score FLOAT NOT NULL DEFAULT 0.5,
    memory_meta JSONB NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_accessed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_shop_id ON agent_memory(shop_id);
CREATE INDEX IF NOT EXISTS idx_agent_memory_user_id ON agent_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_memory_type ON agent_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_agent_memory_active ON agent_memory(is_active);
CREATE INDEX IF NOT EXISTS idx_agent_memory_shop_created ON agent_memory(shop_id, created_at DESC);

-- Keeps updated_at fresh on row updates
CREATE OR REPLACE FUNCTION update_agent_memory_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agent_memory_updated_at ON agent_memory;
CREATE TRIGGER trg_agent_memory_updated_at
BEFORE UPDATE ON agent_memory
FOR EACH ROW
EXECUTE FUNCTION update_agent_memory_updated_at();
