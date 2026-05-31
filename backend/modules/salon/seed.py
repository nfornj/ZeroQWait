"""Seed salon-specific services, inventory defaults, and operating configuration."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

_TENANT_SCHEMA_RE = re.compile(r"^tenant_\d+$")

SALON_INVENTORY_ITEMS: list[dict[str, Any]] = [
	{"name": "Salon Shampoo", "unit": "ml", "category": "salon_supply", "initial_stock": 8000, "reorder_threshold": 1500, "cost_per_unit": 0.02},
	{"name": "Salon Conditioner", "unit": "ml", "category": "salon_supply", "initial_stock": 8000, "reorder_threshold": 1500, "cost_per_unit": 0.02},
	{"name": "Styling Product", "unit": "ml", "category": "salon_supply", "initial_stock": 4000, "reorder_threshold": 800, "cost_per_unit": 0.04},
	{"name": "Heat Protectant", "unit": "ml", "category": "salon_supply", "initial_stock": 2500, "reorder_threshold": 500, "cost_per_unit": 0.05},
	{"name": "Hair Color", "unit": "g", "category": "salon_supply", "initial_stock": 5000, "reorder_threshold": 800, "cost_per_unit": 0.09},
	{"name": "Developer", "unit": "ml", "category": "salon_supply", "initial_stock": 6000, "reorder_threshold": 1000, "cost_per_unit": 0.03},
	{"name": "Lightener", "unit": "g", "category": "salon_supply", "initial_stock": 5000, "reorder_threshold": 800, "cost_per_unit": 0.07},
	{"name": "Toner", "unit": "ml", "category": "salon_supply", "initial_stock": 2500, "reorder_threshold": 500, "cost_per_unit": 0.06},
	{"name": "Keratin Solution", "unit": "ml", "category": "salon_supply", "initial_stock": 3000, "reorder_threshold": 500, "cost_per_unit": 0.12},
	{"name": "Deep Conditioning Mask", "unit": "ml", "category": "salon_supply", "initial_stock": 2500, "reorder_threshold": 400, "cost_per_unit": 0.07},
	{"name": "Scalp Treatment Serum", "unit": "ml", "category": "salon_supply", "initial_stock": 1500, "reorder_threshold": 250, "cost_per_unit": 0.11},
	{"name": "Perm Solution", "unit": "ml", "category": "salon_supply", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.08},
	{"name": "Relaxer Cream", "unit": "ml", "category": "salon_supply", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.08},
	{"name": "Acrylic Powder", "unit": "g", "category": "salon_supply", "initial_stock": 3000, "reorder_threshold": 500, "cost_per_unit": 0.05},
	{"name": "Gel Polish", "unit": "ml", "category": "salon_supply", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.05},
	{"name": "Nail Polish", "unit": "ml", "category": "salon_supply", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.03},
	{"name": "Dip Powder", "unit": "g", "category": "salon_supply", "initial_stock": 2000, "reorder_threshold": 400, "cost_per_unit": 0.05},
	{"name": "Nail Glue", "unit": "ml", "category": "salon_supply", "initial_stock": 1000, "reorder_threshold": 200, "cost_per_unit": 0.06},
	{"name": "Pedicure Soak", "unit": "ml", "category": "salon_supply", "initial_stock": 2000, "reorder_threshold": 300, "cost_per_unit": 0.02},
	{"name": "Base Coat", "unit": "ml", "category": "salon_supply", "initial_stock": 1000, "reorder_threshold": 200, "cost_per_unit": 0.03},
	{"name": "Top Coat", "unit": "ml", "category": "salon_supply", "initial_stock": 1000, "reorder_threshold": 200, "cost_per_unit": 0.03},
	{"name": "Salon Wax", "unit": "g", "category": "salon_supply", "initial_stock": 2500, "reorder_threshold": 400, "cost_per_unit": 0.04},
	{"name": "Wax Strips", "unit": "piece", "category": "salon_supply", "initial_stock": 1000, "reorder_threshold": 200, "cost_per_unit": 0.02},
]

SALON_SERVICES: list[dict[str, Any]] = [
	{"name": "Haircut", "duration_minutes": 45, "price_cents": 5500, "category": "hair", "hst_applicable": False},
	{"name": "Blowout", "duration_minutes": 45, "price_cents": 4500, "category": "style", "hst_applicable": False},
	{"name": "Keratin Treatment", "duration_minutes": 180, "price_cents": 20000, "category": "treatment", "hst_applicable": True},
	{"name": "Colour & Highlights", "duration_minutes": 150, "price_cents": 14000, "category": "colour", "hst_applicable": True},
	{"name": "Waxing - Eyebrow", "duration_minutes": 15, "price_cents": 1800, "category": "waxing", "hst_applicable": True},
	{"name": "Waxing - Lip", "duration_minutes": 15, "price_cents": 1500, "category": "waxing", "hst_applicable": True},
	{"name": "Waxing - Full Leg", "duration_minutes": 60, "price_cents": 6500, "category": "waxing", "hst_applicable": True},
	{"name": "Mani", "duration_minutes": 35, "price_cents": 3000, "category": "nails", "hst_applicable": True},
	{"name": "Pedi", "duration_minutes": 50, "price_cents": 4500, "category": "nails", "hst_applicable": True},
]


def run_seed(tenant_id: str, db_session: Any) -> None:
	"""Seed salon inventory, services, and vertical shop metadata."""
	shop_id = int(tenant_id)
	tenant_schema = _tenant_schema_name(tenant_id)
	_set_salon_profile(shop_id, db_session)
	_seed_inventory(shop_id, tenant_schema, db_session)
	_seed_services(shop_id, tenant_schema, db_session)


def _set_salon_profile(shop_id: int, db_session: Any) -> None:
	db_session.execute(
		text(
			"""
			UPDATE platform.shops
			SET
				vertical = 'salon',
				active_modules = CASE
					WHEN active_modules::jsonb ? 'salon' THEN active_modules
					ELSE (active_modules::jsonb || '["salon"]'::jsonb)::json
				END
			WHERE id = :shop_id
			"""
		),
		{"shop_id": shop_id},
	)


def _seed_inventory(shop_id: int, tenant_schema: str, db_session: Any) -> None:
	for item in SALON_INVENTORY_ITEMS:
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
				"sku": f"SAL-{item['name'].upper().replace(' ', '-')}",
				"category": item["category"],
				"unit": item["unit"],
				"current_stock": item["initial_stock"],
				"reorder_threshold": item["reorder_threshold"],
				"cost_per_unit": item["cost_per_unit"],
				"supplier": "Default salon supplier",
			},
		)


def _seed_services(shop_id: int, tenant_schema: str, db_session: Any) -> None:
	for service in SALON_SERVICES:
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