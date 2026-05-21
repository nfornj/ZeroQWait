-- Migration: Service catalog sections
-- Date: 2026-05-21

ALTER TABLE shop_services
ADD COLUMN IF NOT EXISTS catalog_section VARCHAR(32) NOT NULL DEFAULT 'popular';

WITH ranked_services AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY shop_id
            ORDER BY COALESCE(created_at, NOW()), id
        ) AS section_rank
    FROM shop_services
    WHERE is_active = TRUE
)
UPDATE shop_services AS service
SET catalog_section = CASE
    WHEN ranked_services.section_rank <= 3 THEN 'popular'
    ELSE 'specialized'
END
FROM ranked_services
WHERE service.id = ranked_services.id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_shop_services_catalog_section'
    ) THEN
        ALTER TABLE shop_services
        ADD CONSTRAINT ck_shop_services_catalog_section
        CHECK (catalog_section IN ('popular', 'specialized'));
    END IF;
END $$;
