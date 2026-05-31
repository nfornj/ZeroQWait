"""Schema hook for the lawn care vertical module."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

_TENANT_SCHEMA_RE = re.compile(r"^tenant_\d+$")


def run_schema_migration(tenant_id: str, db_session: Any) -> None:
	"""Add lawn-care appointment fields inside the tenant schema if missing."""
	schema_name = _tenant_schema_name(tenant_id)
	db_session.execute(text(f"SET search_path TO {schema_name}, platform, public"))
	db_session.execute(text(
		"""
		ALTER TABLE appointments
			ADD COLUMN IF NOT EXISTS property_size_sqft INTEGER,
			ADD COLUMN IF NOT EXISTS grass_type VARCHAR(50),
			ADD COLUMN IF NOT EXISTS recurring_interval VARCHAR(20),
			ADD COLUMN IF NOT EXISTS weather_hold BOOLEAN DEFAULT false
		"""
	))
	db_session.execute(text("SET search_path TO platform, public"))


def _tenant_schema_name(tenant_id: str) -> str:
	schema_name = f"tenant_{int(tenant_id)}"
	if not _TENANT_SCHEMA_RE.match(schema_name):
		raise ValueError(f"Invalid tenant schema name: {schema_name}")
	return schema_name