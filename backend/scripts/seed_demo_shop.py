#!/usr/bin/env python3
"""
Realistic Demo Shop Seeder — "Prestige Cuts Barber Shop"
=========================================================
Seeds shop_id=4 with:
  - Refreshed shop profile + realistic services
  - 90 days of daily analytics (weekday/weekend patterns)
  - Active queue with waiting customers
  - Employee records
  - Odoo: company, products, contacts, CRM leads, invoices

Run inside K8s pod:
  kubectl exec -n zeroqwait deployment/backend -- python3 /app/scripts/seed_demo_shop.py

Run locally (with DB tunnel):
  python3 backend/scripts/seed_demo_shop.py
"""

import os, sys, random, socket
from datetime import date, datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from modules.shops.models import Shop, ShopService, DailyAnalytics
from modules.queues.models import Queue, QueueItem, QueueStatus
from modules.employees.models import ShopEmployee, EmployeeShift
from modules.auth.models import User

# ─── Config ──────────────────────────────────────────────────────────────────
SHOP_ID     = 4
OWNER_EMAIL = "owner_danielle_johnson_1@example-zeroqwait.com"

SHOP_NAME   = "Prestige Cuts Barber Shop"
SHOP_TYPE   = "barber_shop"
SHOP_ADDR   = "247 King Street West"
SHOP_CITY   = "Toronto"
SHOP_STATE  = "ON"
SHOP_ZIP    = "M5H 1J9"
SHOP_PHONE  = "+1-416-555-0192"
SHOP_EMAIL  = "info@prestigecuts.ca"
SHOP_SLUG   = "prestige-cuts-barber-toronto"
SHOP_DESC   = (
    "Premium men's grooming since 2018. Expert barbers, hot-towel shaves, "
    "and a relaxed atmosphere right in the heart of downtown Toronto."
)

SERVICES = [
    # (name, duration_min, cost)
    ("Men's Haircut",          25,  28.00),
    ("Beard Trim",             15,  18.00),
    ("Hot Towel Shave",        35,  38.00),
    ("Hair & Beard Combo",     45,  44.00),
    ("Kids Haircut (Under 12)",20,  22.00),
    ("Line-Up / Edge",         15,  15.00),
    ("Scalp Treatment",        20,  25.00),
    ("Hair Color",             60,  65.00),
]

EMPLOYEES = [
    # (first_name, last_name, role)
    ("Marcus",  "Williams", "barber"),
    ("Devon",   "Carter",   "barber"),
    ("Jaylen",  "Brooks",   "barber"),
    ("Sofia",   "Reyes",    "receptionist"),
]

CUSTOMER_NAMES = [
    "Alex Thompson", "Jordan Baker", "Malik Johnson", "Chris Davis",
    "Ryan Mitchell", "Tyler Green", "Brandon Lee", "Kevin Patel",
    "Daniel Kim", "James Wilson", "Andre Foster", "Mike Torres",
    "Sam Cooper", "Omar Hassan", "Liam Nguyen", "Aaron Price",
    "Isaac Brown", "Eric Morales", "Carlos Diaz", "Terrell Moore",
]

TODAY = date.today()
NOW   = datetime.now()


# ─── PostgreSQL seeding ───────────────────────────────────────────────────────

