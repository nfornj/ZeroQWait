"""Seed lawn-care-specific services, equipment defaults, and configuration."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

_TENANT_SCHEMA_RE = re.compile(r"^tenant_\d+$")

LAWN_CARE_INVENTORY_ITEMS: list[dict[str, Any]] = [
	{"name": "Gas", "unit": "litres", "category": "lawn_care_supply", "initial_stock": 80, "reorder_threshold": 20, "cost_per_unit": 1.65},
	{"name": "2-Stroke Oil", "unit": "ml", "category": "lawn_care_supply", "initial_stock": 5000, "reorder_threshold": 1000, "cost_per_unit": 0.03},
	{"name": "Blade Sharpening", "unit": "service_event", "category": "lawn_care_service_event", "initial_stock": 0, "reorder_threshold": 0, "cost_per_unit": 1200},
	{"name": "Lawn Bags", "unit": "piece", "category": "lawn_care_supply", "initial_stock": 200, "reorder_threshold": 40, "cost_per_unit": 0.45},
]

LAWN_CARE_SERVICES: list[dict[str, Any]] = [
	{"name": "Lawn Mow (small <2000sqft)", "duration_minutes": 30, "price_cents": 4500, "category": "mowing", "hst_applicable": True},
	{"name": "Lawn Mow (medium 2000-5000sqft)", "duration_minutes": 45, "price_cents": 6500, "category": "mowing", "hst_applicable": True},
	{"name": "Lawn Mow (large 5000sqft+)", "duration_minutes": 75, "price_cents": 9500, "category": "mowing", "hst_applicable": True},
	{"name": "Edge & Trim", "duration_minutes": 30, "price_cents": 3500, "category": "maintenance", "hst_applicable": True},
	{"name": "Fertilize", "duration_minutes": 45, "price_cents": 7500, "category": "treatment", "hst_applicable": True},
	{"name": "Aeration", "duration_minutes": 60, "price_cents": 12500, "category": "treatment", "hst_applicable": True},
	{"name": "Leaf Cleanup", "duration_minutes": 90, "price_cents": 15000, "category": "cleanup", "hst_applicable": True},
	{"name": "Spring Cleanup", "duration_minutes": 120, "price_cents": 22000, "category": "cleanup", "hst_applicable": True},
	{"name": "Fall Cleanup", "duration_minutes": 120, "price_cents": 22000, "category": "cleanup", "hst_applicable": True},
]


def run_seed(tenant_id: str, db_session: Any) -> None:
	"""Seed lawn-care inventory, services, and vertical shop metadata."""
	shop_id = int(tenant_id)
	tenant_schema = _tenant_schema_name(tenant_id)
	_set_lawn_care_profile(shop_id, db_session)
	_seed_inventory(shop_id, tenant_schema, db_session)
	_seed_services(shop_id, tenant_schema, db_session)


def _set_lawn_care_profile(shop_id: int, db_session: Any) -> None:
	db_session.execute(
		text(
			"""
			UPDATE platform.shops
			SET
				vertical = 'lawn_care',
				active_modules = CASE
					WHEN active_modules::jsonb ? 'lawn_care' THEN active_modules
					ELSE (active_modules::jsonb || '["lawn_care"]'::jsonb)::json
				END
			WHERE id = :shop_id
			"""
		),
		{"shop_id": shop_id},
	)


def _seed_inventory(shop_id: int, tenant_schema: str, db_session: Any) -> None:
	for item in LAWN_CARE_INVENTORY_ITEMS:
		db_session.execute(
			text(
				f"""
				INSERT INTO {tenant_schema}.inventory_items (
					shop_id, name, sku, category, unit, current_stock,
					reorder_threshold, cost_per_unit, supplier, is_active,
					created_at, updated_at
				)
				SELECT
					:shop_id, :name, :sku, :category, :unit, :current_stock,
					:reorder_threshold, :cost_per_unit, :supplier, TRUE,
					NOW(), NOW()
				WHERE NOT EXISTS (
					SELECT 1 FROM {tenant_schema}.inventory_items
					WHERE shop_id = :shop_id AND LOWER(name) = LOWER(:name)
				)
				"""
			),
			{
				"shop_id": shop_id,
				"name": item["name"],
				"sku": f"LWN-{item['name'].upper().replace(' ', '-').replace('&', 'AND')}",
				"category": item["category"],
				"unit": item["unit"],
				"current_stock": item["initial_stock"],
				"reorder_threshold": item["reorder_threshold"],
				"cost_per_unit": item["cost_per_unit"],
				"supplier": "Default lawn care supplier",
			},
		)


def _seed_services(shop_id: int, tenant_schema: str, db_session: Any) -> None:
	for service in LAWN_CARE_SERVICES:
		db_session.execute(
			text(
				f"""
				INSERT INTO {tenant_schema}.shop_services (
					shop_id, name, description, duration_minutes, price_cents,
					hst_applicable, category, staff_ids, supplies_used, is_active, created_at
				)
				SELECT
					:shop_id, :name, :description, :duration_minutes, :price_cents,
					:hst_applicable, :category, '{{}}'::integer[], '[]'::jsonb, TRUE, NOW()
				WHERE NOT EXISTS (
					SELECT 1 FROM {tenant_schema}.shop_services
					WHERE shop_id = :shop_id AND LOWER(name) = LOWER(:name)
				)
				"""
			),
			{
				"shop_id": shop_id,
				"name": service["name"],
				"description": service.get("description"),
				"duration_minutes": service["duration_minutes"],
				"price_cents": service["price_cents"],
				"hst_applicable": service["hst_applicable"],
				"category": service["category"],
			},
		)


def _tenant_schema_name(tenant_id: str) -> str:
	schema_name = f"tenant_{int(tenant_id)}"
	if not _TENANT_SCHEMA_RE.match(schema_name):
		raise ValueError(f"Invalid tenant schema name: {schema_name}")
	return schema_name