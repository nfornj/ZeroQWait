-- Migration 016: Ensure queues always have a response-safe date value.
--
-- SQLAlchemy's Python-side Column(default=datetime.utcnow) does not create a
-- database default. Core module seeding inserts queues through raw SQL, so a
-- freshly provisioned tenant could start with queues.date = NULL and fail API
-- response validation because the Queue schema requires a datetime.

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
              AND table_name = 'queues'
        ) THEN
            EXECUTE format('ALTER TABLE %I.queues ALTER COLUMN date SET DEFAULT NOW()', schema_name);
            EXECUTE format('UPDATE %I.queues SET date = NOW() WHERE date IS NULL', schema_name);
        END IF;
    END LOOP;
END $$;