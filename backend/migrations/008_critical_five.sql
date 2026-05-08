-- Migration 008: Critical 5 Features — Service Catalogue, Inventory, POS, Online Booking,
--                Customer Notifications
-- Date: 2026-05-04
--
-- Changes:
--   1. Extend shop_services with pricing, HST flag, staff assignment, supply linkage, category
--   2. CREATE inventory_items           — tracked supply/product items per shop
--   3. CREATE inventory_movements       — full audit trail of stock changes
--   4. CREATE pos_transactions          — point-of-sale receipts
--   5. CREATE pos_transaction_lines     — line items within a POS receipt
--   6. CREATE public_booking_pages      — per-shop online booking configuration
--   7. Extend appointments with booking_source, reminder flags, public_token

-- ──────────────────────────────────────────────────────────────────────────────
-- 1. Extend shop_services
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE shop_services
    ADD COLUMN IF NOT EXISTS price_cents      INTEGER          NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS hst_applicable   BOOLEAN          NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS staff_ids        INTEGER[]        NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS supplies_used    JSONB            NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS category         TEXT             NULL;

-- Back-fill price_cents from existing cost column (stored in dollars × 100)
UPDATE shop_services
SET price_cents = ROUND(COALESCE(cost, 0) * 100)::INTEGER
WHERE price_cents = 0 AND COALESCE(cost, 0) > 0;

