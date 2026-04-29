#!/usr/bin/env python3
"""Create missing tables in the current PostgreSQL database using SQLAlchemy metadata."""

from sqlalchemy import inspect

import models  # noqa: F401  Ensures SQLAlchemy model metadata is registered.
from database import DATABASE_URL, Base, engine


def main() -> int:
    print("ZeroQwait database bootstrap")
    print("-" * 60)
    print(f"Database: {engine.url.render_as_string(hide_password=True)}")
    print("Creating missing tables from SQLAlchemy metadata...")

    try:
        Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)
        tables = sorted(inspector.get_table_names())

        print(f"Created or verified {len(tables)} table(s):")
        for table_name in tables:
            print(f"  - {table_name}")

        print()
        print("Next steps:")
        print("  1. Start the backend: uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        print("  2. Open the API docs at http://localhost:8000/docs")
        print("  3. Run focused tests with uv run pytest -q")
        return 0
    except Exception as exc:
        print(f"Failed to bootstrap database metadata: {exc}")
        print()
        print("Troubleshooting:")
        print("  1. Verify DB_HOST, DB_PORT, DB_NAME, DB_USER, and DB_PASSWORD")
        print("  2. Confirm PostgreSQL is reachable from the current environment")
        print("  3. Re-check backend/.env or deployment-managed database settings")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
