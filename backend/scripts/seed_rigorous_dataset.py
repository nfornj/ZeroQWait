#!/usr/bin/env python3
"""
Rigorous realistic dataset generator for ZeroQwait.

What it creates:
- Realistic owners (many owners, some owning multiple shops)
- 500 shops (configurable)
- Services per shop
- Active queue per shop
- Employees per shop + employee shifts
- Queue history + daily analytics for past N years
- Shop customer profiles
- Credentials export text file with owner login for each shop

Safety:
- Supports target environments: current, test, prod
- Requires --confirm-prod for prod target

Usage examples:
  python backend/scripts/seed_rigorous_dataset.py --target current --shops 500 --years 3 \
      --credentials-file backend/shop_login_info_test.txt

  python backend/scripts/seed_rigorous_dataset.py --target prod --confirm-prod --shops 500 --years 3 \
      --credentials-file backend/shop_login_info_prod.txt
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import os
import random
import string
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from faker import Faker
from passlib.context import CryptContext
from slugify import slugify
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

# Import ORM models
from modules.auth.models import SubscriptionTier, User, UserRole
from modules.employees.models import EmployeeShift, ShopEmployee
from modules.queues.models import Queue, QueueItem, QueueStatus
from modules.shops.models import DailyAnalytics, Shop, ShopCustomer, ShopService

fake = Faker("en_CA")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


SHOP_TEMPLATES: List[Dict[str, object]] = [
    {
        "shop_type": "barber",
        "label": "Barber Shop",
        "services": [
            ("Classic Haircut", 35.0, 30),
            ("Skin Fade", 42.0, 40),
            ("Beard Trim", 24.0, 20),
            ("Hot Towel Shave", 38.0, 35),
            ("Hair + Beard Combo", 56.0, 55),
        ],
        "staff_range": (3, 8),
        "avg_service_min": 32,
    },
    {
        "shop_type": "salon",
        "label": "Hair Salon",
        "services": [
            ("Women's Cut", 65.0, 45),
            ("Men's Cut", 45.0, 35),
            ("Blowout", 48.0, 40),
            ("Color Root Touch-up", 95.0, 85),
            ("Balayage", 180.0, 150),
            ("Keratin Treatment", 220.0, 180),
        ],
        "staff_range": (4, 12),
        "avg_service_min": 55,
    },
    {
        "shop_type": "spa",
        "label": "Spa and Wellness",
        "services": [
            ("Swedish Massage", 110.0, 60),
            ("Deep Tissue Massage", 135.0, 75),
            ("Custom Facial", 120.0, 70),
            ("Manicure", 45.0, 35),
            ("Pedicure", 62.0, 50),
        ],
        "staff_range": (3, 10),
        "avg_service_min": 58,
    },
    {
        "shop_type": "clinic",
        "label": "Medical Clinic",
        "services": [
            ("General Consultation", 95.0, 25),
            ("Follow-up Visit", 70.0, 20),
            ("Minor Procedure", 180.0, 45),
            ("Vaccination", 35.0, 12),
            ("Lab Review", 52.0, 18),
        ],
        "staff_range": (5, 16),
        "avg_service_min": 24,
    },
    {
        "shop_type": "dental",
        "label": "Dental Office",
        "services": [
            ("Dental Checkup", 110.0, 30),
            ("Cleaning", 140.0, 45),
            ("Filling", 210.0, 55),
            ("Whitening", 260.0, 75),
            ("Emergency Visit", 185.0, 40),
        ],
        "staff_range": (4, 14),
        "avg_service_min": 38,
    },
    {
        "shop_type": "auto_repair",
        "label": "Auto Repair",
        "services": [
            ("Oil Change", 75.0, 30),
            ("Brake Inspection", 95.0, 40),
            ("Tire Rotation", 60.0, 30),
            ("Diagnostic Scan", 120.0, 50),
            ("Battery Replacement", 145.0, 45),
        ],
        "staff_range": (3, 12),
        "avg_service_min": 44,
    },
]

CANADA_LOCATIONS: List[Tuple[str, str, str]] = [
    ("Oshawa", "Ontario", "Canada"),
    ("Toronto", "Ontario", "Canada"),
    ("Mississauga", "Ontario", "Canada"),
    ("Brampton", "Ontario", "Canada"),
    ("Scarborough", "Ontario", "Canada"),
    ("Markham", "Ontario", "Canada"),
    ("Hamilton", "Ontario", "Canada"),
    ("London", "Ontario", "Canada"),
    ("Ottawa", "Ontario", "Canada"),
    ("Kitchener", "Ontario", "Canada"),
    ("Vaughan", "Ontario", "Canada"),
    ("Montreal", "Quebec", "Canada"),
    ("Laval", "Quebec", "Canada"),
    ("Quebec City", "Quebec", "Canada"),
    ("Longueuil", "Quebec", "Canada"),
    ("Calgary", "Alberta", "Canada"),
    ("Edmonton", "Alberta", "Canada"),
    ("Red Deer", "Alberta", "Canada"),
    ("Vancouver", "British Columbia", "Canada"),
    ("Surrey", "British Columbia", "Canada"),
    ("Burnaby", "British Columbia", "Canada"),
    ("Victoria", "British Columbia", "Canada"),
    ("Winnipeg", "Manitoba", "Canada"),
    ("Halifax", "Nova Scotia", "Canada"),
    ("Saskatoon", "Saskatchewan", "Canada"),
    ("Regina", "Saskatchewan", "Canada"),
    ("St. John's", "Newfoundland and Labrador", "Canada"),
]

STREET_SUFFIXES = [
    "Avenue",
    "Street",
    "Road",
    "Boulevard",
    "Drive",
    "Lane",
    "Way",
    "Court",
]

SHOP_NAME_PREFIXES = [
    "North",
    "Prime",
    "Urban",
    "Downtown",
    "Lakeside",
    "Royal",
    "Maple",
    "Bright",
    "True",
    "Modern",
    "Pioneer",
    "Metro",
    "Harbor",
]

SHOP_NAME_CORES = [
    "Care",
    "Studio",
    "Works",
    "Point",
    "Select",
    "Hub",
    "Collective",
    "Group",
    "Center",
    "House",
    "Experts",
    "Solutions",
]


@dataclass
class OwnerCred:
    user_id: int
    username: str
    email: str
    password: str


@dataclass(frozen=True)
class ShopHistoryPayload:
    shop_id: int
    shop_number: int


def recommended_history_workers() -> int:
    cpu_count = os.cpu_count() or 1
    return max(1, min(8, cpu_count))


def chunked_items(items: List[ShopHistoryPayload], chunk_size: int) -> List[List[ShopHistoryPayload]]:
    return [items[idx : idx + chunk_size] for idx in range(0, len(items), chunk_size)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed rigorous realistic test/prod datasets")
    parser.add_argument("--target", choices=["current", "test", "prod"], default="current")
    parser.add_argument("--db-url", default=None, help="Explicit SQLAlchemy DB URL override")
    parser.add_argument("--shops", type=int, default=500)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--credentials-file", default="backend/shop_login_info_generated.txt")
    parser.add_argument("--confirm-prod", action="store_true")
    parser.add_argument("--detailed-days", type=int, default=365, help="Days with raw queue-item history")
    parser.add_argument(
        "--if-less-than-shops",
        type=int,
        default=100,
        help="Only seed when existing shops are below this count",
    )
    parser.add_argument(
        "--history-workers",
        type=int,
        default=recommended_history_workers(),
        help="Worker processes used for heavy per-shop history generation",
    )
    parser.add_argument(
        "--history-batch-size",
        type=int,
        default=8,
        help="Number of shops assigned to each history-generation task",
    )
    return parser.parse_args()


def build_db_url(target: str, explicit_url: Optional[str]) -> str:
    if explicit_url:
        return explicit_url

    def g(name: str, default: Optional[str] = None) -> Optional[str]:
        return os.getenv(name, default)

    if target == "test":
        url = g("TEST_DATABASE_URL")
        if url:
            return url
        host = g("TEST_DB_HOST", g("DB_HOST", "localhost"))
        port = g("TEST_DB_PORT", g("DB_PORT", "5432"))
        name = g("TEST_DB_NAME", g("DB_NAME", "zeroqwait"))
        user = g("TEST_DB_USER", g("DB_USER", "postgres"))
        pwd = g("TEST_DB_PASSWORD", g("DB_PASSWORD", "password"))
        return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"

    if target == "prod":
        url = g("PROD_DATABASE_URL")
        if url:
            return url
        host = g("PROD_DB_HOST", g("DB_HOST", "localhost"))
        port = g("PROD_DB_PORT", g("DB_PORT", "5432"))
        name = g("PROD_DB_NAME", g("DB_NAME", "zeroqwait"))
        user = g("PROD_DB_USER", g("DB_USER", "postgres"))
        pwd = g("PROD_DB_PASSWORD", g("DB_PASSWORD", "password"))
        return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"

    # current
    url = g("DATABASE_URL")
    if url:
        return url
    host = g("DB_HOST", "localhost")
    port = g("DB_PORT", "5432")
    name = g("DB_NAME", "zeroqwait")
    user = g("DB_USER", "postgres")
    pwd = g("DB_PASSWORD", "password")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"


def hash_password(raw_password: str) -> str:
    return pwd_context.hash(raw_password)


def safe_slug(db: Session, shop_name: str) -> str:
    base = slugify(shop_name)[:55]
    slug = base
    i = 2
    while db.query(Shop.id).filter(Shop.slug == slug).first() is not None:
        slug = f"{base}-{i}"
        i += 1
    return slug


def random_phone() -> str:
    return f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"


def random_postal_code(country: str) -> str:
    if country == "Canada":
        letters = string.ascii_uppercase
        return (
            f"{random.choice(letters)}{random.randint(0,9)}{random.choice(letters)} "
            f"{random.randint(0,9)}{random.choice(letters)}{random.randint(0,9)}"
        )
    return f"{random.randint(10000, 99999)}"


def random_address(city: str) -> str:
    number = random.randint(10, 9999)
    street = fake.last_name()
    suffix = random.choice(STREET_SUFFIXES)
    unit = random.choice(["", "", f"Unit {random.randint(1, 150)}"])
    out = f"{number} {street} {suffix}"
    if unit:
        out = f"{out}, {unit}"
    return out


def weighted_shop_template() -> Dict[str, object]:
    weights = [0.23, 0.22, 0.12, 0.14, 0.11, 0.18]
    return random.choices(SHOP_TEMPLATES, weights=weights, k=1)[0]


def create_owner(db: Session, owner_idx: int, created_at: datetime) -> OwnerCred:
    first = fake.first_name().lower()
    last = fake.last_name().lower().replace("'", "")
    username = f"owner_{first}_{last}_{owner_idx}"
    email = f"{username}@example-zeroqwait.com"
    password = f"Owner!{owner_idx:04d}{random.randint(100,999)}"

    owner = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        role=UserRole.SHOP_OWNER,
        is_active=True,
        subscription_tier=random.choices(
            [SubscriptionTier.FREE, SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE],
            weights=[0.7, 0.23, 0.07],
            k=1,
        )[0],
        created_at=created_at,
    )
    db.add(owner)
    db.flush()

    return OwnerCred(user_id=owner.id, username=username, email=email, password=password)


def create_employee_user(db: Session, shop_id: int, idx: int, created_at: datetime) -> Tuple[User, str]:
    first = fake.first_name().lower()
    last = fake.last_name().lower().replace("'", "")
    username = f"emp_{shop_id}_{idx}_{first}_{last}"[:60]
    email = f"{username}@example-zeroqwait.com"
    password = f"Emp!{shop_id:04d}{idx:02d}{random.randint(10,99)}"

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        role=UserRole.EMPLOYEE,
        is_active=True,
        subscription_tier=SubscriptionTier.FREE,
        created_at=created_at,
    )
    db.add(user)
    db.flush()
    return user, password


def create_shop_name(template_label: str, city: str) -> str:
    prefix = random.choice(SHOP_NAME_PREFIXES)
    core = random.choice(SHOP_NAME_CORES)
    city_part = city.split()[0]
    return f"{prefix} {city_part} {core} {template_label}"


def sample_customer_name() -> str:
    return fake.name()


def generate_for_shop(
    db: Session,
    shop: Shop,
    queue: Queue,
    services: List[ShopService],
    employee_user_ids: List[int],
    years: int,
    detailed_days: int,
) -> Dict[str, int]:
    today = date.today()
    start_day = today - timedelta(days=years * 365)
    detailed_cutoff = today - timedelta(days=detailed_days)

    queue_items_buffer: List[QueueItem] = []
    analytics_buffer: List[DailyAnalytics] = []
    shifts_buffer: List[EmployeeShift] = []
    customers_seen: Dict[str, Dict[str, object]] = {}

    total_queue_items = 0
    total_analytics = 0
    total_shifts = 0

    service_wait_baseline = max(4, int(shop.average_service_time * 0.35))

    day = start_day
    while day <= today:
        is_weekend = day.weekday() >= 5

        # Growth trend over 3 years, with seasonality.
        progress = (day - start_day).days / max(1, (today - start_day).days)
        growth = 0.65 + (0.55 * progress)
        seasonality = 1.0
        if day.month in (6, 7, 8, 12):
            seasonality += 0.18

        base = random.randint(6, 22)
        if is_weekend:
            base += random.randint(4, 14)

        daily_customers = max(2, int(base * growth * seasonality))

        # One daily analytics row for all 3 years.
        completed_count = 0
        cancelled_count = 0
        revenue = 0.0
        wait_sum = 0
        service_sum = 0

        # Raw queue history for recent period, plus sparse monthly historical snapshots.
        generate_raw = day >= detailed_cutoff or day.day in (1, 15)

        for pos in range(1, daily_customers + 1):
            service = random.choice(services)
            status_roll = random.random()
            if day == today and status_roll < 0.06:
                status = QueueStatus.WAITING
            elif day == today and status_roll < 0.10:
                status = QueueStatus.BEING_SERVED
            elif status_roll < 0.16:
                status = QueueStatus.CANCELLED
            else:
                status = QueueStatus.COMPLETED

            hour = random.randint(8, 19)
            minute = random.randint(0, 59)
            checked_in_at = datetime.combine(day, time(hour=hour, minute=minute))

            wait_minutes = max(0, int(random.gauss(service_wait_baseline, 7)))
            service_minutes = max(8, int(random.gauss(service.duration_minutes, max(4, service.duration_minutes * 0.15))))

            service_started_at = None
            completed_at = None
            assigned_employee = random.choice(employee_user_ids) if employee_user_ids else None

            if status in (QueueStatus.BEING_SERVED, QueueStatus.COMPLETED):
                service_started_at = checked_in_at + timedelta(minutes=wait_minutes)
            if status == QueueStatus.COMPLETED:
                completed_at = service_started_at + timedelta(minutes=service_minutes)  # type: ignore[arg-type]

            # Metrics for analytics
            if status == QueueStatus.COMPLETED:
                completed_count += 1
                revenue += service.cost
                wait_sum += wait_minutes
                service_sum += service_minutes
            elif status == QueueStatus.CANCELLED:
                cancelled_count += 1

            if generate_raw:
                customer_name = sample_customer_name()
                customer_phone = random_phone()

                queue_items_buffer.append(
                    QueueItem(
                        queue_id=queue.id,
                        user_id=None,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        customer_email=fake.email(),
                        position=pos,
                        status=status,
                        notes=random.choice(["", "", "Prefers quick service", "Follow-up customer"]),
                        checked_in_at=checked_in_at,
                        service_started_at=service_started_at,
                        completed_at=completed_at,
                        assigned_employee_id=assigned_employee,
                        service_id=service.id,
                        service_cost=service.cost,
                    )
                )
                total_queue_items += 1

                # Build customer profile map (for ShopCustomer table)
                profile = customers_seen.get(customer_phone)
                if profile is None:
                    customers_seen[customer_phone] = {
                        "name": customer_name,
                        "email": fake.email(),
                        "visit_count": 1,
                        "last_visit": checked_in_at,
                    }
                else:
                    profile["visit_count"] = int(profile["visit_count"]) + 1
                    if checked_in_at > profile["last_visit"]:
                        profile["last_visit"] = checked_in_at

        avg_wait = (wait_sum / completed_count) if completed_count else 0.0
        avg_service = (service_sum / completed_count) if completed_count else float(shop.average_service_time)

        peak_hour_start = random.randint(10, 17)
        peak_hour_customers = max(1, int(daily_customers * random.uniform(0.2, 0.42)))

        analytics_buffer.append(
            DailyAnalytics(
                shop_id=shop.id,
                date=datetime.combine(day, time(0, 0)),
                total_customers=daily_customers,
                completed_services=completed_count,
                cancelled_services=cancelled_count,
                total_revenue=round(revenue, 2),
                avg_wait_time_minutes=round(avg_wait, 2),
                avg_service_time_minutes=round(avg_service, 2),
                peak_hour_start=peak_hour_start,
                peak_hour_customers=peak_hour_customers,
            )
        )
        total_analytics += 1

        # Shift history (sparse but realistic) across full window
        # About 70% of employees work on weekdays, 45% on weekends.
        shift_prob = 0.70 if not is_weekend else 0.45
        for emp_id in employee_user_ids:
            if random.random() <= shift_prob:
                start_hour = random.randint(8, 11)
                shift_len = random.randint(6, 9)
                clock_in = datetime.combine(day, time(start_hour, random.randint(0, 30)))
                clock_out = clock_in + timedelta(hours=shift_len, minutes=random.randint(0, 40))
                shifts_buffer.append(
                    EmployeeShift(
                        user_id=emp_id,
                        shop_id=shop.id,
                        clock_in=clock_in,
                        clock_out=clock_out,
                    )
                )
                total_shifts += 1

        # Flush in chunks to keep memory under control
        if len(queue_items_buffer) >= 5000:
            db.bulk_save_objects(queue_items_buffer)
            queue_items_buffer.clear()
            db.commit()

        if len(analytics_buffer) >= 3000:
            db.bulk_save_objects(analytics_buffer)
            analytics_buffer.clear()
            db.commit()

        if len(shifts_buffer) >= 5000:
            db.bulk_save_objects(shifts_buffer)
            shifts_buffer.clear()
            db.commit()

        day += timedelta(days=1)

    if queue_items_buffer:
        db.bulk_save_objects(queue_items_buffer)
    if analytics_buffer:
        db.bulk_save_objects(analytics_buffer)
    if shifts_buffer:
        db.bulk_save_objects(shifts_buffer)
    db.commit()

    # Persist ShopCustomer summary entries.
    if customers_seen:
        customer_rows = []
        for phone, profile in customers_seen.items():
            customer_rows.append(
                ShopCustomer(
                    shop_id=shop.id,
                    phone=phone,
                    name=str(profile["name"]),
                    email=str(profile["email"]),
                    visit_count=int(profile["visit_count"]),
                    last_visit=profile["last_visit"],
                    created_at=datetime.now(timezone.utc),
                )
            )
        db.bulk_save_objects(customer_rows)
        db.commit()

    return {
        "queue_items": total_queue_items,
        "analytics": total_analytics,
        "shifts": total_shifts,
        "shop_customers": len(customers_seen),
    }


def generate_history_batch(
    db_url: str,
    payloads: List[ShopHistoryPayload],
    years: int,
    detailed_days: int,
    seed: int,
) -> Dict[str, int]:
    random.seed(seed)
    Faker.seed(seed)

    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db: Session = SessionLocal()

    totals = {
        "shops": 0,
        "queue_items": 0,
        "analytics": 0,
        "shifts": 0,
        "shop_customers": 0,
    }

    try:
        for payload in payloads:
            shop = db.query(Shop).filter(Shop.id == payload.shop_id).one()
            queue = db.query(Queue).filter(Queue.shop_id == payload.shop_id).order_by(Queue.id.desc()).first()
            services = db.query(ShopService).filter(ShopService.shop_id == payload.shop_id).all()
            employee_user_ids = [
                user_id
                for (user_id,) in db.query(ShopEmployee.user_id).filter(ShopEmployee.shop_id == payload.shop_id).all()
            ]

            if queue is None or not services:
                raise RuntimeError(f"Missing queue/services for shop_id={payload.shop_id}")

            stats = generate_for_shop(
                db=db,
                shop=shop,
                queue=queue,
                services=services,
                employee_user_ids=employee_user_ids,
                years=years,
                detailed_days=detailed_days,
            )

            totals["shops"] += 1
            totals["queue_items"] += stats["queue_items"]
            totals["analytics"] += stats["analytics"]
            totals["shifts"] += stats["shifts"]
            totals["shop_customers"] += stats["shop_customers"]
            db.expunge_all()

        return totals
    finally:
        db.close()
        engine.dispose()


def write_credentials_file(path: Path, rows: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("# ZeroQwait Rigorous Dataset Shop Login Export\n")
        f.write(f"# Generated at: {datetime.now(timezone.utc).isoformat()}\n")
        f.write("# Format: shop_id | shop_name | city | owner_username | owner_email | owner_password | slug\n\n")
        for line in rows:
            f.write(line)
            f.write("\n")


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    Faker.seed(args.seed)

    if args.target == "prod" and not args.confirm_prod:
        raise SystemExit("Refusing to run against prod without --confirm-prod")

    db_url = build_db_url(args.target, args.db_url)

    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    db: Session = SessionLocal()

    try:
        current_shops = db.query(func.count(Shop.id)).scalar() or 0
        current_users = db.query(func.count(User.id)).scalar() or 0
        current_queue_items = db.query(func.count(QueueItem.id)).scalar() or 0

        print(f"Current counts -> shops={current_shops}, users={current_users}, queue_items={current_queue_items}")

        if current_shops >= args.if_less_than_shops:
            print(
                f"Skipping seed: existing shops ({current_shops}) >= threshold ({args.if_less_than_shops})."
            )
            return

        print(
            f"Starting dataset generation: shops={args.shops}, years={args.years}, "
            f"detailed_days={args.detailed_days}, target={args.target}, "
            f"history_workers={args.history_workers}, history_batch_size={args.history_batch_size}"
        )

        # Determine owner pool size so many owners have multiple shops.
        # Example for 500 shops -> around 180 owners.
        owner_count = max(20, int(args.shops * 0.36))
        shops_per_owner = [1] * owner_count

        # Distribute remaining shops to create multi-shop ownership.
        remaining = args.shops - owner_count
        idx = 0
        while remaining > 0:
            add = random.choices([0, 1, 2], weights=[0.4, 0.45, 0.15], k=1)[0]
            if add > 0:
                shops_per_owner[idx % owner_count] += add
                remaining -= add
            idx += 1

        # Trim if we overshot.
        while sum(shops_per_owner) > args.shops:
            for i in range(len(shops_per_owner)):
                if shops_per_owner[i] > 1 and sum(shops_per_owner) > args.shops:
                    shops_per_owner[i] -= 1

        owners: List[OwnerCred] = []
        owner_shop_plan: List[int] = []

        start_owner_created = datetime.now(timezone.utc) - timedelta(days=args.years * 365)

        for owner_idx in range(owner_count):
            created_at = start_owner_created + timedelta(days=random.randint(0, args.years * 365))
            cred = create_owner(db, owner_idx + 1, created_at)
            owners.append(cred)
            owner_shop_plan.append(shops_per_owner[owner_idx])

        db.commit()

        credentials_lines: List[str] = []
        total_queue_items = 0
        total_analytics = 0
        total_shifts = 0
        total_customers = 0
        history_payloads: List[ShopHistoryPayload] = []

        shop_counter = 0

        for owner_idx, owner in enumerate(owners):
            for _ in range(owner_shop_plan[owner_idx]):
                if shop_counter >= args.shops:
                    break

                template = weighted_shop_template()
                city, state, country = random.choice(CANADA_LOCATIONS)

                created_at = datetime.now(timezone.utc) - timedelta(days=random.randint(30, args.years * 365))
                shop_name = create_shop_name(str(template["label"]), city)
                slug = safe_slug(db, shop_name)

                shop = Shop(
                    owner_id=owner.user_id,
                    name=shop_name,
                    description=fake.catch_phrase(),
                    shop_type=str(template["shop_type"]),
                    address=random_address(city),
                    city=city,
                    state=state,
                    zip_code=random_postal_code(country),
                    country=country,
                    phone=random_phone(),
                    email=f"{slug}@example-zeroqwait.com",
                    website=f"https://{slug}.example-zeroqwait.com",
                    average_service_time=int(template["avg_service_min"]),
                    slug=slug,
                    latitude=float(fake.latitude()),
                    longitude=float(fake.longitude()),
                    is_active=True,
                    created_at=created_at,
                    primary_color=random.choice(["#6A1B9A", "#AD1457", "#283593", "#00897B", "#1565C0"]),
                    secondary_color=random.choice(["#E1BEE7", "#F8BBD0", "#C5CAE9", "#B2DFDB", "#BBDEFB"]),
                )
                db.add(shop)
                db.flush()

                # Shop services
                services: List[ShopService] = []
                for service_name, base_cost, duration in template["services"]:  # type: ignore[index]
                    price = round(max(10.0, random.gauss(float(base_cost), float(base_cost) * 0.12)), 2)
                    dmin = max(8, int(random.gauss(float(duration), max(3.0, float(duration) * 0.12))))
                    svc = ShopService(
                        shop_id=shop.id,
                        name=str(service_name),
                        description=fake.sentence(nb_words=10),
                        duration_minutes=dmin,
                        cost=price,
                        currency="USD",
                        is_active=True,
                        created_at=created_at,
                    )
                    db.add(svc)
                    services.append(svc)
                db.flush()

                queue = Queue(
                    shop_id=shop.id,
                    name="Main Queue",
                    date=created_at,
                    is_active=True,
                )
                db.add(queue)
                db.flush()

                # Employees
                low_staff, high_staff = template["staff_range"]  # type: ignore[index]
                staff_count = random.randint(int(low_staff), int(high_staff))
                employee_user_ids: List[int] = []

                for eidx in range(1, staff_count + 1):
                    emp_created = created_at + timedelta(days=random.randint(0, 120))
                    emp_user, _ = create_employee_user(db, shop.id, eidx, emp_created)
                    employee_user_ids.append(emp_user.id)
                    db.add(
                        ShopEmployee(
                            shop_id=shop.id,
                            user_id=emp_user.id,
                            created_at=emp_created,
                            created_by=owner.user_id,
                            is_active=True,
                            employee_code=f"EMP-{shop.id:04d}-{eidx:02d}",
                        )
                    )

                db.commit()

                credentials_lines.append(
                    f"{shop.id} | {shop.name} | {shop.city}, {shop.state} | "
                    f"{owner.username} | {owner.email} | {owner.password} | {shop.slug}"
                )

                shop_counter += 1
                history_payloads.append(ShopHistoryPayload(shop_id=shop.id, shop_number=shop_counter))
                if shop_counter % 10 == 0:
                    print(f"Prepared base data: {shop_counter}/{args.shops} shops")

            if shop_counter >= args.shops:
                break

        history_batches = chunked_items(history_payloads, max(1, args.history_batch_size))
        completed_history_shops = 0

        if args.history_workers <= 1:
            for batch_idx, payload_batch in enumerate(history_batches, start=1):
                result = generate_history_batch(
                    db_url=db_url,
                    payloads=payload_batch,
                    years=args.years,
                    detailed_days=args.detailed_days,
                    seed=args.seed + batch_idx,
                )
                completed_history_shops += result["shops"]
                total_queue_items += result["queue_items"]
                total_analytics += result["analytics"]
                total_shifts += result["shifts"]
                total_customers += result["shop_customers"]
                print(
                    f"History progress: {completed_history_shops}/{len(history_payloads)} shops | "
                    f"queue_items={total_queue_items} analytics={total_analytics} shifts={total_shifts}"
                )
        else:
            with ProcessPoolExecutor(
                max_workers=args.history_workers,
                mp_context=multiprocessing.get_context("spawn"),
            ) as executor:
                future_map = {
                    executor.submit(
                        generate_history_batch,
                        db_url,
                        payload_batch,
                        args.years,
                        args.detailed_days,
                        args.seed + batch_idx,
                    ): len(payload_batch)
                    for batch_idx, payload_batch in enumerate(history_batches, start=1)
                }

                for future in as_completed(future_map):
                    result = future.result()
                    completed_history_shops += result["shops"]
                    total_queue_items += result["queue_items"]
                    total_analytics += result["analytics"]
                    total_shifts += result["shifts"]
                    total_customers += result["shop_customers"]
                    print(
                        f"History progress: {completed_history_shops}/{len(history_payloads)} shops | "
                        f"queue_items={total_queue_items} analytics={total_analytics} shifts={total_shifts}"
                    )

        creds_path = Path(args.credentials_file)
        write_credentials_file(creds_path, credentials_lines)

        final_shops = db.query(func.count(Shop.id)).scalar() or 0
        final_users = db.query(func.count(User.id)).scalar() or 0

        print("Generation complete.")
        print(f"Created shops: {shop_counter}")
        print(f"Created queue history rows: {total_queue_items}")
        print(f"Created analytics rows: {total_analytics}")
        print(f"Created employee shifts: {total_shifts}")
        print(f"Created customer profiles: {total_customers}")
        print(f"Current totals -> shops={final_shops}, users={final_users}")
        print(f"Credentials file: {creds_path}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
