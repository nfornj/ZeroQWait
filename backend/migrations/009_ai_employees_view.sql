-- Migration: Add ai_employees view for the finance query engine
-- Date: 2026-04-25
--
-- Adds a tenant-scoped ai_employees view so the dynamic finance SQL agent
-- can answer employee-related questions (e.g. "Which employee handled the
-- most visits this week?") without referencing raw tables.
--
-- Apply with:
--   kubectl exec -n zeroqwait deploy/backend -- \
--     python scripts/apply_migration.py ../migrations/009_ai_employees_view.sql

CREATE OR REPLACE VIEW ai_employees AS
SELECT
    se.id          AS employee_id,
    se.user_id,
    u.username,
    u.role::text   AS role,
    se.is_active,
    se.shop_id,
    se.created_at  AS joined_at
FROM shop_employees se
JOIN users u ON u.id = se.user_id
WHERE se.shop_id = NULLIF(current_setting('app.current_shop_id', true), '')::integer;

-- Grant SELECT to the AI agent role if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zeroqwait_ai_agent') THEN
        GRANT SELECT ON ai_employees TO zeroqwait_ai_agent;
    END IF;
END $$;
