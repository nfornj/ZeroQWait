#!/usr/bin/env python3
"""Seed one deterministic local demo shop for manual testing.

This script is intentionally narrow: it only resets fixture-owned records for
the fixed demo shop slug and leaves unrelated local data alone.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import database first so backend/.env is loaded before auth_utils checks SECRET_KEY.
from database import SessionLocal  # noqa: E402
import models  # noqa: F401,E402  # registers SQLAlchemy models with Base metadata

from sqlalchemy import inspect  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from modules.agent.models import (  # noqa: E402
    AgentNotification,
    ApprovalRequest,
    ApprovalStatus,
    Commitment,
    NotificationStatus,
    PolicyMode,
    ShopPolicy,
    ShopSoul,
    SoulLearning,
)
from modules.appointments.models import Appointment, AppointmentStatus  # noqa: E402
from modules.auth.models import SubscriptionTier, User, UserRole  # noqa: E402
from modules.employees.models import EmployeeShift, ShopEmployee  # noqa: E402
from modules.payments.models import (  # noqa: E402
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from modules.queues.models import Queue, QueueItem, QueueStatus  # noqa: E402
from modules.shops.models import (  # noqa: E402
    DailyAnalytics,
    Shop,
    ShopCustomer,
    ShopOperatingHours,
    ShopService,
)
from shared.auth_utils import get_password_hash  # noqa: E402


DEMO_PASSWORD = "DemoPass123!"
DEMO_SHOP_NAME = "ZeroQ Demo Cuts"
DEMO_SHOP_SLUG = "zeroq-demo-cuts"
DEMO_DOMAIN = "example-zeroqwait.com"


@dataclass(frozen=True)
class AccountSpec:
    username: str
    email: str
    role: UserRole
    tier: SubscriptionTier = SubscriptionTier.FREE


ADMIN = AccountSpec(
    username="demo_admin",
    email=f"demo.admin@{DEMO_DOMAIN}",
    role=UserRole.SUPER_ADMIN,
    tier=SubscriptionTier.ENTERPRISE,
)
OWNER = AccountSpec(
    username="demo_owner",
    email=f"demo.owner@{DEMO_DOMAIN}",
    role=UserRole.SHOP_OWNER,
    tier=SubscriptionTier.PREMIUM,
)
EMPLOYEES = [
    AccountSpec("demo_manager", f"demo.manager@{DEMO_DOMAIN}", UserRole.MANAGER),
    AccountSpec("demo_barber_ava", f"ava.barber@{DEMO_DOMAIN}", UserRole.EMPLOYEE),
    AccountSpec("demo_barber_marco", f"marco.barber@{DEMO_DOMAIN}", UserRole.EMPLOYEE),
    AccountSpec("demo_barber_tess", f"tess.barber@{DEMO_DOMAIN}", UserRole.EMPLOYEE),
]

SERVICES = [
    ("Classic Haircut", "Consultation, wash, precision cut, and style.", 30, 32.00, True),
    ("Skin Fade", "Detailed clipper fade with neckline cleanup.", 40, 42.00, True),
    ("Beard Trim", "Shape, line-up, and conditioning finish.", 20, 18.00, True),
    ("Hot Towel Shave", "Traditional straight-razor shave with hot towel prep.", 35, 30.00, True),
    ("Hair + Beard Combo", "Full haircut, beard sculpting, and finish.", 55, 58.00, True),
    ("Kids Cut", "Quick child-friendly cut for customers under 12.", 25, 24.00, True),
    ("Color Consultation", "Inactive example service for settings screens.", 30, 0.00, False),
]

CUSTOMERS = [
    ("Jordan Lee", "+1-905-555-0101", "jordan.lee@example.com", 8),
    ("Priya Shah", "+1-905-555-0102", "priya.shah@example.com", 3),
    ("Ethan Brooks", "+1-905-555-0103", "ethan.brooks@example.com", 5),
    ("Sofia Chen", "+1-905-555-0104", "sofia.chen@example.com", 2),
    ("Malik Johnson", "+1-905-555-0105", "malik.johnson@example.com", 1),
    ("Nora Patel", "+1-905-555-0106", "nora.patel@example.com", 4),
    ("Andre Wilson", "+1-905-555-0107", "andre.wilson@example.com", 6),
    ("Mei Alvarez", "+1-905-555-0108", "mei.alvarez@example.com", 2),
]


def utcnow() -> datetime:
    """Return a naive UTC timestamp for existing SQLAlchemy DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the local ZeroQwait demo shop.")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not clear existing fixture rows for the demo shop before reseeding.",
    )
    return parser.parse_args()


