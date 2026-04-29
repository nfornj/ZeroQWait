#!/usr/bin/env python3
"""
ZeroQwait — Comprehensive 500-Shop Seed Script with 3 Years Historical Data
=============================================================================
Creates ~500 shops across 15 cities, each with:
  - 1 shop owner (SHOP_OWNER role)
  - 3-6 services matching shop type
  - 2-5 employees per shop
  - 3 years of DailyAnalytics (growth curve + seasonality + weekends)
  - Last 60 days of raw QueueItem records
  - ShopCustomer records per shop
  - Twenty CRM companies + people for every shop owner (optional)

Run:
  python seed_500_shops.py                     # Full seed (500 shops + 3yr data)
  python seed_500_shops.py --shops 100         # Fewer shops
  python seed_500_shops.py --skip-analytics    # Skip slow 3yr generation
  python seed_500_shops.py --skip-crm          # Skip Twenty CRM population
  python seed_500_shops.py --dry-run           # Print plan, don't execute
"""

import os
import sys
import re
import random
import math
import argparse
import logging
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine
from modules.auth.models import User, UserRole, SubscriptionTier
from modules.shops.models import Shop, ShopService, DailyAnalytics, ShopCustomer
from modules.queues.models import Queue, QueueItem, QueueStatus
from modules.employees.models import ShopEmployee, EmployeeShift
from shared.auth_utils import get_password_hash

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed500")

BATCH_SIZE = 500  # DB flush batch size

# ═══════════════════════════════════════════════════════════════════════
# REALISTIC DATA POOLS
# ═══════════════════════════════════════════════════════════════════════

CITIES = [
    {"city": "Toronto",      "state": "ON", "zip": "M5V 3L9", "country": "Canada",        "lat": 43.6532, "lng": -79.3832},
    {"city": "Mississauga",  "state": "ON", "zip": "L5B 3C2", "country": "Canada",        "lat": 43.5890, "lng": -79.6441},
    {"city": "Brampton",     "state": "ON", "zip": "L6Y 1N2", "country": "Canada",        "lat": 43.7315, "lng": -79.7624},
    {"city": "Hamilton",     "state": "ON", "zip": "L8P 4S5", "country": "Canada",        "lat": 43.2557, "lng": -79.8711},
    {"city": "Ottawa",       "state": "ON", "zip": "K1P 5M7", "country": "Canada",        "lat": 45.4215, "lng": -75.6972},
    {"city": "Oshawa",       "state": "ON", "zip": "L1H 7K4", "country": "Canada",        "lat": 43.8971, "lng": -78.8658},
    {"city": "New York",     "state": "NY", "zip": "10001",   "country": "United States",  "lat": 40.7128, "lng": -74.0060},
    {"city": "Los Angeles",  "state": "CA", "zip": "90001",   "country": "United States",  "lat": 34.0522, "lng": -118.2437},
    {"city": "Chicago",      "state": "IL", "zip": "60601",   "country": "United States",  "lat": 41.8781, "lng": -87.6298},
    {"city": "Miami",        "state": "FL", "zip": "33101",   "country": "United States",  "lat": 25.7617, "lng": -80.1918},
    {"city": "Houston",      "state": "TX", "zip": "77001",   "country": "United States",  "lat": 29.7604, "lng": -95.3698},
    {"city": "Vancouver",    "state": "BC", "zip": "V6B 1A1", "country": "Canada",        "lat": 49.2827, "lng": -123.1207},
    {"city": "Montreal",     "state": "QC", "zip": "H2X 1Y4", "country": "Canada",        "lat": 45.5017, "lng": -73.5673},
    {"city": "Dallas",       "state": "TX", "zip": "75201",   "country": "United States",  "lat": 32.7767, "lng": -96.7970},
    {"city": "San Francisco","state": "CA", "zip": "94102",   "country": "United States",  "lat": 37.7749, "lng": -122.4194},
]

