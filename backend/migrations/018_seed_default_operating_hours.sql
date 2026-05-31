-- Migration 018: Seed default operating hours for active shops.
--
-- New vertical module provisioning relies on a complete first-run tenant setup.
-- If a shop has no shop_operating_hours row, time-aware queue/simulation paths
-- get a 404 and have to fall back to process-local defaults.

DO $$
DECLARE
    schema_name text;
BEGIN
    SELECT table_schema
    INTO schema_name
    FROM information_schema.tables
    WHERE table_name = 'shop_operating_hours'
      AND table_schema IN ('platform', 'public')
    ORDER BY CASE table_schema WHEN 'platform' THEN 0 ELSE 1 END
    LIMIT 1;

    IF schema_name IS NOT NULL THEN
        EXECUTE format(
            'INSERT INTO %I.shop_operating_hours (
                 shop_id, open_time, close_time, timezone, auto_open_queue,
                 auto_close_queue, pre_close_buffer_minutes, auto_lock_joins,
                 operating_days, created_at, updated_at
             )
             SELECT
                 id, ''09:00:00''::time, ''17:00:00''::time, ''UTC'', TRUE,
                 TRUE, 15, TRUE, ''{0,1,2,3,4,5,6}''::integer[], NOW(), NOW()
             FROM platform.shops WHERE is_active = TRUE
             ON CONFLICT (shop_id) DO NOTHING',
            schema_name
        );
    END IF;
END $$;