def table_exists(db: Session, table_name: str) -> bool:
    return inspect(db.get_bind()).has_table(table_name)


def require_tables(db: Session, table_names: Iterable[str]) -> None:
    missing = [table_name for table_name in table_names if not table_exists(db, table_name)]
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            f"Database is missing required tables: {missing_list}. "
            "Run from backend with: PYTHONPATH=. .venv/bin/python scripts/init_database.py"
        )


def get_or_create_user(db: Session, spec: AccountSpec, password: str = DEMO_PASSWORD) -> User:
    user = db.query(User).filter(User.username == spec.username).first()
    if user is None:
        existing_email = db.query(User).filter(User.email == spec.email).first()
        if existing_email is not None:
            raise RuntimeError(
                f"Email {spec.email} is already used by username {existing_email.username}; "
                f"cannot create demo user {spec.username}."
            )
        user = User(username=spec.username, email=spec.email)
        db.add(user)

    user.email = spec.email
    user.hashed_password = get_password_hash(password)
    user.role = spec.role
    user.subscription_tier = spec.tier
    user.is_active = True
    db.flush()
    return user


def get_or_create_shop(db: Session, owner: User) -> Shop:
    shop = db.query(Shop).filter(Shop.slug == DEMO_SHOP_SLUG).first()
    if shop is None:
        shop = Shop(slug=DEMO_SHOP_SLUG, owner_id=owner.id)
        db.add(shop)

    shop.owner_id = owner.id
    shop.name = DEMO_SHOP_NAME
    shop.description = (
        "A busy local barbershop demo configured for owner workspace, "
        "employee queue, public booking, and agent-inbox testing."
    )
    shop.shop_type = "barber"
    shop.address = "22 Simcoe Street North"
    shop.city = "Oshawa"
    shop.state = "Ontario"
    shop.zip_code = "L1G 4R8"
    shop.country = "Canada"
    shop.phone = "+1-905-555-0199"
    shop.email = f"hello@{DEMO_SHOP_SLUG}.{DEMO_DOMAIN}"
    shop.website = f"https://{DEMO_SHOP_SLUG}.example.com"
    shop.average_service_time = 30
    shop.primary_color = "#1E6B5C"
    shop.secondary_color = "#D7E7E1"
    shop.accent_color = "#B75D32"
    shop.background_color = "#FAFBF8"
    shop.ai_agent_name = "ZeroQ Reception"
    shop.latitude = 43.8971
    shop.longitude = -78.8658
    shop.is_active = True
    db.flush()
    return shop