-- ──────────────────────────────────────────────────────────────────────────────
-- 2. inventory_items
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inventory_items (
    id                  SERIAL PRIMARY KEY,
    shop_id             INTEGER        NOT NULL REFERENCES shops(id) ON DELETE CASCADE,

    name                TEXT           NOT NULL,
    sku                 TEXT           NULL,
    category            TEXT           NULL,                    -- e.g. 'product', 'supply', 'consumable'
    unit                TEXT           NOT NULL DEFAULT 'piece', -- piece | ml | g | kg | oz | litre | box
    current_stock       NUMERIC(10, 2) NOT NULL DEFAULT 0,
    reorder_threshold   NUMERIC(10, 2) NOT NULL DEFAULT 0,
    cost_per_unit       NUMERIC(10, 4) NULL,                    -- purchase cost per unit (for COGS)
    retail_price_cents  INTEGER        NULL,                    -- selling price in cents (0 = internal use only)
    supplier            TEXT           NULL,

    is_active           BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_inventory_items_shop_id   ON inventory_items(shop_id);
CREATE INDEX IF NOT EXISTS ix_inventory_items_is_active ON inventory_items(shop_id, is_active);

-- ──────────────────────────────────────────────────────────────────────────────
-- 3. inventory_movements
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inventory_movements (
    id                  SERIAL PRIMARY KEY,
    shop_id             INTEGER        NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    item_id             INTEGER        NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,

    movement_type       TEXT           NOT NULL
                        CHECK (movement_type IN ('restock', 'usage', 'adjustment', 'service_deduction', 'sale', 'write_off')),
    quantity            NUMERIC(10, 2) NOT NULL,                -- positive = stock added; negative = stock removed
    stock_after         NUMERIC(10, 2) NULL,                    -- snapshot of current_stock after movement
    unit_cost           NUMERIC(10, 4) NULL,                    -- cost at time of movement (for COGS)

    notes               TEXT           NULL,
    appointment_id      INTEGER        NULL REFERENCES appointments(id) ON DELETE SET NULL,
    created_by          INTEGER        NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_inventory_movements_shop_id ON inventory_movements(shop_id);
CREATE INDEX IF NOT EXISTS ix_inventory_movements_item_id ON inventory_movements(item_id);
CREATE INDEX IF NOT EXISTS ix_inventory_movements_created_at ON inventory_movements(shop_id, created_at DESC);

-- ──────────────────────────────────────────────────────────────────────────────
-- 4. pos_transactions
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pos_transactions (
    id                  SERIAL PRIMARY KEY,
    shop_id             INTEGER        NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    customer_id         INTEGER        NULL REFERENCES shop_customers(id) ON DELETE SET NULL,
    employee_id         INTEGER        NULL REFERENCES shop_employees(id) ON DELETE SET NULL,
    appointment_id      INTEGER        NULL REFERENCES appointments(id) ON DELETE SET NULL,

    -- Amounts stored in cents (integer arithmetic — no float rounding errors)
    subtotal_cents      INTEGER        NOT NULL DEFAULT 0,      -- pre-tax total
    hst_cents           INTEGER        NOT NULL DEFAULT 0,      -- 13% on hst_applicable lines (Ontario)
    tip_cents           INTEGER        NOT NULL DEFAULT 0,
    discount_cents      INTEGER        NOT NULL DEFAULT 0,      -- positive = money off
    total_cents         INTEGER        NOT NULL DEFAULT 0,      -- subtotal + hst + tip - discount

    payment_method      TEXT           NOT NULL DEFAULT 'cash'  -- cash | card | e-transfer | other
                        CHECK (payment_method IN ('cash', 'card', 'e-transfer', 'other')),
    status              TEXT           NOT NULL DEFAULT 'open'  -- open | complete | voided | refunded
                        CHECK (status IN ('open', 'complete', 'voided', 'refunded')),

    notes               TEXT           NULL,
    receipt_sent        BOOLEAN        NOT NULL DEFAULT FALSE,  -- notification dispatched?

    completed_at        TIMESTAMPTZ    NULL,
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_pos_transactions_shop_id    ON pos_transactions(shop_id);
CREATE INDEX IF NOT EXISTS ix_pos_transactions_customer   ON pos_transactions(customer_id);
CREATE INDEX IF NOT EXISTS ix_pos_transactions_status     ON pos_transactions(shop_id, status);
CREATE INDEX IF NOT EXISTS ix_pos_transactions_created_at ON pos_transactions(shop_id, created_at DESC);

-- ──────────────────────────────────────────────────────────────────────────────
-- 5. pos_transaction_lines
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pos_transaction_lines (
    id                  SERIAL PRIMARY KEY,
    transaction_id      INTEGER        NOT NULL REFERENCES pos_transactions(id) ON DELETE CASCADE,
    service_id          INTEGER        NULL REFERENCES shop_services(id) ON DELETE SET NULL,
    item_id             INTEGER        NULL REFERENCES inventory_items(id) ON DELETE SET NULL,

    description         TEXT           NOT NULL,
    quantity            NUMERIC(10, 2) NOT NULL DEFAULT 1,
    unit_price_cents    INTEGER        NOT NULL DEFAULT 0,
    hst_applicable      BOOLEAN        NOT NULL DEFAULT TRUE,
    line_total_cents    INTEGER        NOT NULL DEFAULT 0,      -- quantity × unit_price_cents

    created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_pos_transaction_lines_txn ON pos_transaction_lines(transaction_id);

-- ──────────────────────────────────────────────────────────────────────────────
-- 6. public_booking_pages
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public_booking_pages (
    id                  SERIAL PRIMARY KEY,
    shop_id             INTEGER        NOT NULL UNIQUE REFERENCES shops(id) ON DELETE CASCADE,

    is_enabled          BOOLEAN        NOT NULL DEFAULT TRUE,
    title               TEXT           NULL,                    -- e.g. "Book at Fade Factory"
    welcome_message     TEXT           NULL,
    max_advance_days    INTEGER        NOT NULL DEFAULT 30,     -- how far ahead customers can book
    min_advance_hours   INTEGER        NOT NULL DEFAULT 1,      -- earliest bookable (e.g. 1h from now)
    require_phone       BOOLEAN        NOT NULL DEFAULT TRUE,
    require_email       BOOLEAN        NOT NULL DEFAULT FALSE,

    created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_public_booking_pages_shop_id ON public_booking_pages(shop_id);

-- ──────────────────────────────────────────────────────────────────────────────
-- 7. Extend appointments
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS booking_source     TEXT    NOT NULL DEFAULT 'owner'
                                                CHECK (booking_source IN ('owner', 'public', 'agent')),
    ADD COLUMN IF NOT EXISTS reminder_24h_sent  BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS reminder_1h_sent   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS public_token       TEXT    NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_appointments_public_token ON appointments(public_token) WHERE public_token IS NOT NULL;
