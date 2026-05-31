"""Lawn-care-specific agent skills for recurring jobs and weather holds."""

from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date as date_type, datetime, time, timedelta
from typing import Any

from sqlalchemy import text

from database import SessionLocal


def get_agent_skills() -> list[dict]:
	"""Return lawn-care-specific tool metadata for the module registry."""
	return [
		{
			"name": "schedule_recurring_job",
			"description": "Create the first lawn-care appointment and store its recurring interval.",
			"callable": schedule_recurring_job,
		},
		{
			"name": "check_weather_and_hold",
			"description": "Check rain probability and place lawn appointments on weather hold when needed.",
			"callable": check_weather_and_hold,
		},
		{
			"name": "get_jobs_this_week",
			"description": "Return this week's lawn-care appointments grouped by day.",
			"callable": get_jobs_this_week,
		},
	]


def schedule_recurring_job(customer_id: int, service_id: int, interval: str, start_date: str) -> dict[str, Any]:
	"""Create the first appointment for a recurring lawn-care job."""
	normalized_interval = _normalize_interval(interval)
	scheduled_start = _parse_start_date(start_date)
	with SessionLocal() as session:
		customer = session.execute(
			text(
				"""
				SELECT id, shop_id, name, phone, email
				FROM shop_customers
				WHERE id = :customer_id
				"""
			),
			{"customer_id": customer_id},
		).mappings().first()
		if not customer:
			raise ValueError(f"Customer {customer_id} not found")

		service = session.execute(
			text(
				"""
				SELECT id, shop_id, name, duration_minutes, price_cents
				FROM shop_services
				WHERE id = :service_id AND shop_id = :shop_id
				"""
			),
			{"service_id": service_id, "shop_id": customer["shop_id"]},
		).mappings().first()
		if not service:
			raise ValueError(f"Service {service_id} not found for customer shop")

		scheduled_end = scheduled_start + timedelta(minutes=int(service.get("duration_minutes") or 60))
		row = session.execute(
			text(
				"""
				INSERT INTO appointments (
					shop_id, customer_id, service_id, customer_name, customer_phone,
					customer_email, scheduled_start, scheduled_end, status,
					service_cost, recurring_interval, weather_hold, created_at, updated_at
				) VALUES (
					:shop_id, :customer_id, :service_id, :customer_name, :customer_phone,
					:customer_email, :scheduled_start, :scheduled_end, 'scheduled',
					:service_cost, :recurring_interval, FALSE, NOW(), NOW()
				)
				RETURNING id
				"""
			),
			{
				"shop_id": customer["shop_id"],
				"customer_id": customer_id,
				"service_id": service_id,
				"customer_name": customer["name"],
				"customer_phone": customer.get("phone"),
				"customer_email": customer.get("email"),
				"scheduled_start": scheduled_start,
				"scheduled_end": scheduled_end,
				"service_cost": float(service.get("price_cents") or 0) / 100,
				"recurring_interval": normalized_interval,
			},
		).fetchone()
		session.commit()
	return {
		"appointment_id": int(row[0]),
		"customer_id": customer_id,
		"service_id": service_id,
		"recurring_interval": normalized_interval,
		"scheduled_start": scheduled_start.isoformat(),
	}


def check_weather_and_hold(tenant_id: int, date: str) -> dict[str, Any]:
	"""Check rain probability and set weather_hold=true for a tenant's appointments."""
	target_date = _parse_date(date)
	shop_id = int(tenant_id)
	with SessionLocal() as session:
		shop = session.execute(
			text(
				"""
				SELECT id, name, zip_code, latitude, longitude
				FROM platform.shops
				WHERE id = :shop_id
				"""
			),
			{"shop_id": shop_id},
		).mappings().first()
		if not shop:
			raise ValueError(f"Shop {shop_id} not found")

		coordinates = _resolve_coordinates(shop)
		weather = _fetch_rain_probability(coordinates[0], coordinates[1], target_date)
		rain_probability = weather["precipitation_probability_max"]
		if rain_probability <= 60:
			return {
				"shop_id": shop_id,
				"date": target_date.isoformat(),
				"rain_probability": rain_probability,
				"held_appointments": 0,
			}

		held_rows = session.execute(
			text(
				"""
				UPDATE appointments
				SET weather_hold = TRUE, updated_at = NOW()
				WHERE shop_id = :shop_id
				  AND scheduled_start >= :day_start
				  AND scheduled_start < :day_end
				  AND status IN ('scheduled', 'confirmed')
				RETURNING id
				"""
			),
			{
				"shop_id": shop_id,
				"day_start": datetime.combine(target_date, time.min),
				"day_end": datetime.combine(target_date + timedelta(days=1), time.min),
			},
		).fetchall()
		session.commit()

	notification_results = [_notify_weather_hold(int(row[0]), rain_probability) for row in held_rows]
	return {
		"shop_id": shop_id,
		"date": target_date.isoformat(),
		"rain_probability": rain_probability,
		"held_appointments": len(held_rows),
		"notifications": notification_results,
	}


