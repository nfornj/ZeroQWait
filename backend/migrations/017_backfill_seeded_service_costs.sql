-- Migration 017: Backfill legacy service cost from price_cents.
--
-- The service catalog/POS path stores price_cents, while older public and
-- simulation APIs still serialize shop_services.cost as dollars. Vertical
-- module seeds must keep both populated during the transition.

DO $$
DECLARE
    schema_name text;
BEGIN
    FOR schema_name IN
        SELECT nspname
        FROM pg_namespace
        WHERE nspname IN ('platform', 'public') OR nspname LIKE 'tenant\_%' ESCAPE '\'
    LOOP
        IF EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = schema_name
              AND table_name = 'shop_services'
        ) THEN
            EXECUTE format(
                'UPDATE %I.shop_services SET cost = price_cents / 100.0 WHERE cost IS NULL AND price_cents > 0',
                schema_name
            );
        END IF;
    END LOOP;
END $$;