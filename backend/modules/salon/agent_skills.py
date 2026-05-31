"""Salon-specific agent skills for client treatments and salon supplies."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from agents.tools import inventory_tools
from database import SessionLocal
from .seed import SALON_INVENTORY_ITEMS

_SALON_SUPPLY_NAMES = {str(item["name"]).lower() for item in SALON_INVENTORY_ITEMS}


def get_agent_skills() -> list[dict]:
	"""Return salon-specific tool metadata for the module registry."""
	return [
		{
			"name": "get_client_treatment_history",
			"description": "Read salon client skin type, sensitivities, and last treatment product.",
			"callable": get_client_treatment_history,
		},
		{
			"name": "log_chemical_usage",
			"description": "Record salon chemical product usage for an appointment.",
			"callable": log_chemical_usage,
		},
		{
			"name": "get_low_stock_salon_supplies",
			"description": "Return low-stock salon supplies from existing inventory alerts.",
			"callable": get_low_stock_salon_supplies,
		},
	]


def get_client_treatment_history(client_id: int) -> dict[str, Any]:
	"""Read skin and treatment profile fields from shop_customers."""
	with SessionLocal() as session:
		row = session.execute(
			text(
				"""
				SELECT id, name, skin_type, sensitivities, last_treatment_product, last_visit, visit_count
				FROM shop_customers
				WHERE id = :client_id
				"""
			),
			{"client_id": client_id},
		).mappings().first()
	if not row:
		return {"client_id": client_id, "found": False}
	return {
		"client_id": int(row["id"]),
		"found": True,
		"name": row.get("name"),
		"skin_type": row.get("skin_type"),
		"sensitivities": row.get("sensitivities"),
		"last_treatment_product": row.get("last_treatment_product"),
		"last_visit": row.get("last_visit").isoformat() if row.get("last_visit") else None,
		"visit_count": int(row.get("visit_count") or 0),
	}


def log_chemical_usage(appointment_id: int, product_name: str, quantity_ml: float) -> dict[str, Any]:
	"""Log chemical product usage as an inventory movement for an appointment."""
	if quantity_ml <= 0:
		raise ValueError("quantity_ml must be greater than zero")
	with SessionLocal() as session:
		appointment = session.execute(
			text("SELECT id, shop_id FROM appointments WHERE id = :appointment_id"),
			{"appointment_id": appointment_id},
		).mappings().first()
		if not appointment:
			raise ValueError(f"Appointment {appointment_id} not found")

		item = session.execute(
			text(
				"""
				SELECT id, cost_per_unit
				FROM inventory_items
				WHERE shop_id = :shop_id
				  AND LOWER(name) = LOWER(:product_name)
				  AND is_active = TRUE
				"""
			),
			{"shop_id": appointment["shop_id"], "product_name": product_name},
		).mappings().first()
		if not item:
			raise ValueError(f"Salon product {product_name!r} not found")

		stock_after = session.execute(
			text(
				"""
				UPDATE inventory_items
				SET current_stock = current_stock - :quantity_ml,
					updated_at = NOW()
				WHERE id = :item_id AND shop_id = :shop_id
				RETURNING current_stock
				"""
			),
			{
				"quantity_ml": quantity_ml,
				"item_id": item["id"],
				"shop_id": appointment["shop_id"],
			},
		).scalar_one()
		session.execute(
			text(
				"""
				INSERT INTO inventory_movements (
					shop_id, item_id, movement_type, quantity, stock_after,
					unit_cost, notes, appointment_id, created_at
				) VALUES (
					:shop_id, :item_id, 'usage', :quantity, :stock_after,
					:unit_cost, :notes, :appointment_id, NOW()
				)
				"""
			),
			{
				"shop_id": appointment["shop_id"],
				"item_id": item["id"],
				"quantity": -float(quantity_ml),
				"stock_after": stock_after,
				"unit_cost": item.get("cost_per_unit"),
				"notes": f"Salon chemical usage: {product_name}",
				"appointment_id": appointment_id,
			},
		)
		session.commit()
	return {
		"appointment_id": appointment_id,
		"product_name": product_name,
		"quantity_ml": float(quantity_ml),
		"stock_after": float(stock_after or 0),
	}


def get_low_stock_salon_supplies(shop_id: int) -> list[dict[str, Any]]:
	"""Wrap existing low-stock alerts and keep only salon supply items."""
	alerts = inventory_tools.get_low_stock_alerts(shop_id)
	return [alert for alert in alerts if str(alert.get("name", "")).lower() in _SALON_SUPPLY_NAMES]