def reset_demo_rows(db: Session, shop: Shop) -> None:
    if table_exists(db, "payments"):
        db.query(Payment).filter(Payment.shop_id == shop.id).delete(synchronize_session=False)

    if table_exists(db, "invoice_line_items") and table_exists(db, "invoices"):
        invoice_ids = db.query(Invoice.id).filter(Invoice.shop_id == shop.id)
        db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id.in_(invoice_ids)).delete(
            synchronize_session=False
        )

    if table_exists(db, "invoices"):
        db.query(Invoice).filter(Invoice.shop_id == shop.id).delete(synchronize_session=False)

    if table_exists(db, "appointments"):
        db.query(Appointment).filter(Appointment.shop_id == shop.id).delete(synchronize_session=False)

    if table_exists(db, "queue_items") and table_exists(db, "queues"):
        queue_ids = db.query(Queue.id).filter(Queue.shop_id == shop.id)
        db.query(QueueItem).filter(QueueItem.queue_id.in_(queue_ids)).delete(synchronize_session=False)

    db.query(Queue).filter(Queue.shop_id == shop.id).delete(synchronize_session=False)
    db.query(EmployeeShift).filter(EmployeeShift.shop_id == shop.id).delete(synchronize_session=False)
    db.query(ShopEmployee).filter(ShopEmployee.shop_id == shop.id).delete(synchronize_session=False)
    db.query(ShopService).filter(ShopService.shop_id == shop.id).delete(synchronize_session=False)
    db.query(DailyAnalytics).filter(DailyAnalytics.shop_id == shop.id).delete(synchronize_session=False)
    db.query(ShopCustomer).filter(ShopCustomer.shop_id == shop.id).delete(synchronize_session=False)

    if table_exists(db, "approval_requests"):
        db.query(ApprovalRequest).filter(ApprovalRequest.shop_id == shop.id).delete(synchronize_session=False)
    if table_exists(db, "agent_notifications"):
        db.query(AgentNotification).filter(AgentNotification.shop_id == shop.id).delete(synchronize_session=False)
    if table_exists(db, "shop_policies"):
        db.query(ShopPolicy).filter(ShopPolicy.shop_id == shop.id).delete(synchronize_session=False)
    if table_exists(db, "soul_learnings"):
        db.query(SoulLearning).filter(SoulLearning.shop_id == shop.id).delete(synchronize_session=False)
    if table_exists(db, "commitments"):
        db.query(Commitment).filter(Commitment.shop_id == shop.id).delete(synchronize_session=False)
    if table_exists(db, "shop_soul"):
        db.query(ShopSoul).filter(ShopSoul.shop_id == shop.id).delete(synchronize_session=False)
    if table_exists(db, "shop_operating_hours"):
        db.query(ShopOperatingHours).filter(ShopOperatingHours.shop_id == shop.id).delete(
            synchronize_session=False
        )
    db.flush()


def seed_shop_services(db: Session, shop: Shop) -> dict[str, ShopService]:
    services: dict[str, ShopService] = {}
    for name, description, duration, cost, is_active in SERVICES:
        service = ShopService(
            shop_id=shop.id,
            name=name,
            description=description,
            duration_minutes=duration,
            cost=cost,
            currency="CAD",
            is_active=is_active,
        )
        db.add(service)
        db.flush()
        services[name] = service
    return services


def seed_employees(db: Session, shop: Shop, owner: User) -> dict[str, User]:
    employees: dict[str, User] = {}
    for index, spec in enumerate(EMPLOYEES, start=1):
        user = get_or_create_user(db, spec)
        db.add(
            ShopEmployee(
                shop_id=shop.id,
                user_id=user.id,
                created_by=owner.id,
                is_active=True,
                employee_code=f"DEMO-E{index:02d}",
            )
        )
        employees[spec.username] = user
    db.flush()
    return employees


def seed_shifts(db: Session, shop: Shop, employees: dict[str, User]) -> None:
    today = utcnow().date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    shifts = [
        ("demo_manager", datetime.combine(today, time(8, 45)), None),
        ("demo_barber_ava", datetime.combine(today, time(8, 55)), None),
        ("demo_barber_marco", datetime.combine(today, time(9, 15)), None),
        ("demo_barber_tess", datetime.combine(yesterday, time(9, 0)), datetime.combine(yesterday, time(17, 5))),
        ("demo_barber_tess", datetime.combine(tomorrow, time(9, 0)), datetime.combine(tomorrow, time(15, 0))),
    ]
    for username, clock_in, clock_out in shifts:
        db.add(
            EmployeeShift(
                shop_id=shop.id,
                user_id=employees[username].id,
                clock_in=clock_in,
                clock_out=clock_out,
            )
        )


def seed_customers(db: Session, shop: Shop) -> dict[str, ShopCustomer]:
    now = utcnow()
    customers: dict[str, ShopCustomer] = {}
    for index, (name, phone, email, visits) in enumerate(CUSTOMERS):
        customer = ShopCustomer(
            shop_id=shop.id,
            phone=phone,
            name=name,
            email=email,
            visit_count=visits,
            last_visit=now - timedelta(days=index),
        )
        db.add(customer)
        db.flush()
        customers[name] = customer
    return customers


