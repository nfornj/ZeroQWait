-- Migration 015: add_active_modules_to_shops
--
-- Adds vertical-module activation metadata to the main tenant table.
-- The main tenant table is platform.shops after migration 011.

ALTER TABLE platform.shops
    ADD COLUMN IF NOT EXISTS active_modules JSON NOT NULL DEFAULT '[]'::json,
    ADD COLUMN IF NOT EXISTS vertical VARCHAR(50) DEFAULT 'generic';

UPDATE platform.shops
SET active_modules = '[]'::json
WHERE active_modules IS NULL;

UPDATE platform.shops
SET vertical = 'generic'
WHERE vertical IS NULL;
