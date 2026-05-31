"""Seed default shop configuration required by every ZeroQWait tenant."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

_TENANT_SCHEMA_RE = re.compile(r"^tenant_\d+$")


def run_seed(tenant_id: str, db_session: Any) -> None:
	"""Seed baseline tenant configuration in an idempotent way."""
	shop_id = int(tenant_id)
	shop = db_session.execute(
		text(
			"""
			SELECT id, shop_type, tenant_schema, data_isolation_mode
			FROM platform.shops
			WHERE id = :shop_id
			"""
		),
		{"shop_id": shop_id},
	).mappings().first()
	if not shop:
		raise ValueError(f"Shop {shop_id} not found")

	vertical = str(shop.get("shop_type") or "generic").strip().lower() or "generic"
	db_session.execute(
		text(
			"""
			UPDATE platform.shops
			SET
				active_modules = CASE
					WHEN active_modules::jsonb ? 'core' THEN active_modules
					ELSE (active_modules::jsonb || '["core"]'::jsonb)::json
				END,
				vertical = COALESCE(NULLIF(vertical, ''), :vertical)
			WHERE id = :shop_id
			"""
		),
		{"shop_id": shop_id, "vertical": vertical},
	)

	queue_schema = _resolve_queue_schema(shop)
	db_session.execute(
		text(
			f"""
			INSERT INTO {queue_schema}.queues (shop_id, name, is_active, accepting_joins)
			SELECT :shop_id, 'Main Queue', TRUE, TRUE
			WHERE NOT EXISTS (
				SELECT 1
				FROM {queue_schema}.queues
				WHERE shop_id = :shop_id AND name = 'Main Queue'
			)
			"""
		),
		{"shop_id": shop_id},
	)


def _resolve_queue_schema(shop: dict[str, Any]) -> str:
	schema = shop.get("tenant_schema")
	if schema:
		schema = str(schema)
	elif shop.get("data_isolation_mode") == "shop_schema":
		schema = f"tenant_{int(shop['id'])}"
	else:
		schema = "public"

	if schema != "public" and not _TENANT_SCHEMA_RE.match(schema):
		raise ValueError(f"Invalid tenant schema name: {schema}")
	return schema