def seed_queue(db: Session, shop: Shop, services: dict[str, ShopService], employees: dict[str, User]) -> Queue:
    now = utcnow().replace(microsecond=0)
    queue = Queue(
        shop_id=shop.id,
        name="Main Queue",
        date=now.replace(hour=0, minute=0, second=0),
        is_active=True,
        accepting_joins=True,
    )
    db.add(queue)
    db.flush()

    completed_rows = [
        ("Andre Wilson", services["Classic Haircut"], "demo_barber_ava", 1, 115, 82),
        ("Mei Alvarez", services["Beard Trim"], "demo_barber_marco", 2, 90, 68),
        ("Nora Patel", services["Skin Fade"], "demo_barber_ava", 3, 58, 22),
    ]
    for name, service, employee_username, position, checked_in_delta, completed_delta in completed_rows:
        completed_at = now - timedelta(minutes=completed_delta)
        started_at = completed_at - timedelta(minutes=service.duration_minutes)
        db.add(
            QueueItem(
                queue_id=queue.id,
                customer_name=name,
                customer_phone=next(phone for customer_name, phone, _, _ in CUSTOMERS if customer_name == name),
                customer_email=next(email for customer_name, _, email, _ in CUSTOMERS if customer_name == name),
                position=position,
                status=QueueStatus.COMPLETED,
                notes="Seeded completed service for analytics.",
                checked_in_at=now - timedelta(minutes=checked_in_delta),
                service_started_at=started_at,
                completed_at=completed_at,
                assigned_employee_id=employees[employee_username].id,
                service_id=service.id,
                service_cost=service.cost,
            )
        )

    live_rows = [
        ("Jordan Lee", services["Classic Haircut"], "demo_barber_ava", QueueStatus.BEING_SERVED, 4, 24, 10),
        ("Priya Shah", services["Skin Fade"], "demo_barber_marco", QueueStatus.WAITING, 5, 18, None),
        ("Ethan Brooks", services["Beard Trim"], "demo_barber_ava", QueueStatus.WAITING, 6, 12, None),
        ("Sofia Chen", services["Hair + Beard Combo"], "demo_barber_marco", QueueStatus.WAITING, 7, 8, None),
        ("Malik Johnson", services["Kids Cut"], None, QueueStatus.WAITING, 8, 3, None),
    ]
    for name, service, employee_username, status, position, checked_in_delta, started_delta in live_rows:
        service_started_at = now - timedelta(minutes=started_delta) if started_delta is not None else None
        db.add(
            QueueItem(
                queue_id=queue.id,
                customer_name=name,
                customer_phone=next(phone for customer_name, phone, _, _ in CUSTOMERS if customer_name == name),
                customer_email=next(email for customer_name, _, email, _ in CUSTOMERS if customer_name == name),
                position=position,
                status=status,
                notes="Walk-in demo customer.",
                checked_in_at=now - timedelta(minutes=checked_in_delta),
                service_started_at=service_started_at,
                assigned_employee_id=employees[employee_username].id if employee_username else None,
                service_id=service.id,
                service_cost=service.cost,
            )
        )

    return queue


def seed_appointments(
    db: Session,
    shop: Shop,
    services: dict[str, ShopService],
    employees: dict[str, User],
    customers: dict[str, ShopCustomer],
) -> None:
    if not table_exists(db, "appointments"):
        return

    today = date.today()
    now = utcnow()
    rows = [
        (
            "Nora Patel",
            services["Hot Towel Shave"],
            employees["demo_barber_tess"],
            datetime.combine(today, time(14, 0)),
            AppointmentStatus.CONFIRMED,
            "Requested Tess if available.",
        ),
        (
            "Andre Wilson",
            services["Hair + Beard Combo"],
            employees["demo_manager"],
            datetime.combine(today, time(16, 30)),
            AppointmentStatus.SCHEDULED,
            "Owner wants this visible in today's appointment list.",
        ),
        (
            "Mei Alvarez",
            services["Skin Fade"],
            employees["demo_barber_marco"],
            datetime.combine(today + timedelta(days=1), time(10, 30)),
            AppointmentStatus.SCHEDULED,
            "Tomorrow morning booking.",
        ),
    ]
    for customer_name, service, employee, start_at, status, notes in rows:
        customer = customers[customer_name]
        db.add(
            Appointment(
                shop_id=shop.id,
                customer_id=customer.id,
                service_id=service.id,
                employee_id=employee.id,
                customer_name=customer.name,
                customer_phone=customer.phone,
                customer_email=customer.email,
                scheduled_start=start_at,
                scheduled_end=start_at + timedelta(minutes=service.duration_minutes),
                status=status,
                service_cost=service.cost,
                notes=notes,
                created_at=now - timedelta(hours=3),
            )
        )


