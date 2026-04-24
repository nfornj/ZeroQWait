-- Migration: Shop-scoped LLM configuration
-- Date: 2026-04-24

CREATE TABLE IF NOT EXISTS shop_llm_configs (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL DEFAULT 'ollama',
    model_name VARCHAR(255) NOT NULL,
    api_base_url VARCHAR(512) NULL,
    api_key_encrypted TEXT NULL,
    settings JSONB NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_shop_llm_configs_shop UNIQUE (shop_id)
);

CREATE INDEX IF NOT EXISTS idx_shop_llm_configs_shop_id ON shop_llm_configs(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_llm_configs_provider ON shop_llm_configs(provider);

CREATE OR REPLACE FUNCTION update_shop_llm_configs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_shop_llm_configs_updated_at ON shop_llm_configs;
CREATE TRIGGER trg_shop_llm_configs_updated_at
BEFORE UPDATE ON shop_llm_configs
FOR EACH ROW
EXECUTE FUNCTION update_shop_llm_configs_updated_at();