SHOP_TEMPLATES = [
    {
        "type": "Barber Shop",
        "name_parts": [
            "Classic Cuts", "Sharp Edge Barbers", "The Gentlemen's Den", "FreshFade Studio",
            "Blade & Brush", "Crown Barbers", "Precision Cuts", "Metropolitan Barbers",
            "Urban Trim", "The Clipper Room", "Royal Barber Co", "Heritage Cuts",
            "Mane Street Barbers", "Elite Edge", "The Barber's Chair", "Smooth Operators",
        ],
        "services": [
            ("Men's Haircut", 25, 28.00), ("Beard Trim", 15, 16.00), ("Hot Towel Shave", 30, 32.00),
            ("Kids Haircut", 20, 20.00), ("Hair & Beard Combo", 40, 42.00), ("Line Up", 10, 14.00),
            ("Fade Cut", 30, 30.00), ("Scalp Treatment", 20, 25.00),
        ],
        "avg_time": 25,
    },
    {
        "type": "Hair Salon",
        "name_parts": [
            "Glow Up Salon", "Strand & Style", "Velvet Locks", "Crown Beauty",
            "Luxe Hair Studio", "Shear Elegance", "Tresses & Co", "Color Lab",
            "The Styling Bar", "Chic Hair Lounge", "Mane Attraction", "Silk & Scissors",
            "Fringe Benefits", "The Blowout Bar", "Platinum Salon", "Radiance Hair",
        ],
        "services": [
            ("Women's Haircut", 45, 52.00), ("Blowout", 30, 38.00), ("Color & Highlights", 90, 125.00),
            ("Deep Conditioning", 30, 42.00), ("Updo / Styling", 60, 72.00), ("Keratin Treatment", 120, 210.00),
            ("Balayage", 120, 180.00), ("Extensions Consult", 30, 50.00),
        ],
        "avg_time": 45,
    },
    {
        "type": "Spa & Wellness",
        "name_parts": [
            "Zen Garden Spa", "Tranquil Waters", "Serenity Day Spa", "Pure Bliss Wellness",
            "Oasis Retreat Spa", "The Calm Room", "Harmony Spa", "Balance Wellness",
            "Vitality Spa", "Rejuve Center", "Lotus Spa", "Inner Peace Wellness",
            "Soothe Day Spa", "Cloud Nine Spa", "Refresh Wellness", "Solace Spa",
        ],
        "services": [
            ("Swedish Massage", 60, 92.00), ("Deep Tissue Massage", 60, 112.00), ("Facial", 45, 78.00),
            ("Manicure", 30, 38.00), ("Pedicure", 45, 48.00), ("Body Wrap", 90, 135.00),
            ("Aromatherapy", 60, 95.00), ("Couples Massage", 90, 180.00),
        ],
        "avg_time": 50,
    },
    {
        "type": "Medical Clinic",
        "name_parts": [
            "QuickCare Walk-In", "HealthFirst Clinic", "MedPoint Urgent Care", "CityHealth Medical",
            "Wellness MD", "CarePlus Medical", "FamilyCare Clinic", "MedExpress",
            "PrimeCare", "NovaMed Clinic", "TruHealth", "SwiftCare Medical",
            "LifeLine Clinic", "AllCare Medical", "ProHealth Clinic", "MedConnect",
        ],
        "services": [
            ("General Consultation", 20, 85.00), ("Blood Test", 15, 55.00), ("Flu Shot", 10, 32.00),
            ("Physical Exam", 40, 125.00), ("X-Ray", 20, 105.00), ("Follow-up Visit", 15, 62.00),
            ("COVID Test", 10, 40.00), ("Allergy Test", 30, 90.00),
        ],
        "avg_time": 20,
    },
    {
        "type": "Auto Repair Shop",
        "name_parts": [
            "SpeedWrench Auto", "TurboFix Garage", "Pit Stop Auto Care", "DriveRight Mechanics",
            "AutoPro Service", "GearUp Garage", "MasterMech Auto", "Apex Auto Repair",
            "QuickLube Express", "Torque Auto", "RoadReady Repairs", "AllDrive Auto",
            "PowerHouse Garage", "Summit Auto", "FixIt Fast Auto", "Throttle Garage",
        ],
        "services": [
            ("Oil Change", 30, 48.00), ("Tire Rotation", 30, 42.00), ("Brake Inspection", 45, 65.00),
            ("Engine Diagnostics", 60, 105.00), ("AC Service", 60, 88.00), ("Battery Replacement", 20, 125.00),
            ("Transmission Fluid", 30, 85.00), ("Wheel Alignment", 45, 95.00),
        ],
        "avg_time": 45,
    },
    {
        "type": "Nail Salon",
        "name_parts": [
            "Polish & Shine", "Nail Artistry", "Tips & Toes", "Color Pop Nails",
            "Lacquer Lane", "Glam Nails Studio", "Velvet Nails", "Crystal Nail Spa",
            "The Nail Room", "Luxe Nails", "Sparkle Nails", "Pretty Polished",
            "Dazzle Nails", "Nailology", "Maison Manucure", "Painted Beauty",
        ],
        "services": [
            ("Classic Manicure", 25, 28.00), ("Gel Manicure", 35, 42.00), ("Acrylic Full Set", 60, 58.00),
            ("Classic Pedicure", 35, 38.00), ("Gel Pedicure", 45, 52.00), ("Nail Art (per nail)", 5, 6.00),
            ("Dip Powder", 50, 48.00), ("Nail Repair", 15, 15.00),
        ],
        "avg_time": 35,
    },
    {
        "type": "Pet Grooming",
        "name_parts": [
            "Paws & Claws", "Happy Tails Pet Spa", "Fur Baby Studio", "The Pampered Pooch",
            "Bark Avenue Grooming", "Wagmore Pet Spa", "Fluff & Fold Pets", "PetStyle Studio",
            "Snip & Clip Pets", "Pawfect Grooming", "Golden Paw", "FurEver Clean",
            "Pet Paradise Spa", "The Grooming Spot", "Wags & Whiskers", "Cozy Paws",
        ],
        "services": [
            ("Bath & Brush (Small)", 30, 38.00), ("Bath & Brush (Large)", 45, 58.00), ("Full Groom (Small)", 60, 52.00),
            ("Full Groom (Large)", 90, 82.00), ("Nail Trim", 10, 18.00), ("De-shedding Treatment", 45, 62.00),
            ("Teeth Cleaning", 20, 25.00), ("Flea Bath", 40, 45.00),
        ],
        "avg_time": 45,
    },
    {
        "type": "Dental Clinic",
        "name_parts": [
            "BrightSmile Dental", "Pearl Dental Care", "SmileCraft Dentistry", "Gentle Touch Dental",
            "City Dental Clinic", "Ivory Dental", "Shine Dental Studio", "FreshSmile",
            "DentaCare Plus", "Perfect Teeth", "Radiant Dental", "TrueSmile Clinic",
            "Dental Oasis", "SmileWorks", "Prestige Dental", "OralCare Experts",
        ],
        "services": [
            ("Dental Cleaning", 45, 125.00), ("Whitening", 60, 310.00), ("Filling", 30, 155.00),
            ("Crown", 60, 820.00), ("Consultation", 20, 55.00), ("X-Ray", 15, 78.00),
            ("Root Canal", 90, 950.00), ("Extraction", 30, 200.00),
        ],
        "avg_time": 30,
    },
    {
        "type": "Fitness & Gym",
        "name_parts": [
            "IronWorks Gym", "FitZone Studio", "Peak Performance", "CorePower Fitness",
            "The Training Ground", "Flex Fitness", "PowerHouse Gym", "Evolve Fitness",
            "Momentum Gym", "Titan Fitness", "Rise Athletics", "Sweat Studio",
            "The Grind Gym", "Alpha Fitness", "Endurance Lab", "Pulse Fitness",
        ],
        "services": [
            ("Personal Training 1hr", 60, 80.00), ("Group Class", 45, 25.00), ("Yoga Session", 60, 30.00),
            ("Body Assessment", 30, 50.00), ("Nutrition Consult", 45, 65.00), ("CrossFit Class", 60, 35.00),
            ("Spin Class", 45, 28.00), ("Stretch Therapy", 30, 40.00),
        ],
        "avg_time": 50,
    },
    {
        "type": "Restaurant & Café",
        "name_parts": [
            "The Daily Grind", "Urban Kitchen", "Sunrise Café", "The Rustic Table",
            "Ember & Oak", "Harvest Bistro", "Blue Plate Diner", "The Nook Café",
            "Fork & Knife", "Savour Kitchen", "Basil & Thyme", "The Coffee Collective",
            "Crumbs Bakery", "Sizzle & Grill", "Toast & Co", "Maple Leaf Café",
        ],
        "services": [
            ("Table Reservation (2)", 60, 0.00), ("Table Reservation (4)", 90, 0.00), ("Private Room", 120, 50.00),
            ("Catering Consult", 30, 0.00), ("Tasting Menu", 120, 85.00), ("Brunch Booking", 90, 35.00),
            ("Afternoon Tea", 60, 45.00), ("Birthday Package", 120, 150.00),
        ],
        "avg_time": 60,
    },
]

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Carol", "Kevin", "Amanda", "Brian", "Dorothy", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole", "Brandon", "Helen",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Raymond", "Christine", "Gregory", "Debra",
    "Frank", "Rachel", "Alexander", "Carolyn", "Patrick", "Janet", "Jack", "Catherine",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy",
    "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey",
    "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson", "Watson",
    "Wood", "James", "Bennett", "Gray", "Mendoza", "Ruiz", "Hughes", "Price", "Alvarez",
    "Castillo", "Sanders", "Patel", "Myers", "Long", "Ross", "Foster", "Jimenez", "Powell",
]

