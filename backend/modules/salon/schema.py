"""Schema hook for the salon vertical module."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

_TENANT_SCHEMA_RE = re.compile(r"^tenant_\d+$")


def run_schema_migration(tenant_id: str, db_session: Any) -> None:
	"""Add salon customer-profile columns inside the tenant schema if missing."""
	schema_name = _tenant_schema_name(tenant_id)
	db_session.execute(text(f"SET search_path TO {schema_name}, platform, public"))
	db_session.execute(text(
		"""
		DO $$
		BEGIN
			IF NOT EXISTS (
				SELECT 1
				FROM information_schema.columns
				WHERE table_schema = current_schema()
				  AND table_name = 'shop_customers'
				  AND column_name = 'skin_type'
			) THEN
				ALTER TABLE shop_customers ADD COLUMN skin_type TEXT;
			END IF;

			IF NOT EXISTS (
				SELECT 1
				FROM information_schema.columns
				WHERE table_schema = current_schema()
				  AND table_name = 'shop_customers'
				  AND column_name = 'sensitivities'
			) THEN
				ALTER TABLE shop_customers ADD COLUMN sensitivities TEXT;
			END IF;

			IF NOT EXISTS (
				SELECT 1
				FROM information_schema.columns
				WHERE table_schema = current_schema()
				  AND table_name = 'shop_customers'
				  AND column_name = 'last_treatment_product'
			) THEN
				ALTER TABLE shop_customers ADD COLUMN last_treatment_product TEXT;
			END IF;
		END $$
		"""
	))
	db_session.execute(text("SET search_path TO platform, public"))


def _tenant_schema_name(tenant_id: str) -> str:
	schema_name = f"tenant_{int(tenant_id)}"
	if not _TENANT_SCHEMA_RE.match(schema_name):
		raise ValueError(f"Invalid tenant schema name: {schema_name}")
	return schema_name