def seed_postgres():
    db = SessionLocal()
    try:
        # ── 1. Update shop profile ────────────────────────────────────────────
        shop = db.query(Shop).filter(Shop.id == SHOP_ID).first()
        if not shop:
            print(f"  !! Shop {SHOP_ID} not found — skipping")
            return None
        shop.name           = SHOP_NAME
        shop.shop_type      = SHOP_TYPE
        shop.description    = SHOP_DESC
        shop.address        = SHOP_ADDR
        shop.city           = SHOP_CITY
        shop.state          = SHOP_STATE
        shop.zip_code       = SHOP_ZIP
        shop.phone          = SHOP_PHONE
        shop.email          = SHOP_EMAIL
        shop.slug           = SHOP_SLUG
        shop.average_service_time = 25
        shop.ai_agent_name  = "Max"
        shop.latitude       = 43.6487
        shop.longitude      = -79.3928
        shop.is_active      = True
        db.flush()
        print(f"  ✓ Updated shop {SHOP_ID}: {SHOP_NAME}")

        # ── 2. Replace services (nullify FK on queue_items first) ────────────
        from sqlalchemy import text
        db.execute(text("UPDATE queue_items SET service_id = NULL WHERE service_id IN "
                        "(SELECT id FROM shop_services WHERE shop_id = :sid)"),
                   {"sid": SHOP_ID})
        db.flush()
        db.query(ShopService).filter(ShopService.shop_id == SHOP_ID).delete()
        service_objs = []
        for name, dur, cost in SERVICES:
            svc = ShopService(
                shop_id          = SHOP_ID,
                name             = name,
                duration_minutes = dur,
                cost             = Decimal(str(cost)),
                currency         = "CAD",
                is_active        = True,
            )
            db.add(svc)
            service_objs.append(svc)
        db.flush()
        print(f"  ✓ Seeded {len(SERVICES)} services")

        # ── 3. Employees (link to existing user if available) ─────────────────
        owner_user = db.query(User).filter(User.email == OWNER_EMAIL).first()
        owner_id   = owner_user.id if owner_user else 1
        # remove old employees for this shop
        db.query(ShopEmployee).filter(ShopEmployee.shop_id == SHOP_ID).delete()
        emp_users = db.query(User).filter(User.email.like("%employee%")).limit(4).all()
        emp_objs  = []
        for i, (fn, ln, role) in enumerate(EMPLOYEES):
            user = emp_users[i] if i < len(emp_users) else None
            emp  = ShopEmployee(
                shop_id    = SHOP_ID,
                user_id    = user.id if user else owner_id,
                is_active  = True,
                created_by = owner_id,
            )
            db.add(emp)
            emp_objs.append(emp)
        db.flush()
        print(f"  ✓ Seeded {len(emp_objs)} employees")

        # ── 4. Daily analytics — 90 days ─────────────────────────────────────
        db.query(DailyAnalytics).filter(DailyAnalytics.shop_id == SHOP_ID).delete()
        analytics_rows = []
        for days_ago in range(89, -1, -1):
            d     = TODAY - timedelta(days=days_ago)
            dow   = d.weekday()  # 0=Mon … 6=Sun
            # Weekends are busier; Mondays are slow
            if dow == 6:   # Sunday — closed / very light
                if random.random() < 0.3:
                    continue
                multiplier = 0.4
            elif dow == 5: # Saturday — peak
                multiplier = 1.6
            elif dow == 0: # Monday — slow
                multiplier = 0.7
            else:
                multiplier = 1.0 + random.uniform(-0.15, 0.25)

            base_customers = int(round(random.gauss(22, 4) * multiplier))
            base_customers = max(0, base_customers)
            completed      = int(base_customers * random.uniform(0.82, 0.97))
            cancelled      = base_customers - completed
            avg_cost       = random.uniform(28, 42)
            revenue        = round(completed * avg_cost, 2)
            avg_wait       = round(random.gauss(12, 3), 1)
            avg_service    = round(random.gauss(28, 5), 1)
            peak_hour      = random.choice([11, 12, 13, 14, 15, 16])
            peak_cust      = int(completed * random.uniform(0.12, 0.22))

            row = DailyAnalytics(
                shop_id                 = SHOP_ID,
                date                    = datetime(d.year, d.month, d.day),
                total_customers         = base_customers,
                completed_services      = completed,
                cancelled_services      = cancelled,
                total_revenue           = revenue,
                avg_wait_time_minutes   = max(0, avg_wait),
                avg_service_time_minutes= max(15, avg_service),
                peak_hour_start         = peak_hour,
                peak_hour_customers     = peak_cust,
            )
            db.add(row)
            analytics_rows.append(row)
        db.flush()
        print(f"  ✓ Seeded {len(analytics_rows)} daily analytics records")

        # ── 5. Active queue with waiting customers ────────────────────────────
        # Remove all old queue items for this shop's queues
        existing_queues = db.query(Queue).filter(Queue.shop_id == SHOP_ID).all()
        for q in existing_queues:
            db.query(QueueItem).filter(QueueItem.queue_id == q.id).delete()
        if existing_queues:
            active_queue = existing_queues[0]
            active_queue.is_active = True
            active_queue.name      = "Main Queue"
        else:
            active_queue = Queue(
                shop_id   = SHOP_ID,
                name      = "Main Queue",
                is_active = True,
            )
            db.add(active_queue)
        db.flush()

        # Waiting customers
        waiting_names = random.sample(CUSTOMER_NAMES, 5)
        svc_list_pairs = [(s.id, s.name, float(s.cost)) for s in service_objs]
        for pos, cname in enumerate(waiting_names, start=1):
            svc_id, svc_name, svc_cost = random.choice(svc_list_pairs)
            item = QueueItem(
                queue_id       = active_queue.id,
                customer_name  = cname,
                service_id     = svc_id,
                service_cost   = svc_cost,
                status         = QueueStatus.WAITING,
                position       = pos,
                checked_in_at  = NOW - timedelta(minutes=(len(waiting_names)-pos+1)*8 + random.randint(0, 5)),
                notes          = "",
                customer_phone = f"+1-416-555-{random.randint(1000,9999)}",
                customer_email = "",
            )
            db.add(item)

        # Also add a few completed today for realism
        completed_names = random.sample([n for n in CUSTOMER_NAMES if n not in waiting_names], 8)
        for i, cname in enumerate(completed_names):
            svc_id, svc_name, svc_cost = random.choice(svc_list_pairs)
            start_t = NOW - timedelta(hours=random.randint(1,6), minutes=random.randint(0,59))
            item = QueueItem(
                queue_id           = active_queue.id,
                customer_name      = cname,
                service_id         = svc_id,
                service_cost       = svc_cost,
                status             = QueueStatus.COMPLETED,
                position           = 0,
                checked_in_at      = start_t,
                service_started_at = start_t + timedelta(minutes=random.randint(5, 15)),
                completed_at       = start_t + timedelta(minutes=random.randint(20, 45)),
                notes              = "",
                customer_phone     = f"+1-416-555-{random.randint(1000,9999)}",
                customer_email     = "",
            )
            db.add(item)

        db.flush()
        print(f"  ✓ Queue seeded: {len(waiting_names)} waiting, {len(completed_names)} completed today")

        # ── 6. Today's analytics entry ────────────────────────────────────────
        today_analytics = db.query(DailyAnalytics).filter(
            DailyAnalytics.shop_id == SHOP_ID,
            DailyAnalytics.date    == datetime(TODAY.year, TODAY.month, TODAY.day),
        ).first()
        if not today_analytics:
            today_analytics = DailyAnalytics(shop_id=SHOP_ID, date=datetime(TODAY.year, TODAY.month, TODAY.day))
            db.add(today_analytics)
        today_analytics.total_customers        = len(completed_names) + len(waiting_names)
        today_analytics.completed_services     = len(completed_names)
        today_analytics.cancelled_services     = 1
        today_analytics.total_revenue          = round(sum(
            random.choice([s.cost for s in service_objs])
            for _ in range(len(completed_names))
        ), 2)
        today_analytics.avg_wait_time_minutes  = 11.4
        today_analytics.avg_service_time_minutes= 27.2
        today_analytics.peak_hour_start        = 13
        today_analytics.peak_hour_customers    = 3
        db.flush()
        print(f"  ✓ Today's analytics: {today_analytics.total_customers} customers, ${today_analytics.total_revenue} revenue")

        db.commit()
        print("  ✓ PostgreSQL commit complete")
        return shop
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