STREET_NAMES = [
    "Main St", "Oak Ave", "Maple Dr", "King St W", "Queen St E", "Dundas St", "Yonge St",
    "Broadway", "Park Ave", "5th Ave", "Elm St", "Cedar Blvd", "Pine Rd", "Lakeshore Blvd",
    "Wellington St", "Simcoe St N", "Centre St", "Victoria Ave", "Church St", "Bloor St W",
    "College Ave", "Spadina Ave", "Bay St", "University Ave", "Front St", "Harbourfront Dr",
    "Riverside Dr", "Sunset Blvd", "Ocean Dr", "Peachtree St", "Market St", "State St",
]

PHONE_AREA_CODES = {
    "Toronto": "416", "Mississauga": "905", "Brampton": "905", "Hamilton": "905",
    "Ottawa": "613", "Oshawa": "905", "Vancouver": "604", "Montreal": "514",
    "New York": "212", "Los Angeles": "310", "Chicago": "312", "Miami": "305",
    "Houston": "713", "Dallas": "214", "San Francisco": "415",
}

CUSTOMER_FIRST = [
    "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason", "Isabella", "James",
    "Mia", "Benjamin", "Charlotte", "Elijah", "Amelia", "Lucas", "Harper", "Henry", "Evelyn",
    "Alexander", "Abigail", "Sebastian", "Emily", "Jack", "Ella", "Aiden", "Scarlett", "Owen",
    "Grace", "Luke", "Chloe", "Carter", "Victoria", "Jayden", "Riley", "Dylan", "Aria",
    "Grayson", "Lily", "Levi",
]


