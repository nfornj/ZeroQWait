-- Migration 013: Persist owner dashboard settings.
--
-- Adds the fields and supporting tables used by the Merge_New_UI settings
-- stepper. Run after migration 011 so platform.shops exists.

BEGIN;

ALTER TABLE platform.shops
    ADD COLUMN IF NOT EXISTS tagline VARCHAR(255),
    ADD COLUMN IF NOT EXISTS tax_id VARCHAR(128),
    ADD COLUMN IF NOT EXISTS timezone VARCHAR(64),
    ADD COLUMN IF NOT EXISTS instagram VARCHAR(255),
    ADD COLUMN IF NOT EXISTS whatsapp VARCHAR(64),
    ADD COLUMN IF NOT EXISTS dashboard_gradient VARCHAR(32) NOT NULL DEFAULT 'violet';

UPDATE platform.shops
SET dashboard_gradient = 'violet'
WHERE dashboard_gradient IS NULL;

ALTER TABLE public.shop_close_days
    ADD COLUMN IF NOT EXISTS name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS notes TEXT,
    ADD COLUMN IF NOT EXISTS repeat_yearly BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS public.shop_business_hours (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES platform.shops(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    is_open BOOLEAN NOT NULL DEFAULT TRUE,
    open_time TIME NOT NULL DEFAULT '09:00:00',
    close_time TIME NOT NULL DEFAULT '18:00:00',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_shop_business_hours_shop_day UNIQUE (shop_id, day_of_week)
);

CREATE INDEX IF NOT EXISTS ix_shop_business_hours_shop_id
    ON public.shop_business_hours(shop_id);

INSERT INTO public.shop_business_hours (shop_id, day_of_week, is_open, open_time, close_time)
SELECT s.id, d.day_of_week, d.day_of_week <> 6, '09:00:00'::time, '18:00:00'::time
FROM platform.shops s
CROSS JOIN generate_series(0, 6) AS d(day_of_week)
ON CONFLICT (shop_id, day_of_week) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.shop_booking_settings (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL UNIQUE REFERENCES platform.shops(id) ON DELETE CASCADE,
    booking_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    require_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
    allow_rescheduling BOOLEAN NOT NULL DEFAULT TRUE,
    allow_cancellations BOOLEAN NOT NULL DEFAULT TRUE,
    booking_notice_hours INTEGER NOT NULL DEFAULT 24,
    reminder_channel VARCHAR(16) NOT NULL DEFAULT 'email',
    reminder_time_hours INTEGER NOT NULL DEFAULT 24,
    follow_up_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    waiting_list_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    auto_confirm BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_shop_booking_settings_shop_id
    ON public.shop_booking_settings(shop_id);

INSERT INTO public.shop_booking_settings (shop_id)
SELECT id FROM platform.shops
ON CONFLICT (shop_id) DO NOTHING;

CREATE OR REPLACE FUNCTION public.update_shop_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_shop_business_hours_updated_at ON public.shop_business_hours;
CREATE TRIGGER trg_shop_business_hours_updated_at
    BEFORE UPDATE ON public.shop_business_hours
    FOR EACH ROW EXECUTE FUNCTION public.update_shop_settings_updated_at();

DROP TRIGGER IF EXISTS trg_shop_booking_settings_updated_at ON public.shop_booking_settings;
CREATE TRIGGER trg_shop_booking_settings_updated_at
    BEFORE UPDATE ON public.shop_booking_settings
    FOR EACH ROW EXECUTE FUNCTION public.update_shop_settings_updated_at();

COMMIT;
