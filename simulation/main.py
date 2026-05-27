#!/usr/bin/env python3
"""
ZeroQwait Live Shop Simulation
================================

Simulates a real barber shop with:
  👷 2 barber employees — clock in, serve customers, clock out after shift; random sick days
  👤 Continuous customer arrivals — join queue with random services; paused on holidays
  💳 Checkout + payment — cash / card / contactless logged after every service
  📅 Holidays — upcoming close days registered; customer arrivals paused on those days
  🏪 1 shop owner — asks the AI agent operational questions every minute

Output: Rich terminal dashboard  (docker compose logs -f simulation)
Watch UI at:  http://localhost:3000   (or https://zeroqwait.com)

Environment variables:
  BASE_URL                 HTTP base (default: http://backend:8000)
  SHOP_NAME                Demo shop name (default: ZeroQ Demo Cuts)
    SIM_OWNER_EMAIL          Existing owner email to log in as
    SIM_OWNER_PASSWORD       Existing owner password
    SIM_OWNER_DISPLAY_NAME   Owner display name for logs
    SIM_EMPLOYEE_SPECS       JSON list of employee actors for this shop
    SIM_SHOP_SLUG            Existing shop slug to match
    SIM_ALLOW_USER_CREATE    Create missing users if needed (default: false)
    SIM_ALLOW_SHOP_CREATE    Create missing shop if needed (default: false)
    SIM_LOG_ONLY             Disable the Rich dashboard and emit plain logs only
  CUSTOMER_ARRIVAL_MIN/MAX Seconds between customer arrivals (default: 20/45)
  EMPLOYEE_CALL_MIN/MAX    Seconds between employee call-next attempts (default: 25/55)
  OWNER_QUERY_MIN/MAX      Seconds between owner AI queries (default: 60/120)
  TIME_COMPRESSION         Seconds per simulated service-minute (default: 2)
  MAX_QUEUE_SIZE           Max simultaneous waiting customers (default: 10)
  SHIFT_DURATION_MINUTES   Simulated shift length in minutes before clock-out (default: 480 = 8h)
  SICK_DAY_CHANCE          0.0–1.0 probability each employee calls in sick (default: 0.15)
"""

import asyncio
import json
import logging
import os
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ─── Configuration ────────────────────────────────────────────────────────────

BASE_URL = os.getenv("BASE_URL", "http://backend:8000").rstrip("/")
SHOP_NAME = os.getenv("SHOP_NAME", "ZeroQ Demo Cuts")
SIM_OWNER_EMAIL = os.getenv("SIM_OWNER_EMAIL", "demo.owner@zeroqwait.demo")
SIM_OWNER_PASSWORD = os.getenv("SIM_OWNER_PASSWORD", "ZeroQDemo2025!")
SIM_OWNER_DISPLAY_NAME = os.getenv("SIM_OWNER_DISPLAY_NAME", "demo_owner")
SIM_EMPLOYEE_SPECS = os.getenv("SIM_EMPLOYEE_SPECS", "")
SIM_SHOP_SLUG = os.getenv("SIM_SHOP_SLUG", "").strip()
SIM_ALLOW_USER_CREATE = os.getenv("SIM_ALLOW_USER_CREATE", "false").strip().lower() in {"1", "true", "yes", "on"}
SIM_ALLOW_SHOP_CREATE = os.getenv("SIM_ALLOW_SHOP_CREATE", "false").strip().lower() in {"1", "true", "yes", "on"}
SIM_LOG_ONLY = os.getenv("SIM_LOG_ONLY", "false").strip().lower() in {"1", "true", "yes", "on"}

CUSTOMER_ARRIVAL_MIN = float(os.getenv("CUSTOMER_ARRIVAL_MIN", "20"))
CUSTOMER_ARRIVAL_MAX = float(os.getenv("CUSTOMER_ARRIVAL_MAX", "45"))
EMPLOYEE_CALL_MIN = float(os.getenv("EMPLOYEE_CALL_MIN", "25"))
EMPLOYEE_CALL_MAX = float(os.getenv("EMPLOYEE_CALL_MAX", "55"))
OWNER_QUERY_MIN = float(os.getenv("OWNER_QUERY_MIN", "60"))
OWNER_QUERY_MAX = float(os.getenv("OWNER_QUERY_MAX", "120"))
TIME_COMPRESSION = float(os.getenv("TIME_COMPRESSION", "2"))
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "10"))
# A full 8-hour shift takes SHIFT_DURATION_MINUTES * TIME_COMPRESSION seconds real-time.
# At TIME_COMPRESSION=2, 480 min * 2s = 960s (~16 min) before employee clocks out.
SHIFT_DURATION_MINUTES = float(os.getenv("SHIFT_DURATION_MINUTES", "480"))
SICK_DAY_CHANCE = float(os.getenv("SICK_DAY_CHANCE", "0.15"))

# Shop operating hours (real wall clock — all actor loops obey these)
SHOP_OPEN_HOUR  = int(os.getenv("SHOP_OPEN_HOUR",  "9"))   # 09:00
SHOP_CLOSE_HOUR = int(os.getenv("SHOP_CLOSE_HOUR", "0"))   # 0 = midnight

# Surge management — queue depth thresholds for auto walk-in control
SURGE_THRESHOLD = int(os.getenv("SURGE_THRESHOLD", "7"))   # waiting → block walk-ins
SURGE_RESUME    = int(os.getenv("SURGE_RESUME",    "4"))   # waiting → re-open walk-ins

# Walk-in vs pre-booked appointment split (0.0 = all appointments, 1.0 = all walk-ins)
WALKIN_RATIO    = float(os.getenv("WALKIN_RATIO", "0.6"))

# Customer cancellations — impatient customers abandon the queue
CANCEL_CHECK_INTERVAL = float(os.getenv("CANCEL_CHECK_INTERVAL", "45"))  # seconds between scans
CANCEL_CHANCE         = float(os.getenv("CANCEL_CHANCE",         "0.12")) # per waiting customer

# ─── Customer names ───────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Amir", "Jordan", "Priya", "Marcus", "Elena", "Kai", "Sofia", "Diego",
    "Fatima", "Liam", "Chloe", "Ravi", "Nadia", "Tyler", "Ingrid", "Omar",
    "Zoe", "Dante", "Mia", "Kwame", "Aria", "Felix", "Sonia", "Hugo",
    "Nina", "Elias", "Leila", "Tobias", "Yasmin", "Jason",
]

LAST_NAMES = [
    "Johnson", "Patel", "Garcia", "Kim", "Williams", "Okonkwo", "Chen",
    "Rodriguez", "Murphy", "Ali", "Brown", "Nakamura", "Smith", "Dubois",
    "Nguyen", "Hassan", "Fernandez", "Park", "Osei", "Lindqvist",
]

OWNER_QUERIES = [
    "How many customers are currently waiting in the queue?",
    "What's our revenue so far today?",
    "Give me a quick status summary of the shop right now.",
    "Which service is most popular today?",
    "Is the queue getting backed up? Should I call in more staff?",
    "How many customers have we served today?",
    "What's the average wait time for customers right now?",
    "Are all employees on duty and active?",
    "Show me today's analytics overview.",
    "What's the busiest hour we've had so far today?",
    "Any issues I should know about?",
    "How are we doing compared to yesterday?",
    "We're getting a surge in walk-ins — should I call in a third barber?",
    "A few customers just cancelled. What's our cancellation trend today?",
    "What's the current wait time for a new walk-in customer right now?",
    "Are walk-ins suspended due to surge? What's the queue depth?",
]

PAYMENT_METHODS = ["cash", "card", "contactless", "cash", "card"]  # weighted toward card/cash

PROFILE_CONFIGS = {
    "barber": {
        "keywords": ("barber", "fade", "beard", "cut"),
        "tip_range": (0.08, 0.22),
        "inventory": [
            {"key": "disinfectant", "name": "Clipper Disinfectant", "unit": "spray", "category": "sanitation", "initial_stock": 140, "reorder_threshold": 35, "cost_per_unit": 0.18},
            {"key": "neck_strip", "name": "Neck Strip", "unit": "piece", "category": "consumable", "initial_stock": 360, "reorder_threshold": 90, "cost_per_unit": 0.04},
            {"key": "styling_product", "name": "Styling Product", "unit": "portion", "category": "retail", "initial_stock": 120, "reorder_threshold": 24, "cost_per_unit": 0.35},
            {"key": "beard_oil", "name": "Beard Oil", "unit": "portion", "category": "retail", "initial_stock": 80, "reorder_threshold": 16, "cost_per_unit": 0.42},
        ],
    },
    "salon": {
        "keywords": ("salon", "hair", "blowout", "color"),
        "tip_range": (0.1, 0.24),
        "inventory": [
            {"key": "shampoo", "name": "Salon Shampoo", "unit": "portion", "category": "haircare", "initial_stock": 180, "reorder_threshold": 48, "cost_per_unit": 0.28},
            {"key": "conditioner", "name": "Salon Conditioner", "unit": "portion", "category": "haircare", "initial_stock": 170, "reorder_threshold": 42, "cost_per_unit": 0.3},
            {"key": "color_cream", "name": "Color Cream", "unit": "portion", "category": "color", "initial_stock": 110, "reorder_threshold": 24, "cost_per_unit": 0.75},
            {"key": "styling_serum", "name": "Styling Serum", "unit": "portion", "category": "styling", "initial_stock": 130, "reorder_threshold": 30, "cost_per_unit": 0.34},
        ],
    },
    "nail": {
        "keywords": ("nail", "manicure", "pedicure"),
        "tip_range": (0.1, 0.2),
        "inventory": [
            {"key": "base_coat", "name": "Base Coat", "unit": "portion", "category": "polish", "initial_stock": 120, "reorder_threshold": 26, "cost_per_unit": 0.18},
            {"key": "top_coat", "name": "Top Coat", "unit": "portion", "category": "polish", "initial_stock": 120, "reorder_threshold": 26, "cost_per_unit": 0.2},
            {"key": "polish_remover", "name": "Polish Remover", "unit": "portion", "category": "prep", "initial_stock": 150, "reorder_threshold": 40, "cost_per_unit": 0.12},
            {"key": "nail_file", "name": "Nail File", "unit": "piece", "category": "tooling", "initial_stock": 260, "reorder_threshold": 80, "cost_per_unit": 0.09},
        ],
    },
    "spa": {
        "keywords": ("spa", "massage", "facial", "wellness"),
        "tip_range": (0.12, 0.28),
        "inventory": [
            {"key": "massage_oil", "name": "Massage Oil", "unit": "portion", "category": "treatment", "initial_stock": 170, "reorder_threshold": 36, "cost_per_unit": 0.48},
            {"key": "facial_mask", "name": "Facial Mask", "unit": "portion", "category": "treatment", "initial_stock": 100, "reorder_threshold": 20, "cost_per_unit": 0.66},
            {"key": "aroma_oil", "name": "Aromatherapy Oil", "unit": "portion", "category": "treatment", "initial_stock": 110, "reorder_threshold": 20, "cost_per_unit": 0.31},
            {"key": "spa_towel", "name": "Fresh Towel Service", "unit": "piece", "category": "linen", "initial_stock": 240, "reorder_threshold": 60, "cost_per_unit": 0.14},
        ],
    },
    "dental": {
        "keywords": ("dent", "oral", "cleaning", "whitening"),
        "tip_range": (0.0, 0.06),
        "inventory": [
            {"key": "gloves", "name": "Disposable Gloves", "unit": "pair", "category": "ppe", "initial_stock": 520, "reorder_threshold": 160, "cost_per_unit": 0.22},
            {"key": "bib", "name": "Dental Bib", "unit": "piece", "category": "ppe", "initial_stock": 320, "reorder_threshold": 90, "cost_per_unit": 0.08},
            {"key": "fluoride_gel", "name": "Fluoride Gel", "unit": "portion", "category": "treatment", "initial_stock": 140, "reorder_threshold": 28, "cost_per_unit": 0.4},
            {"key": "sterilization_pouch", "name": "Sterilization Pouch", "unit": "piece", "category": "sanitation", "initial_stock": 260, "reorder_threshold": 70, "cost_per_unit": 0.16},
        ],
    },
    "generic": {
        "keywords": (),
        "tip_range": (0.08, 0.18),
        "inventory": [
            {"key": "service_supply", "name": "Service Supply Pack", "unit": "portion", "category": "consumable", "initial_stock": 180, "reorder_threshold": 40, "cost_per_unit": 0.25},
        ],
    },
}