def gen_slug(name: str, city: str) -> str:
    raw = f"{name} {city}"
    return re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")


def gen_phone(city: str) -> str:
    code = PHONE_AREA_CODES.get(city, "416")
    return f"({code}) {random.randint(200,999)}-{random.randint(1000,9999)}"


def gen_address(city: str) -> str:
    return f"{random.randint(1, 9999)} {random.choice(STREET_NAMES)}"


def unique_username(fname: str, lname: str, idx: int) -> str:
    return f"{fname.lower()}_{lname.lower()}_{idx}"


# ═══════════════════════════════════════════════════════════════════════
# ANALYTICS GENERATION (Realistic 3-year growth patterns)
# ═══════════════════════════════════════════════════════════════════════

MONTH_SEASONALITY = {
    1: 0.85,  2: 0.80,  3: 0.90,  4: 1.00,   5: 1.05,  6: 1.10,
    7: 1.30,  8: 1.25,  9: 1.05, 10: 0.95,  11: 0.90, 12: 1.20,
}


def compute_daily_metrics(
    shop_created: date,
    day: date,
    base_customers: int,
    avg_svc_cost: float,
    shop_popularity: float,   # 0.5 – 1.5 multiplier per shop
) -> dict:
    """Return a dict of DailyAnalytics fields for one day."""
    days_open = (day - shop_created).days
    if days_open < 0:
        return None  # shop not open yet

    # Growth curve: ramp from 30% → 100% over first 365 days, then slow grow
    if days_open <= 365:
        growth = 0.30 + 0.70 * (days_open / 365)
    else:
        # Slow continued growth: +5% per additional year
        extra_years = (days_open - 365) / 365
        growth = 1.0 + 0.05 * extra_years

    month = day.month
    seasonality = MONTH_SEASONALITY.get(month, 1.0)

    is_weekend = day.weekday() >= 5
    weekend_factor = 1.40 if is_weekend else 1.0

    # Random daily noise ±15%
    noise = random.uniform(0.85, 1.15)

    volume = int(base_customers * growth * seasonality * weekend_factor * shop_popularity * noise)
    volume = max(2, volume)

    completed = int(volume * random.uniform(0.88, 0.96))
    cancelled = volume - completed

    revenue = 0.0
    for _ in range(completed):
        cost_jitter = avg_svc_cost * random.uniform(0.80, 1.25)
        revenue += cost_jitter
    revenue = round(revenue, 2)

    avg_wait = round(random.uniform(3, 35) * (1 + 0.3 * (volume / max(base_customers, 1) - 1)), 1)
    avg_svc_time = round(random.uniform(15, 55), 1)
    peak_hour = random.randint(10, 16)
    peak_customers = int(volume * random.uniform(0.18, 0.32))

    return {
        "total_customers": volume,
        "completed_services": completed,
        "cancelled_services": cancelled,
        "total_revenue": revenue,
        "avg_wait_time_minutes": avg_wait,
        "avg_service_time_minutes": avg_svc_time,
        "peak_hour_start": peak_hour,
        "peak_hour_customers": peak_customers,
    }


