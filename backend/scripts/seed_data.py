#!/usr/bin/env python3
"""
ZeroQwait Seed Data Generator
==============================
Creates realistic shops, employees, services, queues, queue items,
daily analytics, and customers across multiple cities and categories.

Idempotent: checks existing data before inserting.

Usage:
  python seed_data.py                  # Local dev DB
    DB_HOST=postgres DB_NAME=zeroqwait DB_USER=zeroqwait DB_PASSWORD=xxx python seed_data.py
"""

import os
import sys
import random
from datetime import datetime, timedelta
from passlib.context import CryptContext
import re

# --- Ensure imports work ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine
from modules.auth.models import User, UserRole, SubscriptionTier
from modules.shops.models import Shop, ShopService, DailyAnalytics, ShopCloseDay, ShopCustomer
from modules.queues.models import Queue, QueueItem, QueueStatus
from modules.employees.models import ShopEmployee, EmployeeShift
from modules.agent.models import CategoryAlias, LearnedSynonym, AgentKnowledge

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DEFAULT_PASSWORD = pwd_context.hash("Test1234!")

# ═══════════════════════════════════════════════
# SEED DATA DEFINITIONS
# ═══════════════════════════════════════════════

CITIES = [
    {"city": "Toronto", "state": "ON", "zip": "M5V 3L9", "country": "Canada", "lat": 43.6532, "lng": -79.3832},
    {"city": "Oshawa", "state": "ON", "zip": "L1H 7K4", "country": "Canada", "lat": 43.8971, "lng": -78.8658},
    {"city": "Mississauga", "state": "ON", "zip": "L5B 3C2", "country": "Canada", "lat": 43.5890, "lng": -79.6441},
    {"city": "Brampton", "state": "ON", "zip": "L6Y 1N2", "country": "Canada", "lat": 43.7315, "lng": -79.7624},
    {"city": "Hamilton", "state": "ON", "zip": "L8P 4S5", "country": "Canada", "lat": 43.2557, "lng": -79.8711},
    {"city": "Ottawa", "state": "ON", "zip": "K1P 5M7", "country": "Canada", "lat": 45.4215, "lng": -75.6972},
    {"city": "New York", "state": "NY", "zip": "10001", "country": "United States", "lat": 40.7128, "lng": -74.0060},
    {"city": "Los Angeles", "state": "CA", "zip": "90001", "country": "United States", "lat": 34.0522, "lng": -118.2437},
    {"city": "Chicago", "state": "IL", "zip": "60601", "country": "United States", "lat": 41.8781, "lng": -87.6298},
    {"city": "Miami", "state": "FL", "zip": "33101", "country": "United States", "lat": 25.7617, "lng": -80.1918},
]

