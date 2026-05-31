"""Schema hook for the core ZeroQWait module."""

from __future__ import annotations

from typing import Any


def run_schema_migration(tenant_id: str, db_session: Any) -> None:
	"""Leave core schema management to the main Alembic/SQL migrations."""
	# Core tables are platform-owned and already managed by the main migration
	# sequence under backend/migrations, not by the vertical module layer.
	return None