# ═══════════════════════════════════════════════════════════════════════
# TWENTY CRM POPULATION
# ═══════════════════════════════════════════════════════════════════════

def populate_twenty_crm(shops_data: list[dict]):
    """
    Batch-populate Twenty CRM with companies + people for each shop owner.
    Requires TWENTY_API_KEY and TWENTY_GRAPHQL_URL env vars.
    """
    import httpx

    api_key = os.environ.get("TWENTY_API_KEY", "")
    graphql_url = os.environ.get("TWENTY_GRAPHQL_URL", "http://localhost:3001/graphql")

    if not api_key:
        log.warning("⚠  TWENTY_API_KEY not set — skipping CRM population")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    log.info("\n[CRM] Populating Twenty CRM with shop companies + contacts...")
    created_companies = 0
    created_people = 0
    errors = 0

    with httpx.Client(base_url=graphql_url.rstrip("/graphql"), headers=headers, timeout=15) as client:
        for sd in shops_data:
            # Create company for each shop
            company_mutation = """
            mutation($name: String!) {
                createCompany(data: { name: $name }) { id name }
            }
            """
            try:
                resp = client.post("/graphql", json={
                    "query": company_mutation,
                    "variables": {"name": sd["shop_name"]},
                })
                resp.raise_for_status()
                result = resp.json()
                if "errors" in result:
                    errors += 1
                    continue
                created_companies += 1
                company_id = result["data"]["createCompany"]["id"]

                # Create owner as person linked to company
                person_mutation = """
                mutation($firstName: String!, $lastName: String!) {
                    createPerson(data: {
                        name: { firstName: $firstName, lastName: $lastName }
                    }) { id }
                }
                """
                resp2 = client.post("/graphql", json={
                    "query": person_mutation,
                    "variables": {
                        "firstName": sd["owner_first"],
                        "lastName": sd["owner_last"],
                    },
                })
                resp2.raise_for_status()
                r2 = resp2.json()
                if "errors" not in r2:
                    created_people += 1

                # Create 1-2 additional contacts per shop
                for _ in range(random.randint(1, 2)):
                    fn = random.choice(CUSTOMER_FIRST)
                    ln = random.choice(LAST_NAMES)
                    resp3 = client.post("/graphql", json={
                        "query": person_mutation,
                        "variables": {"firstName": fn, "lastName": ln},
                    })
                    if resp3.status_code == 200 and "errors" not in resp3.json():
                        created_people += 1

            except Exception as e:
                errors += 1
                if errors <= 3:
                    log.warning(f"   CRM error: {e}")

    log.info(f"   ✅ CRM: {created_companies} companies, {created_people} people ({errors} errors)")


# ═══════════════════════════════════════════════════════════════════════
# MAIN SEED FUNCTION
# ═══════════════════════════════════════════════════════════════════════