def seed_analytics(db: Session, shop: Shop) -> None:
    today = utcnow().date()
    for offset in range(20, -1, -1):
        day = today - timedelta(days=offset)
        weekday_boost = 1.25 if day.weekday() in (4, 5) else 1.0
        completed = int((18 + (20 - offset) % 7) * weekday_boost)
        cancelled = 1 + (offset % 3 == 0)
        avg_ticket = 39.0 + ((20 - offset) % 5) * 2.5
        db.add(
            DailyAnalytics(
                shop_id=shop.id,
                date=datetime.combine(day, time(0, 0)),
                total_customers=completed + cancelled + 3,
                completed_services=completed,
                cancelled_services=int(cancelled),
                total_revenue=round(completed * avg_ticket, 2),
                avg_wait_time_minutes=round(12 + (offset % 6) * 2.1, 2),
                avg_service_time_minutes=round(28 + (offset % 5) * 1.4, 2),
                peak_hour_start=11 + (offset % 5),
                peak_hour_customers=5 + (offset % 8),
            )
        )


def seed_payments(
    db: Session,
    shop: Shop,
    services: dict[str, ShopService],
    customers: dict[str, ShopCustomer],
    employees: dict[str, User],
) -> None:
    if not (table_exists(db, "invoices") and table_exists(db, "invoice_line_items") and table_exists(db, "payments")):
        return

    now = utcnow()
    rows = [
        ("Nora Patel", services["Skin Fade"], PaymentMethod.CARD, employees["demo_barber_ava"]),
        ("Andre Wilson", services["Classic Haircut"], PaymentMethod.CASH, employees["demo_barber_marco"]),
    ]
    for index, (customer_name, service, method, employee) in enumerate(rows, start=1):
        customer = customers[customer_name]
        subtotal = service.cost
        tax_amount = round(subtotal * 0.13, 2)
        total = round(subtotal + tax_amount, 2)
        invoice = Invoice(
            shop_id=shop.id,
            customer_id=customer.id,
            invoice_number=f"DEMO-{shop.id}-{utcnow().strftime('%Y%m%d')}-{index:02d}",
            status=InvoiceStatus.PAID,
            subtotal=subtotal,
            tax_amount=tax_amount,
            tax_rate=0.13,
            total=total,
            currency="CAD",
            notes="Seeded paid invoice for dashboard testing.",
            paid_at=now - timedelta(hours=index),
            due_date=now + timedelta(days=7),
        )
        db.add(invoice)
        db.flush()
        db.add(
            InvoiceLineItem(
                invoice_id=invoice.id,
                service_id=service.id,
                description=service.name,
                quantity=1,
                unit_price=service.cost,
                total=service.cost,
            )
        )
        db.add(
            Payment(
                shop_id=shop.id,
                invoice_id=invoice.id,
                customer_id=customer.id,
                amount=total,
                tip_amount=round(service.cost * 0.15, 2),
                currency="CAD",
                method=method,
                status=PaymentStatus.COMPLETED,
                processed_by=employee.id,
                processed_at=now - timedelta(hours=index),
                notes="Seeded demo payment.",
            )
        )