# ─── Odoo seeding ─────────────────────────────────────────────────────────────

def seed_odoo(odoo_company_id: int | None = None):
    """Seed Odoo with demo data and return the company_id."""
    import xmlrpc.client
    socket.setdefaulttimeout(20)

    odoo_url = os.environ.get("ODOO_URL", "http://localhost:8069")
    odoo_db  = os.environ.get("ODOO_DB",  "odoo")
    odoo_usr = os.environ.get("ODOO_USER","admin")
    odoo_pwd = os.environ.get("ODOO_PASSWORD", "admin")

    common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")
    uid    = common.authenticate(odoo_db, odoo_usr, odoo_pwd, {})
    if not uid:
        print("  !! Odoo auth failed — skipping Odoo seed")
        return None
    m = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/object")

    def call(model, method, args, kwargs=None):
        return m.execute_kw(odoo_db, uid, odoo_pwd, model, method, args, kwargs or {})

    # ── 1. Ensure company exists ──────────────────────────────────────────────
    comp_domain = [["name", "=", SHOP_NAME]]
    existing    = call("res.company", "search_read", [comp_domain], {"fields": ["id","name"], "limit": 1})
    if existing:
        company_id = existing[0]["id"]
        print(f"  ✓ Odoo company already exists: id={company_id}")
    else:
        company_id = call("res.company", "create", [{
            "name":    SHOP_NAME,
            "street":  SHOP_ADDR,
            "city":    SHOP_CITY,
            "phone":   SHOP_PHONE,
            "email":   SHOP_EMAIL,
            "website": "https://prestigecuts.ca",
        }])
        print(f"  ✓ Created Odoo company id={company_id}")

    # Save company_id back to shop
    db = SessionLocal()
    try:
        shop = db.query(Shop).filter(Shop.id == SHOP_ID).first()
        if shop:
            shop.odoo_company_id = company_id
            db.commit()
            print(f"  ✓ Linked shop {SHOP_ID} → odoo_company_id={company_id}")
    finally:
        db.close()

    # ── 2. Products (services as Odoo products) ───────────────────────────────
    for name, dur, cost in SERVICES:
        existing_prod = call("product.template", "search_read",
                             [[["name", "=", name]]], {"fields": ["id","name"], "limit": 1})
        if not existing_prod:
            call("product.template", "create", [{
                "name":          name,
                "type":          "service",
                "list_price":    cost,
                "description":   f"Duration: {dur} min",
                "categ_id":      1,
            }])
    print(f"  ✓ Products (services) synced to Odoo")

    # ── 3. Contacts (regular clients) ────────────────────────────────────────
    regular_clients = [
        ("Marcus Hall",   "marcus.hall@email.com",   "+1-416-555-2201"),
        ("Jordan Banks",  "jordan.banks@gmail.com",  "+1-416-555-2202"),
        ("Tyrone West",   "t.west@outlook.com",      "+1-647-555-2203"),
        ("Devon Clarke",  "devonc@email.ca",         "+1-416-555-2204"),
        ("Nathan Pierce", "nathan.p@gmail.com",       "+1-647-555-2205"),
        ("Elijah Turner", "e.turner@email.com",       "+1-416-555-2206"),
        ("Caleb Stone",   "cstone.haircut@gmail.com", "+1-647-555-2207"),
        ("Andre Lawson",  "andrelawson@proton.me",    "+1-416-555-2208"),
        ("Isaiah Grant",  "isaiah.g@gmail.com",       "+1-647-555-2209"),
        ("Kwame Asante",  "kasante@email.com",         "+1-416-555-2210"),
    ]
    contact_ids = []
    for fname, email, phone in regular_clients:
        existing_c = call("res.partner", "search_read",
                          [[["email", "=", email]]], {"fields": ["id"], "limit": 1})
        if existing_c:
            contact_ids.append(existing_c[0]["id"])
        else:
            cid = call("res.partner", "create", [{
                "name":      fname,
                "email":     email,
                "phone":     phone,
                "company_id": company_id,
                "comment":   "Regular client — loyalty tier: Gold",
            }])
            contact_ids.append(cid)
    print(f"  ✓ {len(contact_ids)} client contacts in Odoo")

    # ── 4. CRM Leads / Opportunities ─────────────────────────────────────────
    stages = call("crm.stage", "search_read", [[]], {"fields": ["id","name"], "limit": 10})
    stage_map = {s["name"]: s["id"] for s in stages}
    # typical CRM stages: New, Qualified, Proposition, Won, Lost
    stage_new  = stage_map.get("New",         stages[0]["id"] if stages else False)
    stage_qual = stage_map.get("Qualified",   stage_new)
    stage_prop = stage_map.get("Proposition", stage_new)
    stage_won  = stage_map.get("Won",         stage_new)

    leads_data = [
        # (name, contact_name, expected_revenue, stage_name, description)
        ("VIP Package Upsell — Marcus Hall",   "Marcus Hall",   150, "Qualified",
         "Marcus interested in monthly unlimited hot-towel shave subscription."),
        ("Corporate Grooming Contract — DevTech Inc", "DevTech HR",  2400, "Proposition",
         "Monthly grooming sessions for 8 employees. Proposal sent 2026-04-28."),
        ("New Walk-In Referral — Kwame Asante", "Kwame Asante",  80, "New",
         "Referral from Jordan Banks. First visit booked for May 6."),
        ("Loyalty Program Launch Sponsorship",  "Local Media Co", 500, "New",
         "Exploring partnership for loyalty card launch social media boost."),
        ("Wedding Grooming Package",            "Caleb Stone",   350, "Qualified",
         "Groom + 4 groomsmen package. Wedding date June 14, 2026."),
    ]
    lead_ids = []
    for lname, cname, rev, stage_name, desc in leads_data:
        existing_l = call("crm.lead", "search_read",
                          [[["name", "=", lname]]], {"fields": ["id"], "limit": 1})
        if existing_l:
            lead_ids.append(existing_l[0]["id"])
            continue
        stage_id = stage_map.get(stage_name, stage_new)
        lid = call("crm.lead", "create", [{
            "name":             lname,
            "contact_name":     cname,
            "expected_revenue": rev,
            "stage_id":         stage_id,
            "description":      desc,
            "company_id":       company_id,
        }])
        lead_ids.append(lid)
    print(f"  ✓ {len(lead_ids)} CRM leads seeded")

    # ── 5. Invoices (last 7 days of completed services) ───────────────────────
    today_dt = datetime.now()
    invoice_count = 0
    for days_ago in range(6, -1, -1):
        day = today_dt - timedelta(days=days_ago)
        day_customers = random.randint(8, 14)
        for _ in range(day_customers):
            svc_name, _, cost = random.choice(SERVICES)
            cid = random.choice(contact_ids) if contact_ids else False
            try:
                inv_id = call("account.move", "create", [{
                    "move_type":      "out_invoice",
                    "partner_id":     cid,
                    "invoice_date":   day.strftime("%Y-%m-%d"),
                    "company_id":     company_id,
                    "invoice_line_ids": [(0, 0, {
                        "name":      svc_name,
                        "quantity":  1,
                        "price_unit": cost,
                    })],
                }])
                # Confirm invoice
                call("account.move", "action_post", [[inv_id]])
                invoice_count += 1
            except Exception as e:
                pass  # Some Odoo configs restrict invoice creation
    print(f"  ✓ {invoice_count} invoices created (last 7 days)")
    return company_id


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Seeding Prestige Cuts demo shop ===")
    print("\n[1/2] PostgreSQL ...")
    seed_postgres()

    print("\n[2/2] Odoo ...")
    odoo_url = os.environ.get("ODOO_URL", "http://localhost:8069")
    print(f"  Odoo URL: {odoo_url}")
    try:
        company_id = seed_odoo()
        if company_id:
            print(f"\n  Odoo company_id={company_id} ✓")
        else:
            print("\n  Odoo skipped (not reachable or disabled)")
    except Exception as e:
        print(f"\n  Odoo error: {e}")

    print("\n=== Seed complete ===")
