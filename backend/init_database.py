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