def get_jobs_this_week(tenant_id: int) -> dict[str, list[dict[str, Any]]]:
	"""Return this week's lawn appointments grouped by day."""
	today = datetime.utcnow().date()
	week_start = today - timedelta(days=today.weekday())
	week_end = week_start + timedelta(days=7)
	with SessionLocal() as session:
		rows = session.execute(
			text(
				"""
				SELECT
					a.id, a.customer_name, a.scheduled_start, a.scheduled_end,
					a.property_size_sqft, a.grass_type, a.recurring_interval,
					a.weather_hold, ss.name AS service_name
				FROM appointments a
				LEFT JOIN shop_services ss ON ss.id = a.service_id
				WHERE a.shop_id = :shop_id
				  AND a.scheduled_start >= :week_start
				  AND a.scheduled_start < :week_end
				ORDER BY a.scheduled_start
				"""
			),
			{
				"shop_id": int(tenant_id),
				"week_start": datetime.combine(week_start, time.min),
				"week_end": datetime.combine(week_end, time.min),
			},
		).mappings().fetchall()

	grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for row in rows:
		day_key = row["scheduled_start"].date().isoformat()
		grouped[day_key].append(
			{
				"appointment_id": int(row["id"]),
				"customer_name": row.get("customer_name"),
				"service_name": row.get("service_name"),
				"scheduled_start": row["scheduled_start"].isoformat() if row.get("scheduled_start") else None,
				"scheduled_end": row["scheduled_end"].isoformat() if row.get("scheduled_end") else None,
				"property_size_sqft": row.get("property_size_sqft"),
				"grass_type": row.get("grass_type"),
				"recurring_interval": row.get("recurring_interval"),
				"weather_hold": bool(row.get("weather_hold")),
			}
		)
	return dict(grouped)


def _normalize_interval(interval: str) -> str:
	value = str(interval or "").strip().lower()
	allowed = {"weekly", "biweekly", "monthly", "one-time"}
	if value not in allowed:
		raise ValueError(f"recurring interval must be one of: {', '.join(sorted(allowed))}")
	return value


def _parse_start_date(value: str) -> datetime:
	parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
	if parsed.tzinfo is not None:
		parsed = parsed.replace(tzinfo=None)
	return parsed


def _parse_date(value: str) -> date_type:
	return datetime.fromisoformat(str(value)).date()


def _resolve_coordinates(shop: dict[str, Any]) -> tuple[float, float]:
	if shop.get("latitude") is not None and shop.get("longitude") is not None:
		return float(shop["latitude"]), float(shop["longitude"])
	postal_code = str(shop.get("zip_code") or "").strip()
	if not postal_code:
		raise ValueError("Shop postal code is required for weather lookup")
	query = urllib.parse.urlencode({"name": postal_code, "count": 1, "format": "json"})
	url = f"https://geocoding-api.open-meteo.com/v1/search?{query}"
	with urllib.request.urlopen(url, timeout=10) as response:
		payload = json.loads(response.read().decode("utf-8"))
	results = payload.get("results") or []
	if not results:
		raise ValueError(f"Open-Meteo could not geocode postal code {postal_code!r}")
	return float(results[0]["latitude"]), float(results[0]["longitude"])


def _fetch_rain_probability(latitude: float, longitude: float, target_date: date_type) -> dict[str, Any]:
	query = urllib.parse.urlencode(
		{
			"latitude": latitude,
			"longitude": longitude,
			"daily": "precipitation_probability_max",
			"start_date": target_date.isoformat(),
			"end_date": target_date.isoformat(),
			"timezone": "auto",
		}
	)
	url = f"https://api.open-meteo.com/v1/forecast?{query}"
	with urllib.request.urlopen(url, timeout=10) as response:
		payload = json.loads(response.read().decode("utf-8"))
	probabilities = payload.get("daily", {}).get("precipitation_probability_max") or []
	return {"precipitation_probability_max": int(probabilities[0] if probabilities else 0)}


def _notify_weather_hold(appointment_id: int, rain_probability: int) -> dict[str, Any]:
	from notification_dispatcher import send_appointment_notification

	return asyncio.run(
		send_appointment_notification(
			appointment_id=appointment_id,
			template_key="reminder_24h",
			extra_vars={
				"service_name": "weather hold for your lawn care appointment",
				"scheduled_time": f"on hold due to {rain_probability}% rain probability",
			},
		)
	)