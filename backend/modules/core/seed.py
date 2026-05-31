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
			INSERT INTO {queue_schema}.queues (shop_id, name, date, is_active, accepting_joins)
			SELECT :shop_id, 'Main Queue', NOW(), TRUE, TRUE
			WHERE NOT EXISTS (
				SELECT 1
				FROM {queue_schema}.queues
				WHERE shop_id = :shop_id AND name = 'Main Queue'
			)
			"""
		),
		{"shop_id": shop_id},
	)
	db_session.execute(
		text(
			f"""
			UPDATE {queue_schema}.queues
			SET date = NOW()
			WHERE shop_id = :shop_id AND date IS NULL
			"""
		),
		{"shop_id": shop_id},
	)

	operating_hours_schema = _resolve_optional_shared_schema(db_session, "shop_operating_hours")
	if operating_hours_schema:
		db_session.execute(
			text(
				f"""
				INSERT INTO {operating_hours_schema}.shop_operating_hours (
					shop_id, open_time, close_time, timezone, auto_open_queue,
					auto_close_queue, pre_close_buffer_minutes, auto_lock_joins,
					operating_days, created_at, updated_at
				)
				VALUES (
					:shop_id, '09:00:00'::time, '17:00:00'::time, 'UTC', TRUE,
					TRUE, 15, TRUE, '{{0,1,2,3,4,5,6}}'::integer[], NOW(), NOW()
				)
				ON CONFLICT (shop_id) DO NOTHING
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
		schema = "platform"

	if schema != "platform" and not _TENANT_SCHEMA_RE.match(schema):
		raise ValueError(f"Invalid tenant schema name: {schema}")
	return schema


def _resolve_optional_shared_schema(db_session: Any, table_name: str) -> str | None:
	row = db_session.execute(
		text(
			"""
			SELECT table_schema
			FROM information_schema.tables
			WHERE table_name = :table_name
			  AND table_schema IN ('platform', 'public')
			ORDER BY CASE table_schema WHEN 'platform' THEN 0 ELSE 1 END
			LIMIT 1
			"""
		),
		{"table_name": table_name},
	).first()
	return str(row[0]) if row else None
