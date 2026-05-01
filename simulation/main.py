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
  CUSTOMER_ARRIVAL_MIN/MAX Seconds between customer arrivals (default: 20/45)
  EMPLOYEE_CALL_MIN/MAX    Seconds between employee call-next attempts (default: 25/55)
  OWNER_QUERY_MIN/MAX      Seconds between owner AI queries (default: 60/120)
  TIME_COMPRESSION         Seconds per simulated service-minute (default: 2)
  MAX_QUEUE_SIZE           Max simultaneous waiting customers (default: 10)
  SHIFT_DURATION_MINUTES   Simulated shift length in minutes before clock-out (default: 480 = 8h)
  SICK_DAY_CHANCE          0.0–1.0 probability each employee calls in sick (default: 0.15)
"""

import asyncio
import logging
import os
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

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

# ─── State ────────────────────────────────────────────────────────────────────


@dataclass
class Actor:
    display_name: str
    email: str
    password: str
    role: str
    token: Optional[str] = None
    user_id: Optional[int] = None
    on_sick_day: bool = False
    clocked_in: bool = False
    svc_time_min: float = 20.0  # simulated minutes per service (lower bound)
    svc_time_max: float = 30.0  # simulated minutes per service (upper bound)


@dataclass
class SimState:
    shop_id: Optional[int] = None
    queue_id: Optional[int] = None
    services: list = field(default_factory=list)
    queue_items: list = field(default_factory=list)
    events: list = field(default_factory=list)
    shop_closed_today: bool = False  # True if today is a registered close day
    walkins_open: bool = True        # False during a queue surge
    in_surge: bool = False           # True when waiting >= SURGE_THRESHOLD
    stats: dict = field(default_factory=lambda: {
        "customers_served": 0,
        "customers_waiting": 0,
        "customers_today": 0,
        "cancellations_today": 0,
        "revenue_today": 0.0,
        "payments_processed": 0,
        "owner_queries": 0,
        "start": datetime.now(),
    })
    running: bool = True

    def log(self, msg: str, style: str = "white") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.events.append((ts, msg, style))
        if len(self.events) > 60:
            self.events.pop(0)


STATE = SimState()

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
                "username": actor.display_name,
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

    if not await ensure_user(client, owner):
        STATE.log("❌ Owner setup failed — aborting", "bold red")
        return False
    STATE.log(f"✅ Owner '{owner.display_name}' ready (id={owner.user_id})", "green")

    # Find or create shop
    try:
        shops: list = await _request(client, "GET", "/api/shops/my-shops", token=owner.token)
        existing = next((s for s in shops if s["name"] == SHOP_NAME), None)
        if existing:
            STATE.shop_id = existing["id"]
            STATE.log(f"🏪 Shop '{SHOP_NAME}' found (id={STATE.shop_id})", "cyan")
        else:
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
                    "username": emp.display_name,
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
        today_str = datetime.now().strftime("%Y-%m-%d")
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

def _shop_is_open() -> bool:
    """Return True if the shop is within operating hours (real wall clock)."""
    h = datetime.now().hour
    if SHOP_CLOSE_HOUR == 0:  # 0 = midnight — open until end of day
        return SHOP_OPEN_HOUR <= h
    return SHOP_OPEN_HOUR <= h < SHOP_CLOSE_HOUR


def _seconds_until_open() -> float:
    """Seconds from now until the shop next opens. Returns 0.0 if already open."""
    import datetime as dt_mod
    if _shop_is_open():
        return 0.0
    now = datetime.now()
    if now.hour < SHOP_OPEN_HOUR:
        next_open = now.replace(hour=SHOP_OPEN_HOUR, minute=0, second=0, microsecond=0)
    else:
        tomorrow = now.date() + dt_mod.timedelta(days=1)
        next_open = dt_mod.datetime(tomorrow.year, tomorrow.month, tomorrow.day, SHOP_OPEN_HOUR)
    return max((next_open - now).total_seconds(), 0.0)


# ─── Actor: Customer ──────────────────────────────────────────────────────────


async def customer_loop(client: httpx.AsyncClient) -> None:
    """Continuously spawn new customers joining the queue."""
    await asyncio.sleep(3)
    while STATE.running:
        # Shop closed today (holiday / close day) — no customers arrive
        if STATE.shop_closed_today:
            await asyncio.sleep(30)
            continue

        active = [i for i in STATE.queue_items if i["status"] in ("waiting", "being_served")]
        if len(active) >= MAX_QUEUE_SIZE:
            await asyncio.sleep(8)
            continue

        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        service = random.choice(STATE.services) if STATE.services else None

        try:
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
            cost = f"${service['cost']:.0f}" if service else ""
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

        delay = random.uniform(CUSTOMER_ARRIVAL_MIN, CUSTOMER_ARRIVAL_MAX)
        await asyncio.sleep(delay)


# ─── Actor: Employee ──────────────────────────────────────────────────────────


async def employee_loop(client: httpx.AsyncClient, emp: Actor) -> None:
    """Employee shift: clock in → serve customers → checkout+pay → clock out."""
    await asyncio.sleep(6 + random.uniform(0, 5))

    if emp.on_sick_day:
        # Nothing to do today — the sick-day log was already written in setup
        return

    shift_seconds = SHIFT_DURATION_MINUTES * TIME_COMPRESSION
    shift_end = asyncio.get_event_loop().time() + shift_seconds

    while STATE.running:
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

        if not emp.token or not emp.clocked_in:
            await asyncio.sleep(5)
            continue

        # Jitter between employees so they don't call in sync
        delay = random.uniform(EMPLOYEE_CALL_MIN, EMPLOYEE_CALL_MAX)

        try:
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

            # Checkout + payment
            payment_method = random.choice(PAYMENT_METHODS)
            tip = round(random.uniform(0, svc_cost * 0.25), 2) if svc_cost > 0 else 0.0
            total = svc_cost + tip
            try:
                await _request(
                    client, "POST", f"/api/queues/items/{item_id}/checkout",
                )
                STATE.log(
                    f"💳 {cust_name} paid ${total:.2f} ({payment_method})"
                    + (f" + ${tip:.2f} tip" if tip > 0.5 else ""),
                    "bright_white",
                )
                STATE.stats["payments_processed"] += 1
            except APIError:
                STATE.log(
                    f"💵 {cust_name} paid ${svc_cost:.2f} ({payment_method}) [no checkout endpoint]",
                    "white",
                )

            STATE.log(
                f"✅ {emp.display_name} ✓ {cust_name} — {svc_name} (${total:.2f})",
                "bright_green",
            )
            STATE.stats["customers_served"] += 1
            STATE.stats["revenue_today"] += total

        except APIError as e:
            if e.status in (400, 404):
                pass  # queue empty, totally normal
            elif e.status == 401:
                STATE.log(f"🔄 {emp.display_name} token expired — re-logging in", "yellow")
                await login(client, emp)
            else:
                STATE.log(f"⚠️  {emp.display_name}: {str(e)[:80]}", "dim yellow")

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
        f"[magenta]{STATE.stats['owner_queries']} AI queries[/magenta]"
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
            f"Hours: {SHOP_OPEN_HOUR:02d}:00–00:00  │  "
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
        display_name="demo_owner",
        email="demo.owner@zeroqwait.demo",
        password="ZeroQDemo2025!",
        role="shop_owner",
    )
    employees = [
        Actor("Marcus", "marcus.barber@zeroqwait.demo", "ZeroQDemo2025!", "employee",
              svc_time_min=24.0, svc_time_max=26.0),   # methodical — 24–26 sim-min per cut
        Actor("Elena",  "elena.barber@zeroqwait.demo",  "ZeroQDemo2025!", "employee",
              svc_time_min=16.0, svc_time_max=18.0),   # quick hands — 16–18 sim-min per cut
    ]

    async with httpx.AsyncClient() as client:
        if not await wait_for_backend(client, console):
            console.print("[bold red]Backend never became ready. Exiting.[/bold red]")
            return

        if not await setup(client, owner, employees):
            console.print("[bold red]Setup failed. Check backend logs.[/bold red]")
            return

        tasks = [
            asyncio.create_task(customer_loop(client)),
            asyncio.create_task(employee_loop(client, employees[0])),
            asyncio.create_task(employee_loop(client, employees[1])),
            asyncio.create_task(owner_loop(client, owner)),
            asyncio.create_task(queue_poller(client)),
            asyncio.create_task(surge_monitor_loop(client, owner)),
            asyncio.create_task(cancellation_loop(client, owner)),
            asyncio.create_task(midnight_reset_loop(client, owner, employees)),
        ]

        try:
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
