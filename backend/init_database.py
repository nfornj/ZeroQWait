"""
Initialize local PostgreSQL database with tables
Run this before starting the application
"""
import os
import sys
from database import engine, Base
from sqlalchemy import text
import models

def init_db():
    """Create all tables in the database"""
    print("Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ All tables created successfully!")
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        return False

    # Idempotent column migrations — run after create_all so that both fresh
    # installs (table just created, columns present) and upgrades of existing
    # databases (table exists, new columns missing) work correctly.
    migrations = [
        # Telegram integration columns (added 2026-04)
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR",
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS telegram_chat_id_hash VARCHAR",
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS telegram_notifications_enabled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS telegram_connect_token VARCHAR",
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS telegram_connect_token_expires_at TIMESTAMPTZ",
        # Explicit shop isolation/runtime metadata (added 2026-05)
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS data_isolation_mode VARCHAR(32) NOT NULL DEFAULT 'shared_public'",
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS compute_mode VARCHAR(32) NOT NULL DEFAULT 'shared_instance'",
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS active_modules JSON NOT NULL DEFAULT '[]'::json",
        "ALTER TABLE shops ADD COLUMN IF NOT EXISTS vertical VARCHAR(50) DEFAULT 'generic'",
        "UPDATE shops SET data_isolation_mode = CASE WHEN tenant_schema IS NOT NULL THEN 'shop_schema' ELSE 'shared_public' END",
        "ALTER TABLE queues ALTER COLUMN date SET DEFAULT NOW()",
        "UPDATE queues SET date = NOW() WHERE date IS NULL",
        # Critical inventory/service catalogue tables used by vertical module seeding.
        """ALTER TABLE shop_services
            ADD COLUMN IF NOT EXISTS price_cents INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS hst_applicable BOOLEAN NOT NULL DEFAULT TRUE,
            ADD COLUMN IF NOT EXISTS staff_ids INTEGER[] NOT NULL DEFAULT '{}',
            ADD COLUMN IF NOT EXISTS supplies_used JSONB NOT NULL DEFAULT '[]',
            ADD COLUMN IF NOT EXISTS category TEXT NULL""",
        """UPDATE shop_services
            SET price_cents = ROUND(COALESCE(cost, 0) * 100)::INTEGER
            WHERE price_cents = 0 AND COALESCE(cost, 0) > 0""",
        """UPDATE shop_services
            SET cost = price_cents / 100.0
            WHERE cost IS NULL AND price_cents > 0""",
        """CREATE TABLE IF NOT EXISTS inventory_items (
            id                  SERIAL PRIMARY KEY,
            shop_id             INTEGER        NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
            name                TEXT           NOT NULL,
            sku                 TEXT           NULL,
            category            TEXT           NULL,
            unit                TEXT           NOT NULL DEFAULT 'piece',
            current_stock       NUMERIC(10, 2) NOT NULL DEFAULT 0,
            reorder_threshold   NUMERIC(10, 2) NOT NULL DEFAULT 0,
            cost_per_unit       NUMERIC(10, 4) NULL,
            retail_price_cents  INTEGER        NULL,
            supplier            TEXT           NULL,
            is_active           BOOLEAN        NOT NULL DEFAULT TRUE,
            created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_inventory_items_shop_id ON inventory_items(shop_id)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_items_is_active ON inventory_items(shop_id, is_active)",
        """CREATE TABLE IF NOT EXISTS inventory_movements (
            id                  SERIAL PRIMARY KEY,
            shop_id             INTEGER        NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
            item_id             INTEGER        NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
            movement_type       TEXT           NOT NULL CHECK (movement_type IN ('restock', 'usage', 'adjustment', 'service_deduction', 'sale', 'write_off')),
            quantity            NUMERIC(10, 2) NOT NULL,
            stock_after         NUMERIC(10, 2) NULL,
            unit_cost           NUMERIC(10, 4) NULL,
            notes               TEXT           NULL,
            appointment_id      INTEGER        NULL REFERENCES appointments(id) ON DELETE SET NULL,
            created_by          INTEGER        NULL REFERENCES users(id) ON DELETE SET NULL,
            created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_inventory_movements_shop_id ON inventory_movements(shop_id)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_movements_item_id ON inventory_movements(item_id)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_movements_created_at ON inventory_movements(shop_id, created_at DESC)",
        # notification_log table
        """CREATE TABLE IF NOT EXISTS notification_log (
            id          BIGSERIAL PRIMARY KEY,
            shop_id     INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
            channel     VARCHAR(32) NOT NULL,
            event_type  VARCHAR(64) NOT NULL,
            message_text TEXT,
            status      VARCHAR(32) NOT NULL DEFAULT 'pending',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        # premium runtime-assignment metadata
        """CREATE TABLE IF NOT EXISTS shop_runtime_assignments (
            id              BIGSERIAL PRIMARY KEY,
            shop_id         INTEGER NOT NULL UNIQUE REFERENCES shops(id) ON DELETE CASCADE,
            runtime_mode    VARCHAR(32) NOT NULL DEFAULT 'shared_instance',
            instance_key    VARCHAR(128),
            namespace       VARCHAR(64),
            backend_service VARCHAR(128),
            worker_service  VARCHAR(128),
            route_host      VARCHAR(255),
            runtime_status  VARCHAR(32) NOT NULL DEFAULT 'pending',
            assigned_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS ix_shops_data_isolation_mode ON shops(data_isolation_mode)",
        "CREATE INDEX IF NOT EXISTS ix_shops_compute_mode ON shops(compute_mode)",
        "CREATE INDEX IF NOT EXISTS ix_shop_runtime_assignments_runtime_mode ON shop_runtime_assignments(runtime_mode)",
        "CREATE INDEX IF NOT EXISTS ix_shop_runtime_assignments_instance_key ON shop_runtime_assignments(instance_key)",
        "CREATE INDEX IF NOT EXISTS ix_shop_runtime_assignments_route_host ON shop_runtime_assignments(route_host)",
        "CREATE INDEX IF NOT EXISTS ix_shop_runtime_assignments_runtime_status ON shop_runtime_assignments(runtime_status)",
        """INSERT INTO shop_operating_hours (
                shop_id, open_time, close_time, timezone, auto_open_queue,
                auto_close_queue, pre_close_buffer_minutes, auto_lock_joins,
                operating_days, created_at, updated_at
            )
            SELECT
                id, '09:00:00'::time, '17:00:00'::time, 'UTC', TRUE,
                TRUE, 15, TRUE, '{0,1,2,3,4,5,6}'::integer[], NOW(), NOW()
            FROM platform.shops WHERE is_active = TRUE
            ON CONFLICT (shop_id) DO NOTHING""",
    ]
    try:
        with engine.connect() as conn:
            for sql in migrations:
                conn.execute(text(sql))
            conn.commit()
        print("✓ Column migrations applied successfully!")
    except Exception as e:
        print(f"✗ Error applying column migrations: {e}")
        return False

    return True

if __name__ == "__main__":
    success = init_db()
    sys.exit(0 if success else 1)
