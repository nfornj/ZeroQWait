#!/usr/bin/env python3
"""
ZeroQwait Live Shop Simulation
================================

Simulates a real barber shop with:
  👷 2 barber employees — serve customers in queue
  👤 Continuous customer arrivals — join queue with random services
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
]

# ─── State ────────────────────────────────────────────────────────────────────


@dataclass
class Actor:
    display_name: str
    email: str
    password: str
    role: str
    token: Optional[str] = None
    user_id: Optional[int] = None


@dataclass
class SimState:
    shop_id: Optional[int] = None
    queue_id: Optional[int] = None
    services: list = field(default_factory=list)
    queue_items: list = field(default_factory=list)
    events: list = field(default_factory=list)
    stats: dict = field(default_factory=lambda: {
        "customers_served": 0,
        "customers_waiting": 0,
        "customers_today": 0,
        "revenue_today": 0.0,
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

    # Setup employees
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
        if await login(client, emp):
            STATE.log(f"👷 Barber '{emp.display_name}' ready (id={emp.user_id})", "green")
        else:
            STATE.log(f"⚠️  Barber '{emp.display_name}' login failed", "yellow")

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
        STATE.log("🚀 Setup complete — simulation is LIVE!", "bold green")
        STATE.log(f"   👀 Watch at http://localhost:3000", "bold cyan")
    return True


# ─── Actor: Customer ──────────────────────────────────────────────────────────


async def customer_loop(client: httpx.AsyncClient) -> None:
    """Continuously spawn new customers joining the queue."""
    await asyncio.sleep(3)
    while STATE.running:
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
    """Employee calls next customer, serves them, marks complete."""
    await asyncio.sleep(6 + random.uniform(0, 5))
    while STATE.running:
        if not emp.token:
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
            STATE.log(
                f"✅ {emp.display_name} ✓ {cust_name} — {svc_name} (${svc_cost:.0f})",
                "bright_green",
            )
            STATE.stats["customers_served"] += 1
            STATE.stats["revenue_today"] += svc_cost

        except APIError as e:
            if e.status in (400, 404):
                pass  # queue empty, totally normal
            elif e.status == 401:
                STATE.log(f"🔄 {emp.display_name} token expired — re-logging in", "yellow")
                await login(client, emp)
            else:
                STATE.log(f"⚠️  {emp.display_name}: {str(e)[:80]}", "dim yellow")


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

    stats_line = (
        f"[cyan]Today[/cyan]: {STATE.stats['customers_today']} arrivals  "
        f"[green]{STATE.stats['customers_served']} served[/green]  "
        f"[yellow]${STATE.stats['revenue_today']:.0f} revenue[/yellow]  "
        f"[magenta]{STATE.stats['owner_queries']} AI queries[/magenta]"
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
    layout["footer"].update(Panel(
        Text(
            f"Ctrl+C to stop  │  "
            f"Waiting: {STATE.stats['customers_waiting']}  │  "
            f"Served today: {STATE.stats['customers_served']}  │  "
            f"Revenue: ${STATE.stats['revenue_today']:.2f}  │  "
            f"TIME_COMPRESSION={TIME_COMPRESSION}x  │  "
            f"Watch UI → http://localhost:3000",
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
        Actor("Marcus", "marcus.barber@zeroqwait.demo", "ZeroQDemo2025!", "employee"),
        Actor("Elena",  "elena.barber@zeroqwait.demo",  "ZeroQDemo2025!", "employee"),
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