# ─── Approval scenarios ────────────────────────────────────────────────────────
# Scenarios that ask the AI agent to perform actions requiring owner approval.
# Each entry is (message, force_reject).
#   force_reject=True  → simulation will always deny (used for destructive ops like closing the queue)
#   force_reject=False → left for the real human owner to decide in the Agent Inbox
#
# These are grouped into categories:
#   STAFFING  — add/remove employee, leave requests, shift changes
#   FINANCE   — invoices, payments, refunds, discounts
#   OPERATIONS — queue management, pricing
#
_APPROVAL_SCENARIOS: list[tuple[str, bool]] = [
    # ── Staffing: employee leave requests (most common real-world approval) ─────
    ("Marcus has asked for a day off this Friday — can you submit his leave request?", False),
    ("Elena texted me — she needs next Monday off for a medical appointment. Please log her leave request.", False),
    ("Marcus wants to take the whole weekend off this week. Please put in his leave request for Saturday and Sunday.", False),
    ("One of our barbers called in sick today — please log Elena's sick day leave for today.", False),
    ("Elena wants to take annual leave on the 15th and 16th. Can you submit that for approval?", False),
    ("Marcus asked for a personal day next Wednesday — please register his leave request.", False),

    # ── Staffing: adding / removing team members ───────────────────────────────
    ("Add a new part-time barber named Sam Rivera to the team. Email: sam.rivera@zeroqwait.demo", False),
    ("We want to hire Jordan Lee for weekend shifts. Email: jordan.lee@zeroqwait.demo", False),
    ("Add a new junior barber, Alex Chen, to the roster. He'll start next week.", False),

    # ── Staffing: shift assignments ────────────────────────────────────────────
    ("Assign Elena to the morning shift this Saturday, 9am to 2pm", False),
    ("Schedule Marcus for a double shift this Sunday — 8am to 8pm", False),
    ("Put Elena on the late shift next Friday, 2pm to 8pm", False),
    ("Can you assign Marcus a shift next Monday morning from 9am to 1pm?", False),

    # ── Finance: refunds ───────────────────────────────────────────────────────
    ("A customer says they were overcharged $10 on their last visit — please process a partial refund", False),
    ("Process a $35 refund for a Fade & Style — the customer was unhappy with the result", False),
    ("Customer Jake Williams wants a refund for a Kids Cut they paid for but didn't get. Can you refund them?", False),

    # ── Finance: invoices ──────────────────────────────────────────────────────
    ("Create an invoice for a Fade & Style service — the customer wants a receipt for expense tracking", False),
    ("Generate an invoice for a Full Service package just completed at chair 1", False),
    ("Customer is asking for a receipt. Please create an invoice for a Classic Haircut and Beard Trim combo.", False),

    # ── Finance: payments ──────────────────────────────────────────────────────
    ("Record a cash payment of $35 for a Classic Haircut just done at the front desk", False),
    ("A customer paid $45 in cash for the Full Service — please record that payment", False),
    ("Log a contactless payment of $18 for a Kids Cut", False),

    # ── Operations: queue management ──────────────────────────────────────────
    ("Close the queue for the next 2 hours — the team needs a lunch break", True),
    ("We're getting overwhelmed — please close the queue to new walk-ins for now", True),
    ("End of day is coming — please close the queue so we can wind down", True),
]

# Timing for approval scenario loop
# Default is 45–90 seconds so the owner sees frequent approvals during testing.
# Override with APPROVAL_SCENARIO_MIN / APPROVAL_SCENARIO_MAX env vars.
# In production you might use 300–600 (5–10 minutes).
_APPROVAL_SCENARIO_INTERVAL_MIN = float(os.getenv("APPROVAL_SCENARIO_MIN", "45"))   # 45 s
_APPROVAL_SCENARIO_INTERVAL_MAX = float(os.getenv("APPROVAL_SCENARIO_MAX", "90"))   # 90 s

# Auto-approve timeout: if the real owner has not responded within this many seconds,
# the simulation steps in as a safety net. Default = 2 hours.
_APPROVAL_TIMEOUT_SECS = float(os.getenv("APPROVAL_TIMEOUT_SECS", "7200"))  # 2 h

# ─── State ────────────────────────────────────────────────────────────────────


@dataclass
class Actor:
    display_name: str
    email: str
    password: str
    role: str
    username: Optional[str] = None
    token: Optional[str] = None
    user_id: Optional[int] = None
    on_sick_day: bool = False
    clocked_in: bool = False
    svc_time_min: float = 20.0  # simulated minutes per service (lower bound)
    svc_time_max: float = 30.0  # simulated minutes per service (upper bound)


@dataclass
class SimState:
    shop_id: Optional[int] = None
    shop_name: Optional[str] = None
    operating_timezone: str = "UTC"
    operating_days: list[int] = field(default_factory=lambda: list(range(7)))
    open_hour: int = SHOP_OPEN_HOUR
    open_minute: int = 0
    close_hour: int = SHOP_CLOSE_HOUR
    close_minute: int = 0
    queue_id: Optional[int] = None
    services: list = field(default_factory=list)
    queue_items: list = field(default_factory=list)
    events: list = field(default_factory=list)
    shop_closed_today: bool = False  # True if today is a registered close day
    walkins_open: bool = True        # False during a queue surge
    in_surge: bool = False           # True when waiting >= SURGE_THRESHOLD
    business_profile: str = "generic"
    staff_employee_ids: list[int] = field(default_factory=list)
    stats: dict = field(default_factory=lambda: {
        "appointments_booked": 0,
        "customers_served": 0,
        "customers_waiting": 0,
        "customers_today": 0,
        "cancellations_today": 0,
        "revenue_today": 0.0,
        "payments_processed": 0,
        "owner_queries": 0,
        "approvals_pending": 0,
        "approvals_resolved": 0,
        "start": datetime.now(),
    })
    running: bool = True

    def log(self, msg: str, style: str = "white") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.events.append((ts, msg, style))
        if len(self.events) > 60:
            self.events.pop(0)
        # Strip Rich markup tags and print to stdout so docker compose logs captures every event
        plain = re.sub(r"\[/?[^\]]+\]", "", msg)
        print(f"[{ts}] {plain}", flush=True)


STATE = SimState()


def _infer_business_profile() -> str:
    profile_text = " ".join(
        filter(
            None,
            [STATE.shop_name or "", *(str(service.get("name") or "") for service in STATE.services)],
        )
    ).lower()
    for profile, config in PROFILE_CONFIGS.items():
        if profile == "generic":
            continue
        if any(keyword in profile_text for keyword in config["keywords"]):
            return profile
    return "generic"


def _service_duration_minutes(service: Optional[dict]) -> int:
    if not service:
        return 30
    return int(service.get("duration_minutes") or 30)


def _service_price(service: Optional[dict]) -> float:
    if not service:
        return 0.0
    if service.get("cost") is not None:
        return float(service.get("cost") or 0.0)
    return round(float(service.get("price_cents") or 0) / 100.0, 2)


def _service_price_cents(service: Optional[dict]) -> int:
    if not service:
        return 0
    if service.get("price_cents") is not None:
        return int(service.get("price_cents") or 0)
    return int(round(_service_price(service) * 100))


def _service_lookup(service_id: Optional[int]) -> Optional[dict]:
    if service_id is None:
        return None
    return next((service for service in STATE.services if service.get("id") == service_id), None)


def _tip_amount(service_cost: float) -> float:
    low, high = PROFILE_CONFIGS.get(STATE.business_profile, PROFILE_CONFIGS["generic"])["tip_range"]
    if service_cost <= 0 or high <= 0:
        return 0.0
    return round(service_cost * random.uniform(low, high), 2)


def _appointment_delay_seconds(service: Optional[dict]) -> float:
    duration = _service_duration_minutes(service)
    base = max(45.0, duration * TIME_COMPRESSION * 0.9)
    ceiling = max(base + 45.0, duration * TIME_COMPRESSION * 3.2)
    return random.uniform(base, ceiling)


