-- Migration: Agent Brain Foundation
-- Date: 2026-04-30

CREATE TABLE IF NOT EXISTS shop_soul (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    tone VARCHAR NULL,
    upsell_style VARCHAR NULL,
    owner_communication VARCHAR NULL,
    personality JSONB NULL,
    learned_patterns JSONB NULL,
    recent_decisions JSONB NULL,
    open_items JSONB NULL,
    summary TEXT NULL,
    tier_scope VARCHAR NOT NULL DEFAULT 'basic',
    rolling_window_days INTEGER NOT NULL DEFAULT 30,
    last_evolved_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_shop_soul_shop UNIQUE (shop_id)
);

CREATE INDEX IF NOT EXISTS idx_shop_soul_shop_id ON shop_soul(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_soul_tier_scope ON shop_soul(tier_scope);

CREATE TABLE IF NOT EXISTS soul_learnings (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    run_id INTEGER NULL REFERENCES agent_runs(id) ON DELETE SET NULL,
    source VARCHAR NOT NULL DEFAULT 'conversation',
    category VARCHAR NOT NULL DEFAULT 'pattern',
    content TEXT NOT NULL,
    confidence_score FLOAT NOT NULL DEFAULT 0.5,
    evidence JSONB NULL,
    graduated BOOLEAN NOT NULL DEFAULT FALSE,
    observed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_soul_learnings_shop_id ON soul_learnings(shop_id);
CREATE INDEX IF NOT EXISTS idx_soul_learnings_run_id ON soul_learnings(run_id);
CREATE INDEX IF NOT EXISTS idx_soul_learnings_source ON soul_learnings(source);
CREATE INDEX IF NOT EXISTS idx_soul_learnings_category ON soul_learnings(category);
CREATE INDEX IF NOT EXISTS idx_soul_learnings_graduated ON soul_learnings(graduated);

CREATE TABLE IF NOT EXISTS commitments (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    run_id INTEGER NULL REFERENCES agent_runs(id) ON DELETE SET NULL,
    made_by VARCHAR NOT NULL,
    commitment TEXT NOT NULL,
    due_at TIMESTAMP NULL,
    trigger_if_missed TEXT NULL,
    status VARCHAR NOT NULL DEFAULT 'pending',
    action_payload JSONB NULL,
    detected_from JSONB NULL,
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_commitments_shop_id ON commitments(shop_id);
CREATE INDEX IF NOT EXISTS idx_commitments_run_id ON commitments(run_id);
CREATE INDEX IF NOT EXISTS idx_commitments_made_by ON commitments(made_by);
CREATE INDEX IF NOT EXISTS idx_commitments_due_at ON commitments(due_at);
CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(status);

CREATE TABLE IF NOT EXISTS shop_schedules (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    created_by_user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    schedule_key VARCHAR NOT NULL,
    temporal_schedule_id VARCHAR NOT NULL,
    schedule_type VARCHAR NOT NULL DEFAULT 'custom',
    title VARCHAR NOT NULL,
    description TEXT NULL,
    natural_language TEXT NULL,
    cron_expression VARCHAR NOT NULL,
    timezone VARCHAR NOT NULL DEFAULT 'UTC',
    target_agent VARCHAR NOT NULL DEFAULT 'supervisor',
    action_payload JSONB NULL,
    condition_payload JSONB NULL,
    status VARCHAR NOT NULL DEFAULT 'active',
    tier_scope VARCHAR NOT NULL DEFAULT 'free',
    last_triggered_at TIMESTAMP NULL,
    cancelled_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_shop_schedule_key UNIQUE (shop_id, schedule_key),
    CONSTRAINT uq_shop_schedule_temporal_id UNIQUE (temporal_schedule_id)
);

CREATE INDEX IF NOT EXISTS idx_shop_schedules_shop_id ON shop_schedules(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_schedules_created_by ON shop_schedules(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_shop_schedules_schedule_key ON shop_schedules(schedule_key);
CREATE INDEX IF NOT EXISTS idx_shop_schedules_temporal_id ON shop_schedules(temporal_schedule_id);
CREATE INDEX IF NOT EXISTS idx_shop_schedules_type ON shop_schedules(schedule_type);
CREATE INDEX IF NOT EXISTS idx_shop_schedules_status ON shop_schedules(status);
CREATE INDEX IF NOT EXISTS idx_shop_schedules_target_agent ON shop_schedules(target_agent);
CREATE INDEX IF NOT EXISTS idx_shop_schedules_tier_scope ON shop_schedules(tier_scope);

CREATE OR REPLACE FUNCTION update_agent_brain_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_shop_soul_updated_at ON shop_soul;
CREATE TRIGGER trg_shop_soul_updated_at
BEFORE UPDATE ON shop_soul
FOR EACH ROW
EXECUTE FUNCTION update_agent_brain_updated_at();

DROP TRIGGER IF EXISTS trg_commitments_updated_at ON commitments;
CREATE TRIGGER trg_commitments_updated_at
BEFORE UPDATE ON commitments
FOR EACH ROW
EXECUTE FUNCTION update_agent_brain_updated_at();

DROP TRIGGER IF EXISTS trg_shop_schedules_updated_at ON shop_schedules;
CREATE TRIGGER trg_shop_schedules_updated_at
BEFORE UPDATE ON shop_schedules
FOR EACH ROW
EXECUTE FUNCTION update_agent_brain_updated_at();