def seed(
    target_shops: int = 500,
    years: int = 3,
    skip_analytics: bool = False,
    skip_crm: bool = False,
    dry_run: bool = False,
    password: str = "password123",
):
    hashed_pw = get_password_hash(password)
    db = SessionLocal()

    try:
        existing_count = db.query(Shop).count()
        shops_to_create = max(0, target_shops - existing_count)

        log.info("=" * 65)
        log.info("ZeroQwait — 500-Shop Seed Generator")
        log.info("=" * 65)
        log.info(f"  Target shops:     {target_shops}")
        log.info(f"  Existing shops:   {existing_count}")
        log.info(f"  To create:        {shops_to_create}")
        log.info(f"  History years:    {years}")
        log.info(f"  Skip analytics:   {skip_analytics}")
        log.info(f"  Skip CRM:         {skip_crm}")
        log.info(f"  Password:         {password}")
        log.info("")

        if dry_run:
            log.info("DRY RUN — no data will be written.")
            return

        if shops_to_create == 0:
            log.info(f"Already have {existing_count} shops — nothing to create.")
            if not skip_analytics:
                log.info("Will still generate analytics for shops missing history.")
            else:
                return

        # ── STEP 1: Create owners + shops + services + employees ──
        log.info("[1/5] Creating shop owners, shops, services, and employees...")

        all_shops_data = []  # For CRM population later
        login_lines = []     # Credentials output
        template_count = len(SHOP_TEMPLATES)
        created = 0

        # Deterministic index start to avoid collisions with existing seed data
        owner_idx_start = existing_count + 200  # offset to avoid collision

        for i in range(shops_to_create):
            tidx = i % template_count
            template = SHOP_TEMPLATES[tidx]
            name_idx = i // template_count
            city_info = CITIES[i % len(CITIES)]

            # Unique shop name: template name + city + number
            base_name = template["name_parts"][name_idx % len(template["name_parts"])]
            if name_idx >= len(template["name_parts"]):
                # Past unique names — append number
                shop_name = f"{base_name} #{name_idx + 1}"
            else:
                shop_name = base_name
            # Append city to make globally unique
            display_name = f"{shop_name} — {city_info['city']}"

            slug = gen_slug(shop_name, city_info["city"])
            # Ensure unique slug
            slug_base = slug
            slug_suffix = 0
            while db.query(Shop).filter(Shop.slug == slug).first() is not None:
                slug_suffix += 1
                slug = f"{slug_base}-{slug_suffix}"

            # Owner user
            uidx = owner_idx_start + i
            fname = FIRST_NAMES[uidx % len(FIRST_NAMES)]
            lname = LAST_NAMES[uidx % len(LAST_NAMES)]
            username = unique_username(fname, lname, uidx)
            email = f"{username}@zeroqwait.com"

            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                owner = existing_user
            else:
                owner = User(
                    email=email,
                    username=username,
                    hashed_password=hashed_pw,
                    role=UserRole.SHOP_OWNER,
                    is_active=True,
                    subscription_tier=random.choice([
                        SubscriptionTier.FREE, SubscriptionTier.FREE,
                        SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE,
                    ]),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(90, years * 365)),
                )
                db.add(owner)
                db.flush()

            # Shop
            lat_off = random.uniform(-0.04, 0.04)
            lng_off = random.uniform(-0.04, 0.04)
            shop_created_at = owner.created_at + timedelta(days=random.randint(0, 14))

            shop = Shop(
                owner_id=owner.id,
                name=display_name,
                description=f"Welcome to {display_name} — your premier {template['type'].lower()} experience in {city_info['city']}.",
                shop_type=template["type"],
                address=gen_address(city_info["city"]),
                city=city_info["city"],
                state=city_info["state"],
                zip_code=city_info["zip"],
                country=city_info["country"],
                phone=gen_phone(city_info["city"]),
                email=f"info@{slug.replace('-', '')[:20]}.com",
                average_service_time=template["avg_time"],
                slug=slug,
                latitude=city_info["lat"] + lat_off,
                longitude=city_info["lng"] + lng_off,
                is_active=True,
                created_at=shop_created_at,
            )
            db.add(shop)
            db.flush()

            # Services (pick 4-6 from template)
            num_svcs = random.randint(4, min(6, len(template["services"])))
            chosen_svcs = random.sample(template["services"], num_svcs)
            currency = "USD" if city_info["country"] == "United States" else "CAD"
            svc_objs = []
            for svc_name, dur, cost in chosen_svcs:
                svc = ShopService(
                    shop_id=shop.id,
                    name=svc_name,
                    description=f"{svc_name} at {display_name}",
                    duration_minutes=dur,
                    cost=round(cost * random.uniform(0.90, 1.15), 2),
                    currency=currency,
                    is_active=True,
                    created_at=shop_created_at + timedelta(days=1),
                )
                db.add(svc)
                svc_objs.append(svc)
            db.flush()

            # Queue
            queue = Queue(
                shop_id=shop.id,
                name="Main Queue",
                is_active=True,
                date=datetime.utcnow(),
            )
            db.add(queue)
            db.flush()

            # Employees (2-5 per shop)
            num_emps = random.randint(2, 5)
            for j in range(num_emps):
                eidx = (uidx * 10 + j) % len(FIRST_NAMES)
                efname = FIRST_NAMES[(eidx + j * 7) % len(FIRST_NAMES)]
                elname = LAST_NAMES[(eidx + j * 3) % len(LAST_NAMES)]
                eusername = f"emp_{efname.lower()}_{elname.lower()}_{uidx}_{j}"
                eemail = f"{eusername}@zeroqwait.com"

                existing_emp_user = db.query(User).filter(User.email == eemail).first()
                if existing_emp_user:
                    emp_user = existing_emp_user
                else:
                    emp_user = User(
                        email=eemail,
                        username=eusername,
                        hashed_password=hashed_pw,
                        role=UserRole.EMPLOYEE,
                        is_active=True,
                        created_at=shop_created_at + timedelta(days=random.randint(1, 30)),
                    )
                    db.add(emp_user)
                    db.flush()

                already = db.query(ShopEmployee).filter(
                    ShopEmployee.shop_id == shop.id, ShopEmployee.user_id == emp_user.id
                ).first()
                if not already:
                    se = ShopEmployee(
                        shop_id=shop.id,
                        user_id=emp_user.id,
                        is_active=True,
                        created_at=shop_created_at + timedelta(days=random.randint(1, 30)),
                    )
                    db.add(se)

            # Track for CRM + login output
            all_shops_data.append({
                "shop_id": shop.id,
                "shop_name": display_name,
                "owner_first": fname,
                "owner_last": lname,
                "city": city_info["city"],
                "type": template["type"],
                "avg_svc_cost": sum(c for _, _, c in chosen_svcs) / len(chosen_svcs),
                "base_customers": random.randint(8, 22),
                "popularity": random.uniform(0.6, 1.4),
                "created_date": shop_created_at.date(),
                "queue_id": queue.id,
                "services": svc_objs,
            })
            login_lines.append(f"OWNER: {username} | {password} | {email} | Shop: {display_name} (ID: {shop.id})")

            created += 1
            if created % 50 == 0:
                db.commit()
                log.info(f"   ... created {created}/{shops_to_create} shops")

        db.commit()
        log.info(f"   ✅ Created {created} shops with owners, services, employees, and queues")

        # ── STEP 2: Shop Customers ──
        log.info("\n[2/5] Creating shop customer records...")
        cust_count = 0
        for sd in all_shops_data:
            num_customers = random.randint(20, 80)
            for _ in range(num_customers):
                fn = random.choice(CUSTOMER_FIRST)
                ln = random.choice(LAST_NAMES)
                code = PHONE_AREA_CODES.get(sd["city"], "416")
                phone = f"({code}) {random.randint(200,999)}-{random.randint(1000,9999)}"
                cust = ShopCustomer(
                    shop_id=sd["shop_id"],
                    name=f"{fn} {ln}",
                    phone=phone,
                    email=f"{fn.lower()}.{ln.lower()}{random.randint(1,999)}@gmail.com",
                    visit_count=random.randint(1, 30),
                    last_visit=datetime.utcnow() - timedelta(days=random.randint(0, 180)),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(30, 365 * 2)),
                )
                db.add(cust)
                cust_count += 1
            if cust_count % 2000 == 0:
                db.flush()
        db.commit()
        log.info(f"   ✅ Created {cust_count:,} customer records")

        # ── STEP 3: 3 Years DailyAnalytics ──
        if not skip_analytics:
            log.info(f"\n[3/5] Generating {years}-year analytics for {len(all_shops_data)} new shops...")
            end_date = date.today()
            start_date = end_date - timedelta(days=years * 365)
            raw_boundary = end_date - timedelta(days=60)

            analytics_count = 0
            queue_item_count = 0

            for shop_idx, sd in enumerate(all_shops_data):
                current = max(start_date, sd["created_date"])
                day_batch = []
                qi_batch = []

                while current <= end_date:
                    metrics = compute_daily_metrics(
                        shop_created=sd["created_date"],
                        day=current,
                        base_customers=sd["base_customers"],
                        avg_svc_cost=sd["avg_svc_cost"],
                        shop_popularity=sd["popularity"],
                    )
                    if metrics is None:
                        current += timedelta(days=1)
                        continue

                    day_batch.append(DailyAnalytics(
                        shop_id=sd["shop_id"],
                        date=current,
                        **metrics,
                    ))
                    analytics_count += 1

                    # Raw queue items for last 60 days
                    if current >= raw_boundary and sd["services"]:
                        for k in range(metrics["total_customers"]):
                            svc = random.choice(sd["services"])
                            status = QueueStatus.COMPLETED if random.random() > 0.08 else QueueStatus.CANCELLED
                            check_in = datetime.combine(current, datetime.min.time()) + \
                                       timedelta(hours=random.randint(8, 18), minutes=random.randint(0, 59))
                            wait_min = random.randint(2, 40)
                            svc_min = random.randint(10, 65)

                            qi_batch.append(QueueItem(
                                queue_id=sd["queue_id"],
                                customer_name=f"{random.choice(CUSTOMER_FIRST)} {random.choice(LAST_NAMES)}",
                                customer_phone=f"555-{random.randint(100,999)}-{random.randint(1000,9999)}",
                                position=k + 1,
                                status=status,
                                service_id=svc.id,
                                service_cost=svc.cost,
                                checked_in_at=check_in,
                                service_started_at=check_in + timedelta(minutes=wait_min) if status == QueueStatus.COMPLETED else None,
                                completed_at=check_in + timedelta(minutes=wait_min + svc_min) if status == QueueStatus.COMPLETED else None,
                            ))
                            queue_item_count += 1

                    # Batch flush
                    if len(day_batch) >= BATCH_SIZE:
                        db.add_all(day_batch)
                        day_batch.clear()
                    if len(qi_batch) >= BATCH_SIZE:
                        db.add_all(qi_batch)
                        qi_batch.clear()

                    current += timedelta(days=1)

                # Flush remaining
                if day_batch:
                    db.add_all(day_batch)
                    day_batch.clear()
                if qi_batch:
                    db.add_all(qi_batch)
                    qi_batch.clear()

                # Commit per shop to manage memory
                db.commit()

                if (shop_idx + 1) % 25 == 0:
                    log.info(f"   ... analytics for {shop_idx + 1}/{len(all_shops_data)} shops "
                             f"({analytics_count:,} days, {queue_item_count:,} queue items)")

            log.info(f"   ✅ Analytics: {analytics_count:,} daily records, {queue_item_count:,} queue items")
        else:
            log.info("\n[3/5] Skipping analytics generation (--skip-analytics)")

        # ── STEP 4: Twenty CRM ──
        if not skip_crm:
            log.info("\n[4/5] Populating Twenty CRM...")
            try:
                populate_twenty_crm(all_shops_data)
            except Exception as e:
                log.warning(f"   ⚠  CRM population failed (non-fatal): {e}")
        else:
            log.info("\n[4/5] Skipping CRM population (--skip-crm)")

        # ── STEP 5: Write credentials file ──
        log.info("\n[5/5] Writing credentials...")
        creds_path = os.path.join(os.path.dirname(__file__), "seed_500_accounts.txt")
        with open(creds_path, "w") as f:
            f.write(f"# ZeroQwait 500-Shop Seed Accounts — Generated {datetime.utcnow().isoformat()}\n")
            f.write(f"# Password for ALL accounts: {password}\n")
            f.write(f"# Total shops created in this run: {created}\n\n")
            for line in login_lines:
                f.write(line + "\n")

        log.info(f"   ✅ Credentials saved to: {creds_path}")

        # ── SUMMARY ──
        total_shops = db.query(Shop).count()
        total_users = db.query(User).count()
        total_analytics = db.query(DailyAnalytics).count()
        total_qi = db.query(QueueItem).count()

        log.info("\n" + "=" * 65)
        log.info("SEED COMPLETE — Summary")
        log.info("=" * 65)
        log.info(f"  Total shops in DB:      {total_shops:,}")
        log.info(f"  Total users:            {total_users:,}")
        log.info(f"  Total analytics days:   {total_analytics:,}")
        log.info(f"  Total queue items:      {total_qi:,}")
        log.info(f"  Credentials file:       {creds_path}")
        log.info(f"  Password for all:       {password}")
        log.info("")
        log.info("Sample logins:")
        for line in login_lines[:5]:
            log.info(f"  {line}")
        log.info(f"  ... and {len(login_lines) - 5} more (see seed_500_accounts.txt)")

    except Exception as e:
        log.error(f"❌ SEED ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZeroQwait 500-shop seed generator")
    parser.add_argument("--shops", type=int, default=500, help="Target number of shops (default: 500)")
    parser.add_argument("--years", type=int, default=3, help="Years of analytics history (default: 3)")
    parser.add_argument("--skip-analytics", action="store_true", help="Skip 3-year analytics generation")
    parser.add_argument("--skip-crm", action="store_true", help="Skip Twenty CRM population")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing data")
    parser.add_argument("--password", default="password123", help="Password for all accounts (default: password123)")
    args = parser.parse_args()

    seed(
        target_shops=args.shops,
        years=args.years,
        skip_analytics=args.skip_analytics,
        skip_crm=args.skip_crm,
        dry_run=args.dry_run,
        password=args.password,
    )