SHOP_TEMPLATES = [
    # (name_prefix, shop_type, services, avg_service_time)
    {
        "type": "Barber Shop",
        "names": ["Classic Cuts", "Sharp Edge Barbers", "The Gentlemen's Den", "FreshFade Studio", "Blade & Brush Barbers"],
        "services": [
            ("Men's Haircut", 25, 25.00), ("Beard Trim", 15, 15.00), ("Hot Towel Shave", 30, 30.00),
            ("Kids Haircut", 20, 18.00), ("Hair & Beard Combo", 40, 40.00), ("Line Up", 10, 12.00),
        ],
        "avg_time": 25,
    },
    {
        "type": "Hair Salon",
        "names": ["Glow Up Salon", "Strand & Style", "Velvet Locks", "Crown Beauty Salon", "Luxe Hair Studio"],
        "services": [
            ("Women's Haircut", 45, 50.00), ("Blowout", 30, 35.00), ("Color & Highlights", 90, 120.00),
            ("Deep Conditioning", 30, 40.00), ("Updo / Styling", 60, 70.00), ("Keratin Treatment", 120, 200.00),
        ],
        "avg_time": 45,
    },
    {
        "type": "Spa & Wellness",
        "names": ["Zen Garden Spa", "Tranquil Waters Spa", "Serenity Day Spa", "Pure Bliss Wellness", "Oasis Retreat Spa"],
        "services": [
            ("Swedish Massage", 60, 90.00), ("Deep Tissue Massage", 60, 110.00), ("Facial", 45, 75.00),
            ("Manicure", 30, 35.00), ("Pedicure", 45, 45.00), ("Body Wrap", 90, 130.00),
        ],
        "avg_time": 50,
    },
    {
        "type": "Medical Clinic",
        "names": ["QuickCare Walk-In", "HealthFirst Clinic", "MedPoint Urgent Care", "CityHealth Medical", "Wellness MD Clinic"],
        "services": [
            ("General Consultation", 20, 80.00), ("Blood Test", 15, 50.00), ("Flu Shot", 10, 30.00),
            ("Physical Exam", 40, 120.00), ("X-Ray", 20, 100.00), ("Follow-up Visit", 15, 60.00),
        ],
        "avg_time": 20,
    },
    {
        "type": "Auto Repair Shop",
        "names": ["SpeedWrench Auto", "TurboFix Garage", "Pit Stop Auto Care", "DriveRight Mechanics", "AutoPro Service"],
        "services": [
            ("Oil Change", 30, 45.00), ("Tire Rotation", 30, 40.00), ("Brake Inspection", 45, 60.00),
            ("Engine Diagnostics", 60, 100.00), ("AC Service", 60, 85.00), ("Battery Replacement", 20, 120.00),
        ],
        "avg_time": 45,
    },
    {
        "type": "Nail Salon",
        "names": ["Polish & Shine", "Nail Artistry Studio", "Tips & Toes Lounge", "Color Pop Nails", "Lacquer Lane"],
        "services": [
            ("Classic Manicure", 25, 25.00), ("Gel Manicure", 35, 40.00), ("Acrylic Full Set", 60, 55.00),
            ("Classic Pedicure", 35, 35.00), ("Gel Pedicure", 45, 50.00), ("Nail Art (per nail)", 5, 5.00),
        ],
        "avg_time": 35,
    },
    {
        "type": "Pet Grooming",
        "names": ["Paws & Claws Grooming", "Happy Tails Pet Spa", "Fur Baby Studio", "The Pampered Pooch", "Bark Avenue Grooming"],
        "services": [
            ("Bath & Brush (Small)", 30, 35.00), ("Bath & Brush (Large)", 45, 55.00), ("Full Groom (Small)", 60, 50.00),
            ("Full Groom (Large)", 90, 80.00), ("Nail Trim", 10, 15.00), ("De-shedding Treatment", 45, 60.00),
        ],
        "avg_time": 45,
    },
    {
        "type": "Dental Clinic",
        "names": ["BrightSmile Dental", "Pearl Dental Care", "SmileCraft Dentistry", "Gentle Touch Dental", "City Dental Clinic"],
        "services": [
            ("Dental Cleaning", 45, 120.00), ("Whitening", 60, 300.00), ("Filling", 30, 150.00),
            ("Crown", 60, 800.00), ("Consultation", 20, 50.00), ("X-Ray", 15, 75.00),
        ],
        "avg_time": 30,
    },
]

FIRST_NAMES = ["Alex", "Jordan", "Sam", "Morgan", "Taylor", "Casey", "Riley", "Quinn", "Avery", "Blake",
               "Cameron", "Dana", "Elliot", "Finley", "Gray", "Harper", "Indigo", "Jamie", "Kai", "Logan",
               "Milan", "Noah", "Oakley", "Parker", "Reese", "Sage", "Tatum", "Uma", "Val", "Wren"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Martinez", "Wilson",
              "Anderson", "Thomas", "Jackson", "White", "Harris", "Clark", "Lewis", "Lee", "Walker", "Hall"]

STREET_NAMES = ["Main St", "Oak Ave", "Maple Dr", "King St W", "Queen St E", "Dundas St", "Yonge St",
                "Broadway", "Park Ave", "5th Ave", "Elm St", "Cedar Blvd", "Pine Rd", "Lakeshore Blvd",
                "Highway 2", "Wellington St", "Simcoe St N", "Centre St", "Victoria Ave", "Church St"]

PHONE_PREFIXES = ["416", "905", "647", "437", "289", "212", "310", "312", "305", "613"]