def seed_agent_workspace(db: Session, shop: Shop, owner: User, employees: dict[str, User]) -> None:
    if table_exists(db, "shop_policies"):
        policies = [
            ("close_queue", "queue", PolicyMode.REQUIRE_APPROVAL, "Require approval before closing the queue."),
            ("assign_shift", "hr", PolicyMode.REQUIRE_APPROVAL, "Require approval before changing shifts."),
            ("process_refund", "finance", PolicyMode.REQUIRE_APPROVAL, "Require approval before refunds."),
            ("queue_notifications", "queue", PolicyMode.NOTIFY_ONLY, "Notify owner when queue pressure is high."),
        ]
        for key, category, mode, value in policies:
            db.add(
                ShopPolicy(
                    shop_id=shop.id,
                    policy_key=key,
                    category=category,
                    mode=mode,
                    enabled=True,
                    policy_value=value,
                    config={"fixture": "demo_shop"},
                )
            )

    if table_exists(db, "shop_soul"):
        db.add(
            ShopSoul(
                shop_id=shop.id,
                tone="calm, concise, operational",
                upsell_style="suggest bundles only when they reduce repeat visits",
                owner_communication="surface issues first, then propose one clear action",
                personality={
                    "shop_style": "premium neighborhood barbershop",
                    "customer_promises": ["accurate wait times", "friendly check-ins", "clean handoffs"],
                },
                learned_patterns=[
                    "Friday afternoons run 25-35% busier than weekday mornings.",
                    "Ava is fastest on classic cuts; Marco handles longer fade services.",
                ],
                recent_decisions=[
                    "Keep walk-ins open while two or more staff are clocked in.",
                    "Ask owner before extending operating hours.",
                ],
                open_items=["Review Saturday staffing before lunch rush."],
                summary=(
                    "ZeroQ Demo Cuts is a practical barbershop fixture for testing the owner cockpit, "
                    "customer receptionist, and employee queue flows."
                ),
                tier_scope="premium",
                rolling_window_days=90,
                last_evolved_at=utcnow() - timedelta(days=1),
            )
        )

    if table_exists(db, "soul_learnings"):
        learnings = [
            ("pattern", "Customers asking for skin fades usually accept the hair + beard combo when wait is under 25 minutes."),
            ("owner_preference", "Owner prefers queue risk called out before finance summaries in the morning."),
        ]
        for category, content in learnings:
            db.add(
                SoulLearning(
                    shop_id=shop.id,
                    source="demo_seed",
                    category=category,
                    content=content,
                    confidence_score=0.82,
                    evidence={"fixture": "demo_shop"},
                    graduated=True,
                )
            )

    if table_exists(db, "commitments"):
        db.add(
            Commitment(
                shop_id=shop.id,
                made_by="supervisor",
                commitment="Check whether Saturday needs an extra barber before the noon rush.",
                due_at=utcnow() + timedelta(hours=2),
                trigger_if_missed="Notify the owner that staffing review is overdue.",
                status="pending",
                action_payload={"suggested_action": "review_staffing", "fixture": "demo_shop"},
                detected_from={"source": "demo_seed"},
            )
        )

    if table_exists(db, "agent_notifications"):
        notifications = [
            (
                "queue_pressure",
                "Queue is building",
                "Four customers are active and two staff are currently serving. Estimated wait is suitable for normal operations.",
                "info",
                {"queue_length": 5, "fixture": "demo_shop"},
                utcnow() - timedelta(minutes=8),
            ),
            (
                "finance_summary",
                "Revenue pacing is healthy",
                "Today has seeded payments and recent completed services for finance-agent chart testing.",
                "success",
                {"today_revenue": 412.25, "fixture": "demo_shop"},
                utcnow() - timedelta(minutes=18),
            ),
            (
                "hr_staffing",
                "Saturday staffing review due",
                "The HR agent has a pending shift proposal ready for owner approval.",
                "warning",
                {"employee_id": employees["demo_barber_tess"].id, "fixture": "demo_shop"},
                utcnow() - timedelta(minutes=24),
            ),
        ]
        for notification_type, title, message, severity, payload, created_at in notifications:
            db.add(
                AgentNotification(
                    shop_id=shop.id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    severity=severity,
                    status=NotificationStatus.UNREAD,
                    payload=payload,
                    created_at=created_at,
                )
            )

    if table_exists(db, "approval_requests"):
        tomorrow = date.today() + timedelta(days=1)
        action_id = "demo-assign-tess-saturday-shift"
        request_payload = {
            "action_id": action_id,
            "action": "assign_shift",
            "shop_id": shop.id,
            "title": "Assign Tess to cover the next lunch rush",
            "details": {
                "user_id": employees["demo_barber_tess"].id,
                "employee_username": employees["demo_barber_tess"].username,
                "date": tomorrow.isoformat(),
                "start_time": "12:00:00",
                "end_time": "18:00:00",
                "reason": "Projected walk-in demand is above the two-barber comfort range.",
                "urgency": "normal",
            },
            "rationale": "The queue pattern suggests an extra barber will reduce wait spikes.",
            "expected_impact": "Adds six hours of coverage for the next rush window.",
            "risk_level": "medium",
        }
        db.add(
            ApprovalRequest(
                external_action_id=action_id,
                shop_id=shop.id,
                requested_by_user_id=owner.id,
                requested_by_agent="hr",
                action_type="assign_shift",
                title="Assign Tess to cover the next lunch rush",
                rationale=request_payload["rationale"],
                expected_impact=request_payload["expected_impact"],
                urgency="normal",
                status=ApprovalStatus.PENDING,
                request_payload=request_payload,
                expires_at=utcnow() + timedelta(days=2),
            )
        )