def _service_supplies_for_profile(profile: str, service: dict) -> list[tuple[str, float]]:
    name = str(service.get("name") or "").lower()
    if profile == "barber":
        supplies = [("disinfectant", 0.08), ("neck_strip", 1.0)]
        if "beard" in name:
            supplies.append(("beard_oil", 0.04))
        if any(keyword in name for keyword in ("fade", "style", "full")):
            supplies.append(("styling_product", 0.06))
        return supplies
    if profile == "salon":
        supplies = [("shampoo", 0.12), ("conditioner", 0.08)]
        if any(keyword in name for keyword in ("color", "highlight", "balayage")):
            supplies.append(("color_cream", 0.18))
        if any(keyword in name for keyword in ("style", "blow", "finish")):
            supplies.append(("styling_serum", 0.05))
        return supplies
    if profile == "nail":
        supplies = [("nail_file", 0.15), ("top_coat", 0.03)]
        if any(keyword in name for keyword in ("manicure", "pedicure", "gel")):
            supplies.append(("base_coat", 0.03))
            supplies.append(("polish_remover", 0.05))
        return supplies
    if profile == "spa":
        supplies = [("spa_towel", 1.0)]
        if "massage" in name:
            supplies.append(("massage_oil", 0.15))
        if "facial" in name:
            supplies.append(("facial_mask", 0.08))
        if any(keyword in name for keyword in ("aroma", "wellness", "relax")):
            supplies.append(("aroma_oil", 0.03))
        return supplies
    if profile == "dental":
        supplies = [("gloves", 2.0), ("bib", 1.0), ("sterilization_pouch", 1.0)]
        if any(keyword in name for keyword in ("clean", "white", "exam", "fill")):
            supplies.append(("fluoride_gel", 0.05))
        return supplies
    return [("service_supply", 0.08)]


async def _owner_request(
    client: httpx.AsyncClient,
    owner: Actor,
    method: str,
    path: str,
    **kwargs: Any,
) -> dict:
    try:
        return await _request(client, method, path, token=owner.token, **kwargs)
    except APIError as exc:
        if exc.status == 401 and await login(client, owner):
            return await _request(client, method, path, token=owner.token, **kwargs)
        raise


async def _ensure_inventory_and_service_supplies(client: httpx.AsyncClient, owner: Actor) -> None:
    STATE.business_profile = _infer_business_profile()
    profile_config = PROFILE_CONFIGS.get(STATE.business_profile, PROFILE_CONFIGS["generic"])

    inventory_payload = await _owner_request(client, owner, "GET", f"/api/v1/inventory/shop/{STATE.shop_id}")
    existing_items = inventory_payload.get("items", [])
    inventory_by_name = {str(item.get("name") or "").lower(): item for item in existing_items}
    inventory_by_key: dict[str, dict] = {}

    for spec in profile_config["inventory"]:
        item = inventory_by_name.get(spec["name"].lower())
        if item is None:
            item = await _owner_request(
                client,
                owner,
                "POST",
                f"/api/v1/inventory/shop/{STATE.shop_id}",
                json={
                    "name": spec["name"],
                    "unit": spec["unit"],
                    "category": spec["category"],
                    "initial_stock": spec["initial_stock"],
                    "reorder_threshold": spec["reorder_threshold"],
                    "cost_per_unit": spec["cost_per_unit"],
                },
            )
        inventory_by_key[spec["key"]] = item

    owner_services = (
        await _owner_request(client, owner, "GET", f"/api/v1/services/shop/{STATE.shop_id}")
    ).get("services", [])
    for service in owner_services:
        current_supplies = service.get("supplies_used") or []
        if current_supplies:
            continue
        desired_supplies = []
        for item_key, quantity in _service_supplies_for_profile(STATE.business_profile, service):
            item = inventory_by_key.get(item_key)
            if item is None:
                continue
            desired_supplies.append({"item_id": item["id"], "quantity": quantity})
        if not desired_supplies:
            continue
        updated = await _owner_request(
            client,
            owner,
            "PATCH",
            f"/api/v1/services/shop/{STATE.shop_id}/{service['id']}",
            json={"supplies_used": desired_supplies},
        )
        service["supplies_used"] = updated.get("supplies_used") or desired_supplies

    if owner_services:
        STATE.services = owner_services
    STATE.log(
        f"📦 Inventory + supplies synced for {STATE.business_profile} profile",
        "cyan",
    )


async def _record_service_inventory_usage(
    client: httpx.AsyncClient,
    owner: Actor,
    *,
    service_id: Optional[int],
    service_name: str,
    appointment_id: Optional[int] = None,
) -> None:
    if service_id is None:
        return
    service = await _owner_request(client, owner, "GET", f"/api/v1/services/shop/{STATE.shop_id}/{service_id}")
    supplies = service.get("supplies_used") or []
    if not supplies:
        return

    for supply in supplies:
        await _owner_request(
            client,
            owner,
            "POST",
            f"/api/v1/inventory/shop/{STATE.shop_id}/{supply['item_id']}/usage",
            json={
                "quantity": float(supply.get("quantity") or 0.0),
                "notes": f"Simulation completion for {service_name}",
                "appointment_id": appointment_id,
            },
        )

    alerts = await _owner_request(client, owner, "GET", f"/api/v1/inventory/shop/{STATE.shop_id}/alerts")
    if alerts.get("count"):
        alert = alerts.get("alerts", [])[0]
        if alert:
            STATE.log(
                f"📉 Low stock: {alert.get('name')} at {alert.get('current_stock')} {alert.get('unit')}",
                "yellow",
            )


async def _process_sale(
    client: httpx.AsyncClient,
    owner: Actor,
    emp: Actor,
    *,
    service: Optional[dict],
    customer_name: str,
    queue_item_id: Optional[int] = None,
    appointment_id: Optional[int] = None,
) -> tuple[float, float, str]:
    service_name = str(service.get("name") if service else "Service")
    service_cost = _service_price(service)
    tip = _tip_amount(service_cost)
    payment_method = random.choice(PAYMENT_METHODS)

    session = await _owner_request(
        client,
        owner,
        "POST",
        f"/api/v1/pos/shop/{STATE.shop_id}/session",
        json={"customer_name": customer_name, "employee_id": emp.user_id},
    )
    session_id = session["session_id"]
    await _owner_request(
        client,
        owner,
        "POST",
        f"/api/v1/pos/shop/{STATE.shop_id}/session/line",
        json={
            "session_id": session_id,
            "service_id": service.get("id") if service else None,
            "description": service_name,
            "quantity": 1,
            "unit_price_cents": _service_price_cents(service),
        },
    )
    if tip > 0:
        await _owner_request(
            client,
            owner,
            "PATCH",
            f"/api/v1/pos/shop/{STATE.shop_id}/session/tip",
            json={"session_id": session_id, "tip_cents": int(round(tip * 100))},
        )
    await _owner_request(
        client,
        owner,
        "POST",
        f"/api/v1/pos/shop/{STATE.shop_id}/session/complete",
        json={"session_id": session_id, "payment_method": payment_method},
    )

    if queue_item_id is not None:
        await _request(client, "POST", f"/api/queues/items/{queue_item_id}/checkout")

    await _record_service_inventory_usage(
        client,
        owner,
        service_id=service.get("id") if service else None,
        service_name=service_name,
        appointment_id=appointment_id,
    )

    total = service_cost + tip
    STATE.stats["payments_processed"] += 1
    STATE.stats["revenue_today"] += total
    return total, tip, payment_method


async def _next_due_appointment(client: httpx.AsyncClient, emp: Actor) -> Optional[dict]:
    appointments = await _request(
        client,
        "GET",
        f"/api/appointments/shop/{STATE.shop_id}/upcoming",
        token=emp.token,
        params={"hours": 6},
    )
    now = datetime.utcnow()
    ready_by = now + timedelta(seconds=max(90.0, 35.0 * TIME_COMPRESSION))
    due: list[tuple[datetime, dict]] = []
    for appointment in appointments:
        status = str(appointment.get("status") or "").lower()
        if status not in {"scheduled", "confirmed", "checked_in", "in_progress"}:
            continue
        if appointment.get("employee_id") != emp.user_id:
            continue
        try:
            scheduled_start = datetime.fromisoformat(str(appointment.get("scheduled_start")).replace("Z", "+00:00").replace("+00:00", ""))
        except ValueError:
            continue
        if scheduled_start <= ready_by:
            due.append((scheduled_start, appointment))
    if not due:
        return None
    due.sort(key=lambda item: item[0])
    return due[0][1]


async def _process_appointment(client: httpx.AsyncClient, owner: Actor, emp: Actor, appointment: dict) -> None:
    appointment_id = int(appointment["id"])
    current_status = str(appointment.get("status") or "scheduled").lower()
    if current_status in {"scheduled", "confirmed"}:
        await _request(
            client,
            "PATCH",
            f"/api/appointments/{appointment_id}/status",
            token=emp.token,
            params={"shop_id": STATE.shop_id, "new_status": "checked_in"},
        )
        current_status = "checked_in"
    if current_status == "checked_in":
        await _request(
            client,
            "PATCH",
            f"/api/appointments/{appointment_id}/status",
            token=emp.token,
            params={"shop_id": STATE.shop_id, "new_status": "in_progress"},
        )

    service = _service_lookup(appointment.get("service_id")) or {
        "id": appointment.get("service_id"),
        "name": appointment.get("service_name") or (appointment.get("service") or {}).get("name") or "Appointment",
        "duration_minutes": appointment.get("duration_minutes") or 30,
        "cost": float(appointment.get("service_cost") or 0.0),
        "price_cents": int(round(float(appointment.get("service_cost") or 0.0) * 100)),
    }
    customer_name = str(appointment.get("customer_name") or "Appointment Customer")
    service_name = str(service.get("name") or "Appointment")
    STATE.log(
        f"📅 {emp.display_name} → appointment for {customer_name} [{service_name}]",
        "bright_blue",
    )

    await asyncio.sleep(min(_service_duration_minutes(service) * TIME_COMPRESSION, 120))

    await _request(
        client,
        "PATCH",
        f"/api/appointments/{appointment_id}/status",
        token=emp.token,
        params={"shop_id": STATE.shop_id, "new_status": "completed"},
    )

    total, tip, payment_method = await _process_sale(
        client,
        owner,
        emp,
        service=service,
        customer_name=customer_name,
        appointment_id=appointment_id,
    )
    STATE.log(
        f"💳 {customer_name} paid ${total:.2f} ({payment_method})"
        + (f" + ${tip:.2f} tip" if tip > 0 else ""),
        "bright_white",
    )
    STATE.log(
        f"✅ {emp.display_name} ✓ {customer_name} — {service_name} (${total:.2f}) [appointment]",
        "bright_green",
    )
    STATE.stats["customers_served"] += 1


