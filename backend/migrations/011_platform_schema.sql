-- Migration 011: Promote control-plane tables to the platform schema.
--
-- Goal:
--   Separate the ZeroQwait company-level authority tables (users, shops,
--   shop_runtime_assignments, audit_logs) from the shop-operational data plane.
--
--   Before: all tables live in public
--   After:  company/authority tables → platform schema
--           shop-operational tables  → public schema (unchanged)
--           DB default search_path   → platform, public
--
-- Safety guarantees:
--   • Idempotent: every ALTER TABLE is guarded by an information_schema check.
--   • PostgreSQL FK constraints are OID-based, not name-based — moving a table
--     does NOT break existing FK constraints from public tables pointing to the
--     moved tables. They continue to reference the same table OID.
--   • DB-level search_path is updated so that unqualified SQL in legacy code
--     (e.g. "SELECT * FROM users") still resolves correctly via platform schema.
--   • Associated serial sequences are moved with the table in PostgreSQL 15.
--
-- Usage:
--   psql -U zeroqwait -d zeroqwait -f 011_platform_schema.sql
--
-- Post-migration restart:
--   The application must be restarted so the SQLAlchemy event listeners pick up
--   the updated search_path configuration in database.py.

BEGIN;

-- ── 1. Create the platform schema ──────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS platform;

-- ── 2. Move users ──────────────────────────────────────────────────────────
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'users'
    ) THEN
        ALTER TABLE public.users SET SCHEMA platform;
        RAISE NOTICE 'Migration 011: moved public.users → platform.users';
    ELSE
        RAISE NOTICE 'Migration 011: users already in platform schema (idempotent skip)';
    END IF;
END $$;

-- ── 3. Move shops ──────────────────────────────────────────────────────────
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'shops'
    ) THEN
        ALTER TABLE public.shops SET SCHEMA platform;
        RAISE NOTICE 'Migration 011: moved public.shops → platform.shops';
    ELSE
        RAISE NOTICE 'Migration 011: shops already in platform schema (idempotent skip)';
    END IF;
END $$;

-- ── 4. Move or create shop_runtime_assignments ─────────────────────────────
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'platform' AND table_name = 'shop_runtime_assignments'
    ) THEN
        RAISE NOTICE 'Migration 011: shop_runtime_assignments already in platform schema (idempotent skip)';
    ELSIF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'shop_runtime_assignments'
    ) THEN
        ALTER TABLE public.shop_runtime_assignments SET SCHEMA platform;
        RAISE NOTICE 'Migration 011: moved public.shop_runtime_assignments → platform.shop_runtime_assignments';
    ELSE
        -- Table was introduced with this migration — create it directly in platform
        CREATE TABLE platform.shop_runtime_assignments (
            id              SERIAL PRIMARY KEY,
            shop_id         INTEGER NOT NULL UNIQUE REFERENCES platform.shops(id) ON DELETE CASCADE,
            runtime_mode    VARCHAR(32)  NOT NULL DEFAULT 'shared_instance',
            instance_key    VARCHAR(128),
            namespace       VARCHAR(64),
            backend_service VARCHAR(128),
            worker_service  VARCHAR(128),
            route_host      VARCHAR(255),
            runtime_status  VARCHAR(32)  NOT NULL DEFAULT 'pending',
            assigned_at     TIMESTAMP,
            created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP    NOT NULL DEFAULT NOW()
        );
        CREATE INDEX ix_shop_runtime_assignments_shop_id       ON platform.shop_runtime_assignments(shop_id);
        CREATE INDEX ix_shop_runtime_assignments_runtime_mode  ON platform.shop_runtime_assignments(runtime_mode);
        CREATE INDEX ix_shop_runtime_assignments_instance_key  ON platform.shop_runtime_assignments(instance_key);
        CREATE INDEX ix_shop_runtime_assignments_route_host    ON platform.shop_runtime_assignments(route_host);
        CREATE INDEX ix_shop_runtime_assignments_runtime_status ON platform.shop_runtime_assignments(runtime_status);
        RAISE NOTICE 'Migration 011: created platform.shop_runtime_assignments (new table)';
    END IF;
END $$;

-- ── 5. Move audit_logs ─────────────────────────────────────────────────────
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'audit_logs'
    ) THEN
        ALTER TABLE public.audit_logs SET SCHEMA platform;
        RAISE NOTICE 'Migration 011: moved public.audit_logs → platform.audit_logs';
    ELSE
        RAISE NOTICE 'Migration 011: audit_logs already in platform schema (idempotent skip)';
    END IF;
END $$;

-- ── 6. Set DB-level default search_path ────────────────────────────────────
-- This ensures any connection that does not override search_path (e.g. psql,
-- pgAdmin, ad-hoc queries) resolves platform tables without qualification.
-- The application's SQLAlchemy event listener (database.py) also sets
-- search_path per-session and is updated in the same release.
ALTER DATABASE zeroqwait SET search_path = platform, public;

COMMIT;

-- ── Post-migration verification (informational) ────────────────────────────
SELECT
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_name IN ('users', 'shops', 'shop_runtime_assignments', 'audit_logs')
ORDER BY table_name;