def seed_operating_hours(db: Session, shop: Shop) -> None:
    if not table_exists(db, "shop_operating_hours"):
        return
    db.add(
        ShopOperatingHours(
            shop_id=shop.id,
            open_time=time(9, 0),
            close_time=time(18, 0),
            timezone="America/Toronto",
            auto_open_queue=True,
            auto_close_queue=True,
            pre_close_buffer_minutes=20,
            auto_lock_joins=True,
            operating_days=[0, 1, 2, 3, 4, 5],
        )
    )


def run_seed(*, reset: bool) -> dict[str, object]:
    db = SessionLocal()
    try:
        require_tables(
            db,
            [
                "users",
                "shops",
                "shop_services",
                "queues",
                "queue_items",
                "shop_employees",
                "employee_shifts",
                "daily_analytics",
                "shop_customers",
            ],
        )

        admin = get_or_create_user(db, ADMIN)
        owner = get_or_create_user(db, OWNER)
        shop = get_or_create_shop(db, owner)
        db.flush()

        if reset:
            reset_demo_rows(db, shop)

        services = seed_shop_services(db, shop)
        employees = seed_employees(db, shop, owner)
        seed_shifts(db, shop, employees)
        customers = seed_customers(db, shop)
        queue = seed_queue(db, shop, services, employees)
        seed_appointments(db, shop, services, employees, customers)
        seed_analytics(db, shop)
        seed_payments(db, shop, services, customers, employees)
        seed_agent_workspace(db, shop, owner, employees)
        seed_operating_hours(db, shop)

        db.commit()

        return {
            "shop_id": shop.id,
            "shop_name": shop.name,
            "shop_slug": shop.slug,
            "queue_id": queue.id,
            "admin_id": admin.id,
            "owner_id": owner.id,
            "employees": {username: employee.id for username, employee in employees.items()},
            "services": len(services),
            "customers": len(customers),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    args = parse_args()
    summary = run_seed(reset=not args.no_reset)

    print("Demo shop seed complete.")
    print(f"Shop: {summary['shop_name']} (id={summary['shop_id']}, slug={summary['shop_slug']})")
    print(f"Queue: id={summary['queue_id']}")
    print("")
    print("Demo credentials:")
    print(f"  Admin:    {ADMIN.username} / {DEMO_PASSWORD}")
    print(f"  Owner:    {OWNER.username} / {DEMO_PASSWORD}")
    for spec in EMPLOYEES:
        print(f"  {spec.role.value.title():<8} {spec.username} / {DEMO_PASSWORD}")
    print("")
    print("Local test URLs:")
    print("  Frontend:     http://localhost:3000")
    print("  Owner inbox:  http://localhost:3000/agent-inbox")
    print(f"  Public shop:  http://localhost:3000/shop-ai/{summary['shop_id']}")
    print(f"  Queue board:  http://localhost:3000/queue/{summary['shop_id']}")
    print(f"  Display:      http://localhost:3000/display/{summary['shop_id']}")


if __name__ == "__main__":
    main()
