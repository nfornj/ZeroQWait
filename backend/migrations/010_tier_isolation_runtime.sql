-- Migration 010: Explicit shop data-isolation and compute-runtime metadata.
--
-- Goal:
--   1. Stop inferring runtime topology only from subscription_tier and tenant_schema.
--   2. Track current shop data isolation explicitly.
--   3. Add a dedicated table for future premium runtime assignments.

ALTER TABLE shops
    ADD COLUMN IF NOT EXISTS data_isolation_mode VARCHAR(32) NOT NULL DEFAULT 'shared_public',
    ADD COLUMN IF NOT EXISTS compute_mode VARCHAR(32) NOT NULL DEFAULT 'shared_instance';

UPDATE shops
SET data_isolation_mode = CASE
    WHEN tenant_schema IS NOT NULL THEN 'shop_schema'
    ELSE 'shared_public'
END;

CREATE INDEX IF NOT EXISTS ix_shops_data_isolation_mode ON shops(data_isolation_mode);
CREATE INDEX IF NOT EXISTS ix_shops_compute_mode ON shops(compute_mode);

CREATE TABLE IF NOT EXISTS shop_runtime_assignments (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    runtime_mode VARCHAR(32) NOT NULL DEFAULT 'shared_instance',
    instance_key VARCHAR(128) NULL,
    namespace VARCHAR(64) NULL,
    backend_service VARCHAR(128) NULL,
    worker_service VARCHAR(128) NULL,
    route_host VARCHAR(255) NULL,
    runtime_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    assigned_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_shop_runtime_assignments_shop UNIQUE (shop_id)
);

CREATE INDEX IF NOT EXISTS ix_shop_runtime_assignments_runtime_mode
    ON shop_runtime_assignments(runtime_mode);
CREATE INDEX IF NOT EXISTS ix_shop_runtime_assignments_instance_key
    ON shop_runtime_assignments(instance_key);
CREATE INDEX IF NOT EXISTS ix_shop_runtime_assignments_route_host
    ON shop_runtime_assignments(route_host);
CREATE INDEX IF NOT EXISTS ix_shop_runtime_assignments_runtime_status
    ON shop_runtime_assignments(runtime_status);