def _load_employee_specs() -> list[Actor]:
    if not SIM_EMPLOYEE_SPECS.strip():
        return [
            Actor("Marcus", "marcus.barber@zeroqwait.demo", SIM_OWNER_PASSWORD, "employee",
                  svc_time_min=24.0, svc_time_max=26.0),
            Actor("Elena", "elena.barber@zeroqwait.demo", SIM_OWNER_PASSWORD, "employee",
                  svc_time_min=16.0, svc_time_max=18.0),
        ]

    try:
        raw_specs = json.loads(SIM_EMPLOYEE_SPECS)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid SIM_EMPLOYEE_SPECS JSON: {exc}") from exc

    employees: list[Actor] = []
    for index, spec in enumerate(raw_specs):
        if not isinstance(spec, dict):
            raise RuntimeError(f"Employee spec at index {index} must be an object")
        employees.append(
            Actor(
                display_name=spec.get("display_name") or spec.get("username") or f"employee_{index + 1}",
                email=spec["email"],
                password=spec.get("password", SIM_OWNER_PASSWORD),
                role=spec.get("role", "employee"),
                username=spec.get("username"),
                svc_time_min=float(spec.get("svc_time_min", 20.0)),
                svc_time_max=float(spec.get("svc_time_max", 30.0)),
            )
        )
    return employees

# ─── HTTP helpers ─────────────────────────────────────────────────────────────


class APIError(Exception):
    def __init__(self, status: int, body: str, method: str, path: str):
        self.status = status
        super().__init__(f"{method} {path} → {status}: {body[:200]}")


async def _request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    token: Optional[str] = None,
    **kwargs: Any,
) -> dict:
    headers: dict = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = await client.request(
        method,
        f"{BASE_URL}{path}",
        headers=headers,
        timeout=30,
        **kwargs,
    )
    if resp.status_code >= 400:
        raise APIError(resp.status_code, resp.text, method, path)
    ct = resp.headers.get("content-type", "")
    if "application/json" in ct:
        return resp.json()
    return {}