CUSTOMER_FIRST_NAMES = ["Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason", "Isabella", "James",
                         "Mia", "Benjamin", "Charlotte", "Elijah", "Amelia", "Lucas", "Harper", "Henry", "Evelyn", "Alexander"]

def gen_phone(city_info):
    prefix = random.choice(PHONE_PREFIXES)
    return f"({prefix}) {random.randint(200,999)}-{random.randint(1000,9999)}"

def gen_address(city_info):
    return f"{random.randint(1, 9999)} {random.choice(STREET_NAMES)}"

def gen_slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


# ═══════════════════════════════════════════════
# MAIN SEED FUNCTION
# ═══════════════════════════════════════════════

def seed_all():
    db = SessionLocal()
    try:
        # --- Check if seed data already exists ---
        existing_shops = db.query(Shop).count()
        if existing_shops >= 30:
            print(f"Database already has {existing_shops} shops. Skipping seed (use --force to override).")
            if "--force" not in sys.argv:
                return
            print("--force flag detected. Proceeding with additional seed data...")

        print("=" * 60)
        print("ZeroQwait Seed Data Generator")
        print("=" * 60)

        # ── 1. Create shop owner users ──
        print("\n[1/8] Creating shop owner users...")
        owners = []
        for i, template in enumerate(SHOP_TEMPLATES):
            for j, name in enumerate(template["names"]):
                idx = i * 5 + j
                fname = FIRST_NAMES[idx % len(FIRST_NAMES)]
                lname = LAST_NAMES[idx % len(LAST_NAMES)]
                username = f"{fname.lower()}_{lname.lower()}_{idx}"
                email = f"{username}@zeroqwait-seed.com"

                existing = db.query(User).filter(User.email == email).first()
                if existing:
                    owners.append(existing)
                    continue

                user = User(
                    email=email,
                    username=username,
                    hashed_password=DEFAULT_PASSWORD,
                    role=UserRole.SHOP_OWNER,
                    is_active=True,
                    subscription_tier=random.choice([SubscriptionTier.FREE, SubscriptionTier.PREMIUM]),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(30, 365)),
                )
                db.add(user)
                db.flush()
                owners.append(user)
        db.commit()
        print(f"   Created/found {len(owners)} shop owners")

        # ── 2. Create employee users ──
        print("\n[2/8] Creating employee users...")
        employee_users = []
        for i in range(60):
            fname = FIRST_NAMES[(i + 10) % len(FIRST_NAMES)]
            lname = LAST_NAMES[(i + 5) % len(LAST_NAMES)]
            username = f"emp_{fname.lower()}_{lname.lower()}_{i}"
            email = f"{username}@zeroqwait-seed.com"

            existing = db.query(User).filter(User.email == email).first()
            if existing:
                employee_users.append(existing)
                continue

            user = User(
                email=email,
                username=username,
                hashed_password=DEFAULT_PASSWORD,
                role=UserRole.EMPLOYEE,
                is_active=True,
                created_at=datetime.utcnow() - timedelta(days=random.randint(10, 300)),
            )
            db.add(user)
            db.flush()
            employee_users.append(user)
        db.commit()
        print(f"   Created/found {len(employee_users)} employees")

        # ── 3. Create shops ──
        print("\n[3/8] Creating shops...")
        shops = []
        owner_idx = 0
        for template in SHOP_TEMPLATES:
            for name in template["names"]:
                city_info = random.choice(CITIES)
                slug = gen_slug(name + " " + city_info["city"])

                existing = db.query(Shop).filter(Shop.slug == slug).first()
                if existing:
                    shops.append(existing)
                    owner_idx += 1
                    continue

                # Add small random offset to coordinates so shops don't stack
                lat_offset = random.uniform(-0.03, 0.03)
                lng_offset = random.uniform(-0.03, 0.03)

                shop = Shop(
                    owner_id=owners[owner_idx % len(owners)].id,
                    name=name,
                    description=f"Welcome to {name} — your premier {template['type'].lower()} in {city_info['city']}!",
                    shop_type=template["type"],
                    address=gen_address(city_info),
                    city=city_info["city"],
                    state=city_info["state"],
                    zip_code=city_info["zip"],
                    country=city_info["country"],
                    phone=gen_phone(city_info),
                    email=f"info@{gen_slug(name)}.com",
                    average_service_time=template["avg_time"],
                    slug=slug,
                    latitude=city_info["lat"] + lat_offset,
                    longitude=city_info["lng"] + lng_offset,
                    is_active=True,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(60, 400)),
                )
                db.add(shop)
                db.flush()
                shops.append(shop)
                owner_idx += 1
        db.commit()
        print(f"   Created/found {len(shops)} shops across {len(CITIES)} cities")

        # ── 4. Create services for each shop ──
        print("\n[4/8] Creating shop services...")
        svc_count = 0
        for shop in shops:
            # Find matching template
            template = next((t for t in SHOP_TEMPLATES if t["type"] == shop.shop_type), SHOP_TEMPLATES[0])
            existing_svcs = db.query(ShopService).filter(ShopService.shop_id == shop.id).count()
            if existing_svcs > 0:
                continue
            for svc_name, duration, cost in template["services"]:
                svc = ShopService(
                    shop_id=shop.id,
                    name=svc_name,
                    description=f"{svc_name} at {shop.name}",
                    duration_minutes=duration,
                    cost=cost + random.uniform(-5, 10),  # slight price variation
                    currency="USD" if shop.country == "United States" else "CAD",
                    is_active=True,
                    created_at=shop.created_at + timedelta(days=1),
                )
                db.add(svc)
                svc_count += 1
        db.commit()
        print(f"   Created {svc_count} services")

        # ── 5. Create queues + employees per shop ──
        print("\n[5/8] Creating queues & employees...")
        queue_count = 0
        emp_assign_count = 0
        emp_idx = 0
        shop_queues = {}  # shop_id -> Queue
        shop_svcs = {}    # shop_id -> [ShopService]

        for shop in shops:
            # Queue
            existing_q = db.query(Queue).filter(Queue.shop_id == shop.id, Queue.is_active == True).first()
            if existing_q:
                shop_queues[shop.id] = existing_q
            else:
                q = Queue(shop_id=shop.id, name="Main Queue", is_active=True, date=datetime.utcnow())
                db.add(q)
                db.flush()
                shop_queues[shop.id] = q
                queue_count += 1

            # Employees (2-4 per shop)
            existing_emps = db.query(ShopEmployee).filter(ShopEmployee.shop_id == shop.id).count()
            if existing_emps == 0:
                num_emps = random.randint(2, 4)
                for _ in range(num_emps):
                    emp_user = employee_users[emp_idx % len(employee_users)]
                    # Check not already assigned to this shop
                    already = db.query(ShopEmployee).filter(
                        ShopEmployee.shop_id == shop.id, ShopEmployee.user_id == emp_user.id
                    ).first()
                    if not already:
                        se = ShopEmployee(
                            shop_id=shop.id,
                            user_id=emp_user.id,
                            is_active=True,
                            created_at=shop.created_at + timedelta(days=random.randint(1, 30)),
                        )
                        db.add(se)
                        emp_assign_count += 1
                    emp_idx += 1

            # Cache services
            svcs = db.query(ShopService).filter(ShopService.shop_id == shop.id, ShopService.is_active == True).all()
            shop_svcs[shop.id] = svcs

        db.commit()
        print(f"   Created {queue_count} queues, assigned {emp_assign_count} employees")

        # ── 6. Create historical daily analytics (90 days) ──
        print("\n[6/8] Creating historical analytics (90 days)...")
        analytics_count = 0
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        for shop in shops:
            existing_analytics = db.query(DailyAnalytics).filter(DailyAnalytics.shop_id == shop.id).count()
            if existing_analytics >= 30:
                continue

            for days_ago in range(90, 0, -1):
                date = today - timedelta(days=days_ago)
                # Skip Sundays with 30% chance (some shops close)
                if date.weekday() == 6 and random.random() < 0.3:
                    continue

                # Realistic patterns: weekends busier, gradual growth
                base = random.randint(8, 25)
                weekend_mult = 1.3 if date.weekday() >= 5 else 1.0
                growth_mult = 1 + (90 - days_ago) * 0.003  # gradual growth

                total_customers = int(base * weekend_mult * growth_mult)
                completed = int(total_customers * random.uniform(0.75, 0.95))
                cancelled = total_customers - completed
                avg_svc_cost = 40 if not shop_svcs.get(shop.id) else sum(s.cost for s in shop_svcs[shop.id]) / max(len(shop_svcs[shop.id]), 1)
                revenue = completed * avg_svc_cost * random.uniform(0.8, 1.2)

                peak_hour = random.choice([10, 11, 12, 13, 14, 15, 16])

                analytics = DailyAnalytics(
                    shop_id=shop.id,
                    date=date,
                    total_customers=total_customers,
                    completed_services=completed,
                    cancelled_services=cancelled,
                    total_revenue=round(revenue, 2),
                    avg_wait_time_minutes=round(random.uniform(5, 25), 1),
                    avg_service_time_minutes=round(random.uniform(15, 50), 1),
                    peak_hour_start=peak_hour,
                    peak_hour_customers=random.randint(3, 8),
                    created_at=date + timedelta(hours=18),
                )
                db.add(analytics)
                analytics_count += 1

            # Batch commit every 10 shops
            if shops.index(shop) % 10 == 9:
                db.commit()

        db.commit()
        print(f"   Created {analytics_count} daily analytics records")

        # ── 7. Create shop customers & historical queue items ──
        print("\n[7/8] Creating customers & historical queue items...")
        customer_count = 0
        qi_count = 0

        for shop in shops:
            existing_customers = db.query(ShopCustomer).filter(ShopCustomer.shop_id == shop.id).count()
            if existing_customers >= 10:
                continue

            # Create 15-30 regular customers per shop
            num_customers = random.randint(15, 30)
            shop_customers = []
            for c in range(num_customers):
                fname = random.choice(CUSTOMER_FIRST_NAMES)
                lname = random.choice(LAST_NAMES)
                customer = ShopCustomer(
                    shop_id=shop.id,
                    phone=gen_phone(CITIES[0]),
                    name=f"{fname} {lname}",
                    email=f"{fname.lower()}.{lname.lower()}.{random.randint(1,999)}@example.com" if random.random() > 0.3 else None,
                    visit_count=random.randint(1, 20),
                    last_visit=datetime.utcnow() - timedelta(days=random.randint(0, 60)),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(30, 365)),
                )
                db.add(customer)
                shop_customers.append(customer)
                customer_count += 1

            # Create some historical queue items (completed) for the past 7 days
            queue = shop_queues.get(shop.id)
            svcs = shop_svcs.get(shop.id, [])
            if queue and svcs:
                for days_ago in range(7, 0, -1):
                    date = today - timedelta(days=days_ago)
                    num_items = random.randint(5, 15)
                    for pos in range(1, num_items + 1):
                        cname = f"{random.choice(CUSTOMER_FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                        svc = random.choice(svcs)
                        check_in = date + timedelta(hours=random.randint(9, 17), minutes=random.randint(0, 59))
                        svc_start = check_in + timedelta(minutes=random.randint(5, 30))
                        completed_at = svc_start + timedelta(minutes=svc.duration_minutes + random.randint(-5, 10))

                        status = random.choices(
                            [QueueStatus.COMPLETED, QueueStatus.CANCELLED],
                            weights=[85, 15]
                        )[0]

                        qi = QueueItem(
                            queue_id=queue.id,
                            customer_name=cname,
                            customer_phone=gen_phone(CITIES[0]) if random.random() > 0.4 else None,
                            position=pos,
                            status=status,
                            checked_in_at=check_in,
                            service_started_at=svc_start if status == QueueStatus.COMPLETED else None,
                            completed_at=completed_at if status == QueueStatus.COMPLETED else check_in + timedelta(minutes=random.randint(1, 10)),
                            service_id=svc.id,
                            service_cost=svc.cost,
                        )
                        db.add(qi)
                        qi_count += 1

            # Batch commit
            if shops.index(shop) % 5 == 4:
                db.commit()

        db.commit()
        print(f"   Created {customer_count} customers, {qi_count} queue items")

        # ── 8. Seed agent knowledge & category aliases ──
        print("\n[8/8] Seeding agent knowledge & category aliases...")

        # Agent knowledge entries
        knowledge_entries = [
            ("critical_instructions", """## CRITICAL INSTRUCTIONS
- If the user expressed intent to sign up, join, create account, or register (either as a customer or shop owner), you MUST call the `start_registration` tool.
- If the user explicitly or implicitly asks to find shops, see nearby businesses, or list options (e.g., "list shops near me", "find a barber"), you MUST call the `search_shops` tool immediately. Do not ask for their location first; the tool handles that.
- If the user asks about pricing or how much it costs, call `see_pricing`.
- If the user asks about features or what the app can do, call `see_features`.
- If the user asks for help or FAQ, call `see_faq`.
- NEVER give health, legal, or financial advice.""", "Core instructions for the AI agent"),

            ("about_zeroqwait", """## ABOUT ZEROQWAIT
ZeroQwait is a universal queue management platform where service businesses (barbers, salons, clinics, auto shops, etc.) register, and customers can discover them, join queues remotely, and view real-time wait times.
Key features: AI assistant, real-time queue tracking, voice interface, shop discovery, analytics dashboard.""", "Description of the platform"),

            ("conversational_responses", """## CONVERSATIONAL GUIDELINES
- Greet warmly, be concise (1-3 sentences for simple questions)
- For shop discovery: suggest categories if the user is vague
- Always offer to help with next steps after answering""", "How the agent should converse"),

            ("search_guidance", """## SEARCH GUIDANCE
- When searching: prefer matching shop_type first, then name/description
- If no results: suggest broadening the search or trying nearby cities
- Always mention the city in results for clarity""", "Search behavior guidance"),
        ]

        for key, content, description in knowledge_entries:
            from modules.agent.models import AgentKnowledge
            existing = db.query(AgentKnowledge).filter(AgentKnowledge.key == key).first()
            if not existing:
                db.add(AgentKnowledge(key=key, content=content, description=description))

        # Category aliases for better search matching
        alias_entries = [
            ("Barber Shop", ["barber", "barbershop", "haircut", "mens haircut", "fade", "lineup"]),
            ("Hair Salon", ["salon", "hair salon", "hairdresser", "hairstylist", "blowout", "color"]),
            ("Spa & Wellness", ["spa", "massage", "wellness", "facial", "relaxation", "body treatment"]),
            ("Medical Clinic", ["clinic", "doctor", "walk-in", "urgent care", "medical", "healthcare"]),
            ("Auto Repair Shop", ["auto repair", "mechanic", "garage", "car repair", "auto shop", "oil change"]),
            ("Nail Salon", ["nails", "nail salon", "manicure", "pedicure", "gel nails", "acrylics"]),
            ("Pet Grooming", ["pet grooming", "dog grooming", "pet spa", "groomer", "dog wash"]),
            ("Dental Clinic", ["dentist", "dental", "teeth cleaning", "dental clinic", "orthodontist"]),
        ]

        for category_key, aliases in alias_entries:
            for alias in aliases:
                existing = db.query(CategoryAlias).filter(
                    CategoryAlias.category_key == category_key,
                    CategoryAlias.alias == alias
                ).first()
                if not existing:
                    db.add(CategoryAlias(category_key=category_key, alias=alias))

        db.commit()
        print("   Agent knowledge & category aliases seeded")

        # ── Summary ──
        print("\n" + "=" * 60)
        total_shops = db.query(Shop).count()
        total_users = db.query(User).count()
        total_svcs = db.query(ShopService).count()
        total_analytics = db.query(DailyAnalytics).count()
        total_qi = db.query(QueueItem).count()
        total_customers = db.query(ShopCustomer).count()
        print(f"SEED COMPLETE!")
        print(f"  Users:          {total_users}")
        print(f"  Shops:          {total_shops}")
        print(f"  Services:       {total_svcs}")
        print(f"  Analytics:      {total_analytics}")
        print(f"  Queue Items:    {total_qi}")
        print(f"  Customers:      {total_customers}")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
