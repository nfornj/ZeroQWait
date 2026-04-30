-- Migration 005: Shop Operating Hours
-- Adds per-shop time config for Temporal operational schedules
-- (auto-open queue at open_time, pre-close intelligence, auto-close queue at close_time)

-- ─── shop_operating_hours ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shop_operating_hours (
    id                      SERIAL PRIMARY KEY,
    shop_id                 INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,

    -- Daily open/close (stored as HH:MM in 24h local time)
    open_time               TIME NOT NULL DEFAULT '09:00:00',
    close_time              TIME NOT NULL DEFAULT '17:00:00',

    -- IANA timezone for this shop (e.g. "America/New_York")
    timezone                VARCHAR(64) NOT NULL DEFAULT 'UTC',

    -- Whether Temporal should automatically open/close the queue
    auto_open_queue         BOOLEAN NOT NULL DEFAULT TRUE,
    auto_close_queue        BOOLEAN NOT NULL DEFAULT TRUE,

    -- How many minutes before close to run the pre-close intelligence assessment
    pre_close_buffer_minutes INTEGER NOT NULL DEFAULT 15,

    -- If waiting_count * avg_service_time will exceed remaining_open_minutes,
    -- don't accept additional joins automatically (agent will notify owner instead)
    auto_lock_joins         BOOLEAN NOT NULL DEFAULT TRUE,

    -- Which days are operating days (0=Mon … 6=Sun)
    operating_days          INTEGER[] NOT NULL DEFAULT '{0,1,2,3,4,5,6}',

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_shop_operating_hours UNIQUE (shop_id)
);

CREATE INDEX IF NOT EXISTS ix_shop_operating_hours_shop_id ON shop_operating_hours (shop_id);

-- Seed a default row for every existing active shop so they are immediately
-- managed by the new schedules. Shops can update via API to customise their hours.
INSERT INTO shop_operating_hours (shop_id)
SELECT id FROM shops WHERE is_active = TRUE
ON CONFLICT (shop_id) DO NOTHING;

-- ─── Queue new columns ───────────────────────────────────────────────────────
-- Allows Temporal to lock new joins without fully closing the queue
ALTER TABLE queues
    ADD COLUMN IF NOT EXISTS accepting_joins BOOLEAN NOT NULL DEFAULT TRUE;

-- track why a queue was locked/closed (for owner visibility in Agent Inbox)
ALTER TABLE queues
    ADD COLUMN IF NOT EXISTS lock_reason TEXT;

-- ─── Helper trigger: auto-update updated_at ──────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_shop_operating_hours_updated_at ON shop_operating_hours;
CREATE TRIGGER trg_shop_operating_hours_updated_at
    BEFORE UPDATE ON shop_operating_hours
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