async def login(client: httpx.AsyncClient, actor: Actor) -> bool:
    try:
        data = await _request(
            client, "POST", "/api/auth/token",
            data={"username": actor.email, "password": actor.password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        actor.token = data["access_token"]
        me = await _request(client, "GET", "/api/users/me", token=actor.token)
        actor.user_id = me["id"]
        return True
    except Exception as exc:
        STATE.log(f"⚠️  Login failed for {actor.display_name}: {exc}", "yellow")
        return False


async def ensure_user(client: httpx.AsyncClient, actor: Actor) -> bool:
    """Create user if not exists, then login."""
    try:
        await _request(
            client, "POST", "/api/users",
            json={
                "email": actor.email,
                "username": actor.username or actor.display_name,
                "password": actor.password,
                "role": actor.role,
            },
        )
    except APIError as e:
        if e.status not in (400, 409, 422):
            STATE.log(f"⚠️  Could not create {actor.display_name}: {e}", "yellow")
    return await login(client, actor)


# ─── Setup ────────────────────────────────────────────────────────────────────


_SERVICES = [
    ("Classic Haircut",          30, 25.0),
    ("Beard Trim",               20, 15.0),
    ("Fade & Style",             45, 35.0),
    ("Full Service (Cut+Beard)", 60, 45.0),
    ("Kids Cut",                 20, 18.0),
]


async def setup(
    client: httpx.AsyncClient,
    owner: Actor,
    employees: list[Actor],
) -> bool:
    STATE.log("⚙️  Starting setup...", "bold yellow")

    owner_ready = await ensure_user(client, owner) if SIM_ALLOW_USER_CREATE else await login(client, owner)
    if not owner_ready:
        STATE.log("❌ Owner setup failed — aborting", "bold red")
        return False
    STATE.log(f"✅ Owner '{owner.display_name}' ready (id={owner.user_id})", "green")

    # Find existing shop (creation is opt-in)
    try:
        shops: list = await _request(client, "GET", "/api/shops/my-shops", token=owner.token)
        existing = None
        if SIM_SHOP_SLUG:
            existing = next((s for s in shops if s.get("slug") == SIM_SHOP_SLUG), None)
        if existing is None and SHOP_NAME:
            existing = next((s for s in shops if s.get("name") == SHOP_NAME), None)
        if existing is None and len(shops) == 1:
            existing = shops[0]
        if existing:
            STATE.shop_id = existing["id"]
            STATE.shop_name = existing.get("name", SHOP_NAME)
            STATE.log(f"🏪 Shop '{existing.get('name', SHOP_NAME)}' found (id={STATE.shop_id})", "cyan")
        else:
            if not SIM_ALLOW_SHOP_CREATE:
                available = ", ".join(s.get("name", "unnamed") for s in shops) or "none"
                STATE.log(
                    f"❌ Existing shop not found for owner {owner.email}. Wanted name='{SHOP_NAME}' slug='{SIM_SHOP_SLUG or '-'}'; available: {available}",
                    "bold red",
                )
                return False
            shop = await _request(
                client, "POST", "/api/shops/",
                token=owner.token,
                json={
                    "name": SHOP_NAME,
                    "shop_type": "barbershop",
                    "address": "123 Main Street",
                    "city": "Toronto",
                    "state": "ON",
                    "zip_code": "M5V 1A1",
                    "country": "Canada",
                    "phone": "+1-416-555-0100",
                    "description": "ZeroQwait demo barber shop — AI-powered operations",
                    "average_service_time": 30,
                },
            )
            STATE.shop_id = shop["id"]
            STATE.shop_name = shop.get("name", SHOP_NAME)
            STATE.log(f"🏪 Shop '{SHOP_NAME}' created (id={STATE.shop_id})", "bold green")
    except Exception as exc:
        STATE.log(f"❌ Shop setup failed: {exc}", "bold red")
        return False

    # Find or create services
    try:
        services: list = await _request(
            client, "GET", f"/api/shops/{STATE.shop_id}/services",
        )
        if not services:
            for name, dur, cost in _SERVICES:
                svc = await _request(
                    client, "POST", f"/api/shops/{STATE.shop_id}/services",
                    token=owner.token,
                    json={"name": name, "duration_minutes": dur, "cost": cost, "is_active": True},
                )
                services.append(svc)
            STATE.log(f"✂️  {len(services)} services created", "green")
        STATE.services = services
        STATE.log(f"✂️  Services: {', '.join(s['name'] for s in services)}", "cyan")
    except Exception as exc:
        STATE.log(f"⚠️  Service setup issue: {exc}", "yellow")

    try:
        await _ensure_inventory_and_service_supplies(client, owner)
    except Exception as exc:
        STATE.log(f"⚠️  Inventory sync issue: {exc}", "yellow")

    # Get queue
    try:
        queue = await _request(client, "GET", f"/api/queues/shop/{STATE.shop_id}/active")
        STATE.queue_id = queue["id"]
        STATE.log(f"🗂️  Queue '{queue['name']}' ready (id={STATE.queue_id})", "cyan")
    except Exception as exc:
        STATE.log(f"❌ Queue fetch failed: {exc}", "bold red")
        return False

    # Setup employees — sick-day roll + clock-in
    for emp in employees:
        # Try to add via shop employee endpoint (creates + links in one call)
        try:
            await _request(
                client, "POST", f"/api/shops/{STATE.shop_id}/employees",
                token=owner.token,
                json={
                    "email": emp.email,
                    "username": emp.username or emp.display_name,
                    "password": emp.password,
                    "role": "employee",
                },
            )
        except APIError:
            pass  # already exists is fine
        # Login the employee regardless
        if not await login(client, emp):
            STATE.log(f"⚠️  Barber '{emp.display_name}' login failed", "yellow")
            continue

        # If a previous test run deactivated the shop-employee link, restore it
        # so the simulator roster and active shifts stay in sync.
        if emp.user_id is not None:
            try:
                await _request(
                    client,
                    "PUT",
                    f"/api/shops/{STATE.shop_id}/employees/{emp.user_id}/reactivate",
                    token=owner.token,
                )
            except APIError as e:
                if e.status not in (404, 409):
                    STATE.log(f"⚠️  Reactivate failed for {emp.display_name}: {e}", "yellow")

        # Sick-day lottery
        if random.random() < SICK_DAY_CHANCE:
            emp.on_sick_day = True
            STATE.log(
                f"🤒 Barber '{emp.display_name}' called in sick today — only one barber on duty!",
                "bold red",
            )
            continue

        # Clock in
        try:
            await _request(
                client, "POST", f"/api/clock-in/{STATE.shop_id}",
                token=emp.token,
            )
            emp.clocked_in = True
            STATE.log(f"👷 Barber '{emp.display_name}' clocked in (id={emp.user_id})", "green")
        except APIError as e:
            if e.status == 400:
                emp.clocked_in = True  # already clocked in from a previous run
                STATE.log(f"👷 Barber '{emp.display_name}' already clocked in", "cyan")
            else:
                STATE.log(f"⚠️  Clock-in failed for {emp.display_name}: {e}", "yellow")

    # Register upcoming close days (bank holidays, etc.)
    await _register_upcoming_holidays(client, owner)

    # Check if today is a registered close day
    await _check_today_closed(client)

    if STATE.shop_closed_today:
        STATE.log("🔒 Today is a registered CLOSE DAY — no customers will arrive", "bold red")
    else:
        STATE.staff_employee_ids = [int(emp.user_id) for emp in employees if emp.clocked_in and emp.user_id is not None]
        STATE.log("🚀 Setup complete — simulation is LIVE!", "bold green")
        STATE.log(f"   👀 Watch at http://localhost:3000", "bold cyan")
    return True


# ─── Holiday helpers ──────────────────────────────────────────────────────────

# Well-known Canadian public holidays (month-day). Adjust for your locale.
_CANADIAN_HOLIDAYS: list[tuple[int, int, str]] = [
    (1,  1,  "New Year's Day"),
    (2,  17, "Family Day"),
    (4,  18, "Good Friday"),
    (5,  19, "Victoria Day"),
    (7,  1,  "Canada Day"),
    (8,  4,  "Civic Holiday"),
    (9,  1,  "Labour Day"),
    (10, 13, "Thanksgiving"),
    (11, 11, "Remembrance Day"),
    (12, 25, "Christmas Day"),
    (12, 26, "Boxing Day"),
]


async def _register_upcoming_holidays(client: httpx.AsyncClient, owner: Actor) -> None:
    """Register the next 3 upcoming public holidays as shop close days."""
    today = datetime.now().date()
    import datetime as dt_mod
    year = today.year
    registered = 0
    for month, day, reason in _CANADIAN_HOLIDAYS:
        try:
            holiday = dt_mod.date(year, month, day)
        except ValueError:
            continue
        if holiday < today:
            # Try next year
            try:
                holiday = dt_mod.date(year + 1, month, day)
            except ValueError:
                continue
        if (holiday - today).days > 180:
            continue  # too far out
        try:
            await _request(
                client, "POST", f"/api/shops/{STATE.shop_id}/close-days",
                token=owner.token,
                params={"date_str": str(holiday), "reason": reason},
            )
            STATE.log(f"📅 Registered close day: {holiday} — {reason}", "yellow")
            registered += 1
            if registered >= 3:
                break
        except Exception:
            pass  # already registered or error — non-fatal


async def _check_today_closed(client: httpx.AsyncClient) -> None:
    """Check if today is listed as a shop close day."""
    try:
        close_days: list = await _request(
            client, "GET", f"/api/shops/{STATE.shop_id}/close-days",
        )
        today_str = _shop_now().strftime("%Y-%m-%d")
        for cd in close_days:
            if str(cd.get("date", "")).startswith(today_str):
                STATE.shop_closed_today = True
                STATE.log(
                    f"🏖️  Shop is closed today ({cd.get('reason', 'holiday')}) — queue paused",
                    "bold red",
                )
                return
    except Exception:
        pass


# ─── Shop-hours helpers ───────────────────────────────────────────────────────

def _shop_tzinfo():
    try:
        return ZoneInfo(STATE.operating_timezone or "UTC")
    except (ZoneInfoNotFoundError, Exception):
        return timezone.utc


def _shop_now() -> datetime:
    return datetime.now(_shop_tzinfo())


def _parse_hour_minute(value: str, fallback_hour: int, fallback_minute: int = 0) -> tuple[int, int]:
    try:
        parts = str(value).split(":")
        return int(parts[0]), int(parts[1])
    except Exception:
        return fallback_hour, fallback_minute


async def _load_operating_hours(client: httpx.AsyncClient, owner: Actor) -> None:
    try:
        hours = await _owner_request(client, owner, "GET", f"/api/shops/{STATE.shop_id}/operating-hours")
    except Exception as exc:
        STATE.log(f"⚠️  Operating-hours fetch failed, using env defaults: {exc}", "yellow")
        return

    STATE.operating_timezone = str(hours.get("timezone") or STATE.operating_timezone or "UTC")
    days = hours.get("operating_days") or []
    if isinstance(days, list) and days:
        STATE.operating_days = [int(day) for day in days]
    STATE.open_hour, STATE.open_minute = _parse_hour_minute(
        str(hours.get("open_time") or f"{SHOP_OPEN_HOUR:02d}:00:00"),
        SHOP_OPEN_HOUR,
    )
    default_close_hour = 0 if SHOP_CLOSE_HOUR == 0 else SHOP_CLOSE_HOUR
    STATE.close_hour, STATE.close_minute = _parse_hour_minute(
        str(hours.get("close_time") or f"{default_close_hour:02d}:00:00"),
        default_close_hour,
    )
    STATE.log(
        f"🕒 Operating hours loaded: {STATE.open_hour:02d}:{STATE.open_minute:02d}–{STATE.close_hour:02d}:{STATE.close_minute:02d} {STATE.operating_timezone}",
        "cyan",
    )


def _is_operating_day(now: datetime) -> bool:
    return now.weekday() in (STATE.operating_days or list(range(7)))

def _shop_is_open() -> bool:
    """Return True if the shop is within operating hours in the shop timezone."""
    now = _shop_now()
    if not _is_operating_day(now):
        return False
    now_minutes = (now.hour * 60) + now.minute
    open_minutes = (STATE.open_hour * 60) + STATE.open_minute
    close_minutes = (STATE.close_hour * 60) + STATE.close_minute
    if close_minutes == 0:
        return now_minutes >= open_minutes
    return open_minutes <= now_minutes < close_minutes


def _next_open_datetime(now: datetime) -> datetime:
    for offset in range(0, 8):
        candidate_date = (now + timedelta(days=offset)).date()
        candidate = datetime(
            candidate_date.year,
            candidate_date.month,
            candidate_date.day,
            STATE.open_hour,
            STATE.open_minute,
            tzinfo=_shop_tzinfo(),
        )
        if candidate.weekday() not in (STATE.operating_days or list(range(7))):
            continue
        if offset == 0 and candidate <= now:
            continue
        return candidate
    return now + timedelta(hours=12)


def _seconds_until_open() -> float:
    """Seconds from now until the shop next opens. Returns 0.0 if already open."""
    if _shop_is_open():
        return 0.0
    now = _shop_now()
    next_open = _next_open_datetime(now)
    return max((next_open - now).total_seconds(), 0.0)


# ─── Actor: Customer ──────────────────────────────────────────────────────────


async def customer_loop(client: httpx.AsyncClient, owner: Actor) -> None:
    """Continuously spawn new customers joining the queue."""
    await asyncio.sleep(3)
    while STATE.running:
        # No new customer traffic outside shop hours or on registered close days.
        if STATE.shop_closed_today or not _shop_is_open():
            await asyncio.sleep(max(_seconds_until_open(), 30.0))
            continue

        active = [i for i in STATE.queue_items if i["status"] in ("waiting", "being_served")]
        if len(active) >= MAX_QUEUE_SIZE:
            await asyncio.sleep(8)
            continue

        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        service = random.choice(STATE.services) if STATE.services else None
        employee_id = random.choice(STATE.staff_employee_ids) if STATE.staff_employee_ids else None

        try:
            if not STATE.walkins_open or random.random() > WALKIN_RATIO:
                scheduled_start = datetime.utcnow() + timedelta(seconds=_appointment_delay_seconds(service))
                appointment = await _request(
                    client,
                    "POST",
                    f"/api/appointments/shop/{STATE.shop_id}/book",
                    json={
                        "customer_name": name,
                        "service_id": service["id"] if service else None,
                        "customer_phone": f"+1-416-555-{random.randint(1000, 9999)}",
                        "customer_email": f"{name.lower().replace(' ', '.')}@demo.zeroqwait.local",
                        "scheduled_start": scheduled_start.isoformat(),
                        "duration_minutes": _service_duration_minutes(service),
                        "employee_id": employee_id,
                        "notes": random.choice([None, None, "Booked online", "Returning client"]),
                    },
                )
                svc_name = service["name"] if service else "appointment"
                STATE.log(
                    f"📅 {name} booked {svc_name} at {scheduled_start.strftime('%H:%M:%S')}"
                    + (f" with employee #{appointment.get('employee_id')}" if appointment.get("employee_id") else ""),
                    "bright_blue",
                )
                STATE.stats["appointments_booked"] += 1
            else:
                item = await _request(
                    client, "POST", f"/api/queues/shop/{STATE.shop_id}/join",
                    json={
                        "customer_name": name,
                        "service_id": service["id"] if service else None,
                        "customer_phone": f"+1-416-555-{random.randint(1000, 9999)}",
                        "notes": random.choice([None, None, None, "First time here", "Referred by a friend"]),
                    },
                )
                pos = item.get("position", "?")
                svc_name = service["name"] if service else "walk-in"
                cost = f"${_service_price(service):.0f}" if service else ""
                STATE.log(
                    f"🚶 {name} joined queue — {svc_name} {cost}  (#{pos})",
                    "bright_cyan",
                )
            STATE.stats["customers_today"] += 1
        except APIError as e:
            if e.status == 429:
                STATE.log("⏸️  Rate limit hit — slowing arrivals", "dim yellow")
                await asyncio.sleep(30)
            else:
                STATE.log(f"⚠️  Join failed ({e.status}): {str(e)[:60]}", "dim yellow")
        except Exception as e:
            STATE.log(f"⚠️  Customer loop error: {type(e).__name__}: {str(e)[:80]}", "dim yellow")
            await asyncio.sleep(10)

        await _load_operating_hours(client, owner)

        delay = random.uniform(CUSTOMER_ARRIVAL_MIN, CUSTOMER_ARRIVAL_MAX)
        await asyncio.sleep(delay)


# ─── Actor: Employee ──────────────────────────────────────────────────────────


async def employee_loop(client: httpx.AsyncClient, owner: Actor, emp: Actor) -> None:
    """Employee shift: clock in → serve customers → checkout+pay → clock out."""
    await asyncio.sleep(6 + random.uniform(0, 5))

    if emp.on_sick_day:
        # Nothing to do today — the sick-day log was already written in setup
        return

    shift_seconds = SHIFT_DURATION_MINUTES * TIME_COMPRESSION
    shift_end = asyncio.get_event_loop().time() + shift_seconds

    while STATE.running:
        if STATE.shop_closed_today or not _shop_is_open():
            if emp.clocked_in:
                try:
                    await _request(client, "POST", "/api/clock-out", token=emp.token)
                except Exception:
                    pass
                emp.clocked_in = False
            await asyncio.sleep(max(_seconds_until_open(), 30.0))
            continue

        # Clock-out time reached
        if asyncio.get_event_loop().time() >= shift_end:
            if emp.clocked_in:
                try:
                    await _request(client, "POST", "/api/clock-out", token=emp.token)
                    emp.clocked_in = False
                    STATE.log(
                        f"🏁 Barber '{emp.display_name}' clocked out — shift complete",
                        "yellow",
                    )
                except Exception:
                    pass
            # Restart shift cycle (next simulated day)
            shift_end = asyncio.get_event_loop().time() + shift_seconds
            STATE.log(
                f"🌅 Barber '{emp.display_name}' starting next shift",
                "dim cyan",
            )
            try:
                await _request(
                    client, "POST", f"/api/clock-in/{STATE.shop_id}",
                    token=emp.token,
                )
                emp.clocked_in = True
            except APIError as e:
                if e.status == 400:
                    emp.clocked_in = True  # already clocked in
                else:
                    await asyncio.sleep(15)
                    continue

        if not emp.token:
            await asyncio.sleep(5)
            continue

        if not emp.clocked_in:
            try:
                await _request(
                    client, "POST", f"/api/clock-in/{STATE.shop_id}",
                    token=emp.token,
                )
                emp.clocked_in = True
            except APIError as e:
                if e.status != 400:
                    await asyncio.sleep(5)
                    continue
                emp.clocked_in = True

        # Jitter between employees so they don't call in sync
        delay = random.uniform(EMPLOYEE_CALL_MIN, EMPLOYEE_CALL_MAX)

        try:
            due_appointment = await _next_due_appointment(client, emp)
            if due_appointment is not None:
                await _process_appointment(client, owner, emp, due_appointment)
                await asyncio.sleep(delay)
                continue

            item = await _request(
                client, "POST", f"/api/queues/{STATE.queue_id}/call-next",
                token=emp.token,
                params={"employee_id": emp.user_id},
            )
            svc: dict = item.get("service") or {}
            svc_name = svc.get("name", "service")
            svc_dur = svc.get("duration_minutes", 30)
            svc_cost = float(svc.get("cost") or 0)
            cust_name = item.get("customer_name", "Customer")
            item_id = item["id"]

            STATE.log(
                f"✂️  {emp.display_name} → serving {cust_name}  [{svc_name}]",
                "bright_yellow",
            )

            # Serve customer (compressed duration)
            service_secs = min(svc_dur * TIME_COMPRESSION, 120)
            await asyncio.sleep(service_secs)

            # Mark complete
            await _request(
                client, "PATCH", f"/api/queues/items/{item_id}/status",
                token=emp.token,
                params={"new_status": "completed"},
            )

            try:
                total, tip, payment_method = await _process_sale(
                    client,
                    owner,
                    emp,
                    service=svc,
                    customer_name=cust_name,
                    queue_item_id=item_id,
                )
                STATE.log(
                    f"💳 {cust_name} paid ${total:.2f} ({payment_method})"
                    + (f" + ${tip:.2f} tip" if tip > 0.5 else ""),
                    "bright_white",
                )
            except APIError as exc:
                STATE.log(f"⚠️  Checkout flow failed for {cust_name}: {exc}", "dim yellow")
                total = svc_cost

            STATE.log(
                f"✅ {emp.display_name} ✓ {cust_name} — {svc_name} (${total:.2f})",
                "bright_green",
            )
            STATE.stats["customers_served"] += 1

        except APIError as e:
            if e.status in (400, 404):
                pass  # queue empty, totally normal
            elif e.status == 401:
                STATE.log(f"🔄 {emp.display_name} token expired — re-logging in", "yellow")
                await login(client, emp)
            else:
                STATE.log(f"⚠️  {emp.display_name}: {str(e)[:80]}", "dim yellow")
        except Exception as exc:
            STATE.log(f"⚠️  {emp.display_name} loop error: {type(exc).__name__}: {str(exc)[:80]}", "dim yellow")

        await asyncio.sleep(delay)


# ─── Actor: Surge Monitor ─────────────────────────────────────────────────────


async def surge_monitor_loop(client: httpx.AsyncClient, owner: Actor) -> None:
    """Watch queue depth; block walk-ins + notify owner via AI on surge."""
    await asyncio.sleep(30)
    while STATE.running:
        if not _shop_is_open() or STATE.shop_closed_today:
            await asyncio.sleep(30)
            continue

        waiting = len([i for i in STATE.queue_items if i["status"] == "waiting"])

        if waiting >= SURGE_THRESHOLD and not STATE.in_surge:
            STATE.in_surge = True
            STATE.walkins_open = False
            STATE.log(
                f"⚡ SURGE — {waiting} waiting! Walk-ins suspended automatically.",
                "bold red",
            )
            try:
                await _request(
                    client, "POST", "/api/v2/agent/chat",
                    token=owner.token,
                    json={
                        "message": (
                            f"ALERT: Queue surge — {waiting} customers waiting right now. "
                            "Walk-ins have been automatically suspended. "
                            "Should I call in a third barber?"
                        ),
                        "shop_id": STATE.shop_id,
                    },
                )
                STATE.log("📲 AI agent notified owner of surge", "bold yellow")
                STATE.stats["owner_queries"] += 1
            except Exception:
                pass

        elif waiting <= SURGE_RESUME and STATE.in_surge:
            STATE.in_surge = False
            STATE.walkins_open = True
            STATE.log(
                f"✅ Surge cleared — {waiting} waiting. Walk-ins re-opened.",
                "bold green",
            )
            try:
                await _request(
                    client, "POST", "/api/v2/agent/chat",
                    token=owner.token,
                    json={
                        "message": (
                            f"Surge resolved — only {waiting} customers waiting now. "
                            "Walk-ins have been re-opened automatically."
                        ),
                        "shop_id": STATE.shop_id,
                    },
                )
                STATE.stats["owner_queries"] += 1
            except Exception:
                pass

        await asyncio.sleep(10)


# ─── Actor: Cancellations ─────────────────────────────────────────────────────


async def cancellation_loop(client: httpx.AsyncClient, owner: Actor) -> None:
    """Impatient customers abandon the queue; rate doubles during a surge."""
    await asyncio.sleep(60)
    while STATE.running:
        if _shop_is_open() and not STATE.shop_closed_today:
            waiting = [i for i in STATE.queue_items if i["status"] == "waiting"]
            # Higher abandonment during surge (longer waits)
            effective_chance = CANCEL_CHANCE * (2.0 if STATE.in_surge else 1.0)
            for item in waiting:
                if random.random() < effective_chance:
                    item_id = item.get("id")
                    name = item.get("customer_name", "Customer")
                    try:
                        await _request(
                            client, "PATCH", f"/api/queues/items/{item_id}/status",
                            params={"new_status": "cancelled"},
                        )
                        STATE.log(
                            f"❌ {name} left the queue — wait too long"
                            + (" (surge)" if STATE.in_surge else ""),
                            "dim red",
                        )
                        STATE.stats["cancellations_today"] += 1
                    except APIError:
                        pass
        await asyncio.sleep(random.uniform(CANCEL_CHECK_INTERVAL * 0.5, CANCEL_CHECK_INTERVAL * 1.5))


# ─── Midnight reset ───────────────────────────────────────────────────────────


async def midnight_reset_loop(
    client: httpx.AsyncClient, owner: Actor, employees: list,
) -> None:
    """At midnight: reset daily stats, re-check close days, re-roll sick days."""
    while STATE.running:
        import datetime as dt_mod
        now = datetime.now()
        tomorrow = (now + dt_mod.timedelta(days=1)).replace(
            hour=0, minute=0, second=5, microsecond=0
        )
        await asyncio.sleep((tomorrow - now).total_seconds())
        if not STATE.running:
            return

        STATE.log("🌙 Midnight — resetting daily stats for the new day", "bold blue")
        STATE.stats["customers_served"] = 0
        STATE.stats["customers_today"] = 0
        STATE.stats["cancellations_today"] = 0
        STATE.stats["revenue_today"] = 0.0
        STATE.stats["payments_processed"] = 0
        STATE.stats["owner_queries"] = 0
        STATE.stats["approvals_pending"] = 0
        STATE.stats["approvals_resolved"] = 0
        STATE.stats["start"] = datetime.now()
        STATE.shop_closed_today = False
        STATE.in_surge = False
        STATE.walkins_open = True

        await _check_today_closed(client)
        await _register_upcoming_holidays(client, owner)

        for emp in employees:
            was_sick = emp.on_sick_day
            emp.on_sick_day = random.random() < SICK_DAY_CHANCE
            if emp.on_sick_day:
                STATE.log(f"🤒 {emp.display_name} called in sick today!", "bold red")
            elif was_sick:
                STATE.log(f"👷 {emp.display_name} is back from sick day", "green")


# ─── Actor: Owner ─────────────────────────────────────────────────────────────


async def owner_loop(client: httpx.AsyncClient, owner: Actor) -> None:
    """Owner periodically chats with the AI agent about shop operations."""
    await asyncio.sleep(20)
    query_idx = 0
    while STATE.running:
        if not owner.token or not STATE.shop_id:
            await asyncio.sleep(10)
            continue
        if STATE.shop_closed_today or not _shop_is_open():
            await asyncio.sleep(max(_seconds_until_open(), 30.0))
            continue

        query = OWNER_QUERIES[query_idx % len(OWNER_QUERIES)]
        query_idx += 1

        try:
            resp = await _request(
                client, "POST", "/api/v2/agent/chat",
                token=owner.token,
                json={"message": query, "shop_id": STATE.shop_id},
            )
            answer: str = resp.get("response", "")
            agent: str = resp.get("agent", "supervisor")
            short = (answer[:140] + "…") if len(answer) > 140 else answer
            # Strip markdown for display
            short = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", short)

            STATE.log(f'🏪 Owner: "{query[:65]}"', "magenta")
            STATE.log(f"   🤖 [{agent}]: {short}", "bright_magenta")
            STATE.stats["owner_queries"] += 1

        except APIError as e:
            if e.status == 401:
                STATE.log("🔄 Owner token expired — re-logging in", "yellow")
                await login(client, owner)
            else:
                STATE.log(f"⚠️  Agent query failed ({e.status})", "dim yellow")
        except Exception as exc:
            STATE.log(f"⚠️  Owner loop error: {str(exc)[:60]}", "dim yellow")

        await asyncio.sleep(random.uniform(OWNER_QUERY_MIN, OWNER_QUERY_MAX))


# ─── Actor: Owner Approval ────────────────────────────────────────────────────


async def _resolve_orphaned_approvals(client: httpx.AsyncClient, owner: Actor) -> None:
    """
    Poll /api/v2/agent/pending and log any waiting approvals.
    Only auto-approve an item if the real owner has not responded within
    _APPROVAL_TIMEOUT_SECS (default 2 hours) — this is a safety-net fallback,
    not the primary flow.  The human owner is expected to approve/reject via
    the Agent Inbox UI before this timeout fires.
    """
    if not owner.token or not STATE.shop_id:
        return
    try:
        data = await _request(
            client, "GET", "/api/v2/agent/pending",
            token=owner.token,
            params={"shop_id": STATE.shop_id},
        )
        pending_list = data.get("pending", [])
        now = datetime.now(timezone.utc)
        for item in pending_list:
            action_id = item.get("action_id")
            action_type = item.get("action") or item.get("action_type", "unknown")
            if not action_id:
                continue

            # Parse created_at to decide whether the timeout has elapsed.
            created_at_raw = item.get("created_at")
            age_secs: float = 0.0
            if created_at_raw:
                try:
                    created_dt = datetime.fromisoformat(
                        str(created_at_raw).replace("Z", "+00:00")
                    )
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    age_secs = (now - created_dt).total_seconds()
                except (ValueError, TypeError):
                    pass

            if age_secs < _APPROVAL_TIMEOUT_SECS:
                # Still within the human owner's decision window — just notify.
                hours_left = (_APPROVAL_TIMEOUT_SECS - age_secs) / 3600
                STATE.log(
                    f"   🔔 Approval pending: [{action_type}] — "
                    f"waiting for owner decision ({hours_left:.1f}h until auto-approve)",
                    "bold yellow",
                )
                STATE.stats["approvals_pending"] = max(
                    STATE.stats.get("approvals_pending", 0),
                    len(pending_list),
                )
            else:
                # Timeout elapsed — step in as a safety-net fallback.
                # Never auto-approve queue closures (would break the simulation).
                approved = action_type != "close_queue"
                reason = (
                    "Auto-approved: owner did not respond within 2 hours"
                    if approved
                    else "Auto-rejected: queue-close requests are never auto-approved"
                )
                try:
                    await _request(
                        client, "POST", "/api/v2/agent/approve",
                        token=owner.token,
                        json={
                            "shop_id": STATE.shop_id,
                            "action_id": action_id,
                            "approved": approved,
                            "reason": reason,
                        },
                    )
                    verdict = "⏰ Auto-approved (2h timeout)" if approved else "⏰ Auto-rejected (queue-close, never auto)"
                    STATE.log(
                        f"   {verdict} [{action_type}]",
                        "bright_green" if approved else "bright_red",
                    )
                    STATE.stats["approvals_resolved"] = STATE.stats.get("approvals_resolved", 0) + 1
                    STATE.stats["approvals_pending"] = max(0, STATE.stats.get("approvals_pending", 0) - 1)
                except APIError:
                    pass
    except Exception:
        pass


async def owner_approval_loop(client: httpx.AsyncClient, owner: Actor) -> None:
    """
    Owner periodically issues action-oriented commands designed to trigger HITL
    approval gates (close_queue, add_employee, assign_shift, create_invoice,
    record_payment, process_refund). After a short deliberation pause the
    simulation owner approves or rejects and the LangGraph checkpoint resumes.
    """
    await asyncio.sleep(45)  # let setup + first customers settle
    scenario_idx = 0

    while STATE.running:
        if not owner.token or not STATE.shop_id:
            await asyncio.sleep(10)
            continue
        if not _shop_is_open() or STATE.shop_closed_today:
            await asyncio.sleep(30)
            continue

        message, force_reject = _APPROVAL_SCENARIOS[scenario_idx % len(_APPROVAL_SCENARIOS)]
        scenario_idx += 1

        STATE.log(f'🏪 Owner → agent: "{message[:70]}"', "magenta")

        try:
            resp = await _request(
                client, "POST", "/api/v2/agent/chat",
                token=owner.token,
                json={"message": message, "shop_id": STATE.shop_id},
            )
            STATE.stats["owner_queries"] += 1

            approval_required = resp.get("approval_required", False)
            pending = resp.get("pending_action") or {}
            action_id = pending.get("action_id")
            action_type = pending.get("action") or pending.get("action_type", "unknown")

            if approval_required and action_id:
                # The approval was created — leave it for the real human owner to
                # decide via the Agent Inbox UI.  The _resolve_orphaned_approvals
                # poller will auto-approve as a safety-net after 2 hours.
                STATE.stats["approvals_pending"] = STATE.stats.get("approvals_pending", 0) + 1
                STATE.log(
                    f"   🔔 Approval created: [{action_type}] — check the Agent Inbox to approve/reject",
                    "bold yellow",
                )
            else:
                agent_reply: str = resp.get("response", "")
                short = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", agent_reply[:120])
                if len(agent_reply) > 120:
                    short += "…"
                STATE.log(f"   🤖 [no gate]: {short}", "dim magenta")

        except APIError as e:
            if e.status == 401:
                STATE.log("🔄 Owner token expired — re-logging in", "yellow")
                await login(client, owner)
            else:
                STATE.log(f"⚠️  Approval scenario failed ({e.status})", "dim yellow")
        except Exception as exc:
            STATE.log(f"⚠️  Approval loop error: {str(exc)[:60]}", "dim yellow")

        # Clean up any orphaned approvals from the regular owner_loop queries
        await _resolve_orphaned_approvals(client, owner)

        await asyncio.sleep(
            random.uniform(_APPROVAL_SCENARIO_INTERVAL_MIN, _APPROVAL_SCENARIO_INTERVAL_MAX)
        )


# ─── Actor: Employee leave request loop ───────────────────────────────────────

# Employee-initiated leave requests. Each employee uses their own JWT token to
# message the agent directly — just like a real employee would do on their phone.
# The HR specialist receives the message, recognises it as a leave_request, and
# creates a pending_action that lands in the OWNER's Agent Inbox.
# This is the most realistic approval flow (employee → agent → owner approval gate).

def _next_weekday_str(offset_days: int) -> str:
    """Return a date string N working days from today, skipping weekends."""
    from datetime import date, timedelta
    target = date.today()
    added = 0
    while added < offset_days:
        target += timedelta(days=1)
        if target.weekday() < 5:   # Mon–Fri
            added += 1
    return target.strftime("%A, %B %-d")   # e.g. "Friday, May 9"

# Leave request templates.
# Each tuple: (message_template, leave_type, reason)
# {date} is replaced at runtime with a realistic upcoming date.
_EMPLOYEE_LEAVE_REQUESTS: list[dict] = [
    # Sick day
    {
        "employee": "marcus",
        "template": "Hi, I'm not feeling well today — I need to call in sick. Can you register my sick day for today?",
        "leave_type": "sick",
    },
    {
        "employee": "elena",
        "template": "I've come down with a cold and won't be able to come in tomorrow. Please log my sick day.",
        "leave_type": "sick",
    },
    # Annual leave
    {
        "employee": "marcus",
        "template": "I'd like to request annual leave on {date} — I have a family event. Can you submit that for me?",
        "leave_type": "annual",
    },
    {
        "employee": "elena",
        "template": "Can I take a day off on {date}? I've got some personal things to take care of. Please request leave for me.",
        "leave_type": "annual",
    },
    {
        "employee": "marcus",
        "template": "Hey, I need to take {date} off — I have a doctor's appointment I can't reschedule. Please put in a leave request.",
        "leave_type": "personal",
    },
    {
        "employee": "elena",
        "template": "I was hoping to take leave on {date} and {date2} for a short trip. Could you file that leave request for me?",
        "leave_type": "annual",
    },
    # Shift swap / early finish
    {
        "employee": "marcus",
        "template": "Is it possible to leave early on {date}? I need to finish by 3pm. Can you request a half-day for me?",
        "leave_type": "personal",
    },
    {
        "employee": "elena",
        "template": "I need next {date} off — I have my kid's school event. Can you register a personal day for me?",
        "leave_type": "personal",
    },
    # Longer leave
    {
        "employee": "marcus",
        "template": "I'd like to take my remaining annual leave days starting {date}. I'm planning to take 3 days off. Please submit the leave request.",
        "leave_type": "annual",
    },
    {
        "employee": "elena",
        "template": "I need to request a couple of days off — {date} and {date2}. It's for a family commitment. Please file the leave request.",
        "leave_type": "personal",
    },
]

# Interval for each employee submitting a leave request (real-time seconds)
_EMPLOYEE_LEAVE_INTERVAL_MIN = float(os.getenv("EMPLOYEE_LEAVE_MIN", "90"))    # 1.5 min
_EMPLOYEE_LEAVE_INTERVAL_MAX = float(os.getenv("EMPLOYEE_LEAVE_MAX", "180"))   # 3 min


async def employee_leave_loop(
    client: httpx.AsyncClient,
    employees: list[Actor],
) -> None:
    """
    Simulates employees submitting leave requests directly to the AI agent.
    Each employee uses their own JWT token, so the agent knows who is asking.
    The HR specialist creates a leave_request pending_action → appears in owner's Agent Inbox.
    """
    await asyncio.sleep(60)  # let the main loops settle first
    request_idx = 0

    # Build a name → actor lookup
    emp_by_name: dict[str, Actor] = {e.display_name.lower(): e for e in employees}

    while STATE.running:
        if not STATE.shop_id:
            await asyncio.sleep(10)
            continue

        req = _EMPLOYEE_LEAVE_REQUESTS[request_idx % len(_EMPLOYEE_LEAVE_REQUESTS)]
        request_idx += 1

        # Pick the right employee actor
        actor = emp_by_name.get(req["employee"])
        if actor is None or actor.on_sick_day or not actor.token:
            await asyncio.sleep(random.uniform(_EMPLOYEE_LEAVE_INTERVAL_MIN, _EMPLOYEE_LEAVE_INTERVAL_MAX))
            continue

        # Build realistic dates
        date1 = _next_weekday_str(random.randint(1, 5))
        date2 = _next_weekday_str(random.randint(6, 8))
        message = req["template"].replace("{date}", date1).replace("{date2}", date2)

        STATE.log(
            f"👷 {actor.display_name} → agent: \"{message[:70]}\"",
            "cyan",
        )

        try:
            resp = await _request(
                client, "POST", "/api/v2/agent/chat",
                token=actor.token,
                json={"message": message, "shop_id": STATE.shop_id},
            )

            approval_required = resp.get("approval_required", False)
            pending = resp.get("pending_action") or {}
            action_id = pending.get("action_id")
            action_type = pending.get("action") or pending.get("action_type", "unknown")

            if approval_required and action_id:
                STATE.stats["approvals_pending"] = STATE.stats.get("approvals_pending", 0) + 1
                STATE.log(
                    f"   🔔 Leave request created for {actor.display_name}: [{action_type}] — "
                    f"check Agent Inbox to approve/reject",
                    "bold yellow",
                )
            else:
                agent_reply: str = resp.get("response", "")
                short = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", agent_reply[:100])
                STATE.log(f"   🤖 Agent replied (no gate): {short}", "dim cyan")

        except APIError as e:
            if e.status == 401:
                STATE.log(f"🔄 {actor.display_name} token expired — re-logging in", "yellow")
                await login(client, actor)
            else:
                STATE.log(f"⚠️  Employee leave request failed ({e.status})", "dim yellow")
        except Exception as exc:
            STATE.log(f"⚠️  Employee leave loop error: {str(exc)[:60]}", "dim yellow")

        await asyncio.sleep(
            random.uniform(_EMPLOYEE_LEAVE_INTERVAL_MIN, _EMPLOYEE_LEAVE_INTERVAL_MAX)
        )


# ─── Queue poller ─────────────────────────────────────────────────────────────


async def queue_poller(client: httpx.AsyncClient) -> None:
    """Refresh live queue state every 4 seconds for the dashboard."""
    while STATE.running:
        try:
            if STATE.shop_id:
                queue = await _request(
                    client, "GET", f"/api/queues/shop/{STATE.shop_id}/active",
                )
                STATE.queue_items = queue.get("queue_items", [])
                active = [
                    i for i in STATE.queue_items
                    if i["status"] in ("waiting", "being_served")
                ]
                STATE.stats["customers_waiting"] = len(active)
        except Exception:
            pass
        await asyncio.sleep(4)


# ─── Rich dashboard ───────────────────────────────────────────────────────────


def _build_dashboard() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="queue", ratio=2),
        Layout(name="log", ratio=3),
    )

    # ── Header ──
    elapsed = datetime.now() - STATE.stats["start"]
    h = int(elapsed.total_seconds() // 3600)
    m = int((elapsed.total_seconds() % 3600) // 60)
    s = int(elapsed.total_seconds() % 60)
    layout["header"].update(Panel(
        Text(
            f"🚀  ZeroQwait Live Simulation — {SHOP_NAME}"
            f"   |   Running {h:02d}:{m:02d}:{s:02d}"
            f"   |   Watch UI → http://localhost:3000",
            style="bold white on blue",
            justify="center",
        ),
        border_style="blue",
    ))

    # ── Queue table ──
    q_table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold cyan",
        title="[bold]Live Queue[/bold]",
        expand=True,
    )
    q_table.add_column("#", width=4, justify="right")
    q_table.add_column("Customer", min_width=18)
    q_table.add_column("Service", min_width=20)
    q_table.add_column("Status", width=14)
    q_table.add_column("Barber", width=12)

    active_items = [
        i for i in STATE.queue_items
        if i["status"] in ("waiting", "being_served")
    ]
    for item in sorted(active_items, key=lambda x: x.get("position", 999)):
        status = item["status"]
        is_serving = status == "being_served"
        row_style = "bright_green" if is_serving else "white"
        icon = "✂️ " if is_serving else "⏳"
        svc = (item.get("service") or {}).get("name", "—")
        emp = (item.get("assigned_employee") or {})
        emp_name = emp.get("username", "—") if emp else "—"
        q_table.add_row(
            str(item.get("position", "?")),
            item.get("customer_name", "?"),
            svc,
            f"{icon} {status.replace('_', ' ')}",
            emp_name,
            style=row_style,
        )

    if not active_items:
        q_table.add_row("—", "[dim]Queue empty[/dim]", "—", "[dim]—[/dim]", "[dim]—[/dim]")

    surge_badge = "  [bold red blink]⚡ SURGE — WALK-INS CLOSED[/bold red blink]" if STATE.in_surge else ""
    stats_line = (
        f"[cyan]Today[/cyan]: {STATE.stats['customers_today']} arrivals  "
        f"[green]{STATE.stats['customers_served']} served[/green]  "
        f"[red]{STATE.stats['cancellations_today']} cancelled[/red]  "
        f"[bright_white]{STATE.stats['payments_processed']} payments[/bright_white]  "
        f"[yellow]${STATE.stats['revenue_today']:.2f} revenue[/yellow]  "
        f"[magenta]{STATE.stats['owner_queries']} AI queries[/magenta]  "
        f"[bold yellow]{STATE.stats['approvals_pending']} pending[/bold yellow]  "
        f"[green]{STATE.stats['approvals_resolved']} resolved[/green]"
        + ("  [bold red]CLOSED TODAY[/bold red]" if STATE.shop_closed_today else "")
        + surge_badge
    )
    layout["queue"].update(Panel(
        q_table,
        border_style="cyan",
        subtitle=stats_line,
    ))

    # ── Activity log ──
    log_text = Text()
    for ts, msg, style in STATE.events[-28:]:
        log_text.append(f"[{ts}] ", style="dim")
        log_text.append(f"{msg}\n", style=style)
    layout["log"].update(Panel(
        log_text,
        title="[bold]Live Activity Feed[/bold]",
        border_style="green",
        subtitle="[dim]All actor events in real time[/dim]",
    ))

    # ── Footer ──
    shop_status   = "🟢 OPEN" if (_shop_is_open() and not STATE.shop_closed_today) else "🔴 CLOSED"
    walkin_status = "🚶 Walk-ins: OPEN" if STATE.walkins_open else "🚫 Walk-ins: SUSPENDED"
    layout["footer"].update(Panel(
        Text(
            f"{shop_status}  │  {walkin_status}  │  "
            f"Waiting: {STATE.stats['customers_waiting']}  │  "
            f"Cancelled: {STATE.stats['cancellations_today']}  │  "
            f"Served: {STATE.stats['customers_served']}  │  "
            f"Revenue: ${STATE.stats['revenue_today']:.2f}  │  "
            f"Hours: {STATE.open_hour:02d}:{STATE.open_minute:02d}–{STATE.close_hour:02d}:{STATE.close_minute:02d} {STATE.operating_timezone}  │  "
            f"Compression={TIME_COMPRESSION}x  │  "
            f"http://localhost:3000",
            justify="center",
            style="dim",
        ),
        border_style="dim",
    ))

    return layout


# ─── Wait for backend ─────────────────────────────────────────────────────────


async def wait_for_backend(client: httpx.AsyncClient, console: Console) -> bool:
    console.print("[bold yellow]⏳ Waiting for backend to be ready...[/bold yellow]")
    for attempt in range(40):
        try:
            resp = await client.get(f"{BASE_URL}/api/agent/health", timeout=5)
            if resp.status_code < 500:
                console.print(f"[bold green]✅ Backend ready[/bold green]")
                return True
        except Exception:
            pass
        console.print(f"[dim]  [{attempt + 1}/40] not yet ready, retrying in 5s...[/dim]")
        await asyncio.sleep(5)
    return False


# ─── Main ────────────────────────────────────────────────────────────────────


async def main() -> None:
    console = Console()
    console.print(
        "\n[bold blue]╔══════════════════════════════════════════════════╗[/bold blue]"
    )
    console.print(
        "[bold blue]║  ZeroQwait Live Shop Simulation                  ║[/bold blue]"
    )
    console.print(
        "[bold blue]╚══════════════════════════════════════════════════╝[/bold blue]\n"
    )
    console.print(f"  Target: [cyan]{BASE_URL}[/cyan]")
    console.print(f"  Shop:   [cyan]{SHOP_NAME}[/cyan]")
    console.print(f"  Watch:  [cyan]http://localhost:3000[/cyan]\n")

    owner = Actor(
        display_name=SIM_OWNER_DISPLAY_NAME,
        email=SIM_OWNER_EMAIL,
        password=SIM_OWNER_PASSWORD,
        role="shop_owner",
    )
    try:
        employees = _load_employee_specs()
    except RuntimeError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        return

    async with httpx.AsyncClient() as client:
        if not await wait_for_backend(client, console):
            console.print("[bold red]Backend never became ready. Exiting.[/bold red]")
            return

        if not await setup(client, owner, employees):
            console.print("[bold red]Setup failed. Check backend logs.[/bold red]")
            return

        tasks = [
            asyncio.create_task(customer_loop(client, owner)),
            *(asyncio.create_task(employee_loop(client, owner, employee)) for employee in employees),
            asyncio.create_task(owner_loop(client, owner)),
            asyncio.create_task(owner_approval_loop(client, owner)),
            asyncio.create_task(employee_leave_loop(client, employees)),
            asyncio.create_task(queue_poller(client)),
            asyncio.create_task(surge_monitor_loop(client, owner)),
            asyncio.create_task(cancellation_loop(client, owner)),
            asyncio.create_task(midnight_reset_loop(client, owner, employees)),
        ]

        try:
            if SIM_LOG_ONLY:
                while STATE.running:
                    await asyncio.sleep(1)
            else:
                with Live(
                    _build_dashboard(),
                    refresh_per_second=1,
                    console=console,
                    screen=False,
                    vertical_overflow="visible",
                ) as live:
                    while STATE.running:
                        await asyncio.sleep(1)
                        live.update(_build_dashboard())
        except (KeyboardInterrupt, asyncio.CancelledError):
            STATE.running = False
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    console.print("\n[bold green]Simulation stopped cleanly.[/bold green]")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
