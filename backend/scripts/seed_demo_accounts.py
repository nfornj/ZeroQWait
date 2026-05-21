"""
Comprehensive demo account seeding script for K8s/production DB.
Creates 11 demo accounts with shops, services, employees, queues,
queue items, appointments, and analytics history.

Accounts created:
  - demo_owner_premium@example.com (PREMIUM)  password: Test123!
  - demo_owner_free@example.com    (FREE)     password: Test123!
  - free_user_1..9@example.com     (FREE)     password: Test123!
"""

import sys
import random
from datetime import datetime, timedelta, date
from sqlalchemy import text

sys.path.insert(0, '/app')

from database import SessionLocal, engine
from shared.auth_utils import get_password_hash

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEMO_PASSWORD = "Test123!"

SHOP_TEMPLATES = [
    {"type": "Barbershop", "services": ["Haircut", "Beard Trim", "Shave", "Buzz Cut", "Hot Towel Shave"], "avg_time": 25},
    {"type": "Hair Salon", "services": ["Blowout", "Hair Coloring", "Highlights", "Keratin Treatment", "Trim"], "avg_time": 60},
    {"type": "Nail Salon", "services": ["Manicure", "Pedicure", "Gel Nails", "Acrylic Set", "Nail Art"], "avg_time": 45},
    {"type": "Spa", "services": ["Swedish Massage", "Deep Tissue", "Facial", "Body Scrub", "Hot Stone"], "avg_time": 60},
    {"type": "Dentist", "services": ["Cleaning", "X-Ray", "Filling", "Whitening", "Consultation"], "avg_time": 30},
    {"type": "Barbershop", "services": ["Classic Cut", "Fade", "Shape Up", "Beard Lineup", "Kids Cut"], "avg_time": 20},
    {"type": "Hair Salon", "services": ["Shampoo & Style", "Perm", "Relaxer", "Color Correction", "Deep Condition"], "avg_time": 90},
    {"type": "Nail Salon", "services": ["Basic Manicure", "Spa Pedicure", "Dip Powder", "Nail Repair", "Polish Change"], "avg_time": 40},
    {"type": "Barbershop", "services": ["Haircut", "Shave", "Mustache Trim", "Head Shave", "Eyebrow Shape"], "avg_time": 22},
    {"type": "Spa", "services": ["Aromatherapy", "Couples Massage", "Exfoliation", "Mud Wrap", "Hydrotherapy"], "avg_time": 75},
    {"type": "Hair Salon", "services": ["Balayage", "Ombre", "Cut & Style", "Toner", "Scalp Treatment"], "avg_time": 120},
]

EMPLOYEE_NAMES = [
    ("Alex", "Johnson"), ("Sam", "Williams"), ("Jordan", "Davis"), ("Taylor", "Brown"),
    ("Morgan", "Wilson"), ("Casey", "Moore"), ("Riley", "Thomas"), ("Drew", "Anderson"),
    ("Blake", "Jackson"), ("Avery", "White"), ("Quinn", "Harris"), ("Charlie", "Martin"),
]

CITIES = [
    ("New York", "NY", "10001", "America/New_York"),
    ("Los Angeles", "CA", "90001", "America/Los_Angeles"),
    ("Chicago", "IL", "60601", "America/Chicago"),
    ("Houston", "TX", "77001", "America/Chicago"),
    ("Phoenix", "AZ", "85001", "America/Phoenix"),
    ("Philadelphia", "PA", "19101", "America/New_York"),
    ("San Antonio", "TX", "78201", "America/Chicago"),
    ("San Diego", "CA", "92101", "America/Los_Angeles"),
    ("Dallas", "TX", "75201", "America/Chicago"),
    ("Austin", "TX", "73301", "America/Chicago"),
    ("Seattle", "WA", "98101", "America/Los_Angeles"),
]

DEMO_ACCOUNTS = [
    {"email": "demo_owner_premium@example.com", "username": "demo_owner_premium", "tier": "PREMIUM"},
    {"email": "demo_owner_free@example.com",    "username": "demo_owner_free",    "tier": "FREE"},
    {"email": "free_user_1@example.com",        "username": "free_user_1",        "tier": "FREE"},
    {"email": "free_user_2@example.com",        "username": "free_user_2",        "tier": "FREE"},
    {"email": "free_user_3@example.com",        "username": "free_user_3",        "tier": "FREE"},
    {"email": "free_user_4@example.com",        "username": "free_user_4",        "tier": "FREE"},
    {"email": "free_user_5@example.com",        "username": "free_user_5",        "tier": "FREE"},
    {"email": "free_user_6@example.com",        "username": "free_user_6",        "tier": "FREE"},
    {"email": "free_user_7@example.com",        "username": "free_user_7",        "tier": "FREE"},
    {"email": "free_user_8@example.com",        "username": "free_user_8",        "tier": "FREE"},
    {"email": "free_user_9@example.com",        "username": "free_user_9",        "tier": "FREE"},
]


def run():
    db = SessionLocal()
    hashed_pw = get_password_hash(DEMO_PASSWORD)
    created_shops = []

    try:
        print("=" * 60)
        print("FastCuts Demo Account & Data Seeder")
        print("=" * 60)

        # ---------------------------------------------------------------
        # Step 1: Create / verify demo user accounts
        # ---------------------------------------------------------------
        print("\n[1/6] Creating demo user accounts...")
        user_ids = {}
        for i, acct in enumerate(DEMO_ACCOUNTS):
            row = db.execute(
                text("SELECT id FROM users WHERE email = :e"),
                {"e": acct["email"]}
            ).fetchone()
            if row:
                uid = row[0]
                # Update password to Test123!
                db.execute(
                    text("UPDATE users SET hashed_password = :h, is_active = true WHERE id = :id"),
                    {"h": hashed_pw, "id": uid}
                )
                print(f"  ✓ EXISTS  {acct['email']} (id={uid}) — password reset to Test123!")
            else:
                result = db.execute(
                    text("""
                        INSERT INTO users (email, username, hashed_password, role, is_active, subscription_tier, created_at)
                        VALUES (:email, :username, :pw, 'SHOP_OWNER', true, :tier, NOW())
                        RETURNING id
                    """),
                    {
                        "email": acct["email"],
                        "username": acct["username"],
                        "pw": hashed_pw,
                        "tier": acct["tier"],
                    }
                )
                uid = result.scalar()
                print(f"  ✓ CREATED {acct['email']} (id={uid}) tier={acct['tier']}")
            user_ids[acct["email"]] = uid

        db.commit()

        # ---------------------------------------------------------------
        # Step 2: Create shops for each user (1 per user)
        # ---------------------------------------------------------------
        print("\n[2/6] Creating demo shops...")
        shop_ids = {}
        for i, acct in enumerate(DEMO_ACCOUNTS):
            uid = user_ids[acct["email"]]
            tmpl = SHOP_TEMPLATES[i]
            city, state, zip_code, timezone_name = CITIES[i]
            shop_name = f"Demo {tmpl['type']} ({acct['username']})"
            slug = acct["username"].replace("_", "-")

            # Check if shop already exists for this user
            row = db.execute(
                text("SELECT id FROM shops WHERE owner_id = :uid AND slug = :slug"),
                {"uid": uid, "slug": slug}
            ).fetchone()
            if row:
                sid = row[0]
                print(f"  ✓ EXISTS  shop '{shop_name}' (id={sid})")
            else:
                result = db.execute(
                    text("""
                        INSERT INTO shops (owner_id, name, shop_type, address, city, state, zip_code,
                            country, phone, email, average_service_time, slug, is_active, created_at)
                        VALUES (:oid, :name, :stype, :addr, :city, :state, :zip,
                            'US', :phone, :email, :avg_t, :slug, true, NOW())
                        RETURNING id
                    """),
                    {
                        "oid": uid,
                        "name": shop_name,
                        "stype": tmpl["type"],
                        "addr": f"{100 + i} Main St",
                        "city": city,
                        "state": state,
                        "zip": zip_code,
                        "phone": f"+15551{i:02d}0000",
                        "email": f"shop{i}@fastcuts-demo.com",
                        "avg_t": tmpl["avg_time"],
                        "slug": slug,
                    }
                )
                sid = result.scalar()
                print(f"  ✓ CREATED shop '{shop_name}' (id={sid})")

            shop_ids[acct["email"]] = sid

            db.execute(
                text(
                    """
                    INSERT INTO shop_operating_hours
                        (shop_id, open_time, close_time, timezone, auto_open_queue, auto_close_queue,
                         pre_close_buffer_minutes, auto_lock_joins, operating_days, created_at, updated_at)
                    VALUES
                        (:shop_id, '09:00:00', '17:00:00', :timezone, true, true,
                         15, true, ARRAY[1,2,3,4,5,6], NOW(), NOW())
                    ON CONFLICT (shop_id) DO UPDATE SET
                        timezone = EXCLUDED.timezone,
                        updated_at = NOW()
                    """
                ),
                {"shop_id": sid, "timezone": timezone_name},
            )

            created_shops.append({"shop_id": sid, "template": tmpl, "user_email": acct["email"]})

        db.commit()

        # ---------------------------------------------------------------
        # Step 3: Create services for each shop
        # ---------------------------------------------------------------
        print("\n[3/6] Creating services for each shop...")
        service_ids_by_shop = {}
        for info in created_shops:
            sid = info["shop_id"]
            tmpl = info["template"]
            service_ids_by_shop[sid] = []

            for j, svc_name in enumerate(tmpl["services"]):
                row = db.execute(
                    text("SELECT id FROM shop_services WHERE shop_id = :sid AND name = :n"),
                    {"sid": sid, "n": svc_name}
                ).fetchone()
                if row:
                    service_ids_by_shop[sid].append(row[0])
                else:
                    price = round(random.uniform(20, 150), 2)
                    duration = tmpl["avg_time"] + random.randint(-5, 20)
                    result = db.execute(
                        text("""
                            INSERT INTO shop_services (shop_id, name, duration_minutes, cost, is_active)
                            VALUES (:sid, :name, :dur, :cost, true)
                            RETURNING id
                        """),
                        {"sid": sid, "name": svc_name, "dur": duration, "cost": price}
                    )
                    service_ids_by_shop[sid].append(result.scalar())

        db.commit()
        print(f"  ✓ Services created for {len(created_shops)} shops")

        # ---------------------------------------------------------------
        # Step 4: Create employees for each shop
        # ---------------------------------------------------------------
        print("\n[4/6] Creating employees for each shop...")
        employee_ids_by_shop = {}
        for idx, info in enumerate(created_shops):
            sid = info["shop_id"]
            employee_ids_by_shop[sid] = []
            num_employees = random.randint(2, 4)

            for k in range(num_employees):
                fn, ln = EMPLOYEE_NAMES[(idx * 4 + k) % len(EMPLOYEE_NAMES)]
                emp_email = f"emp_{fn.lower()}_{ln.lower()}_{sid}_{k}@example.com"

                # Create user account for employee
                row = db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": emp_email}).fetchone()
                if row:
                    emp_user_id = row[0]
                else:
                    result = db.execute(
                        text("""
                            INSERT INTO users (email, username, hashed_password, role, is_active, subscription_tier, created_at)
                            VALUES (:email, :username, :pw, 'EMPLOYEE', true, 'FREE', NOW())
                            RETURNING id
                        """),
                        {"email": emp_email, "username": f"emp_{fn.lower()}_{sid}_{k}", "pw": hashed_pw}
                    )
                    emp_user_id = result.scalar()

                # Link to shop
                row2 = db.execute(
                    text("SELECT id FROM shop_employees WHERE shop_id = :sid AND user_id = :uid"),
                    {"sid": sid, "uid": emp_user_id}
                ).fetchone()
                if not row2:
                    result2 = db.execute(
                        text("""
                            INSERT INTO shop_employees (shop_id, user_id, is_active, employee_code, created_at)
                            VALUES (:sid, :uid, true, :code, NOW())
                            RETURNING id
                        """),
                        {"sid": sid, "uid": emp_user_id, "code": f"EMP{sid:03d}{k:02d}"}
                    )
                    employee_ids_by_shop[sid].append(result2.scalar())
                else:
                    employee_ids_by_shop[sid].append(row2[0])

        db.commit()
        print(f"  ✓ Employees created for {len(created_shops)} shops")

        # ---------------------------------------------------------------
        # Step 5: Create queues and queue items
        # ---------------------------------------------------------------
        print("\n[5/6] Creating queues and queue items...")
        today = date.today()
        customer_names = [
            "Alice Brown", "Bob Chen", "Carol Davis", "Dan Evans", "Eve Foster",
            "Frank Green", "Grace Hall", "Henry Irwin", "Irene Jones", "Jack King",
            "Karen Lee", "Liam Moore", "Maya Nelson", "Noah Parker", "Olivia Quinn",
        ]

        for info in created_shops:
            sid = info["shop_id"]
            svcs = service_ids_by_shop.get(sid, [])
            emps = employee_ids_by_shop.get(sid, [])

            # Create queues for last 30 days + today
            for days_back in range(29, -1, -1):
                q_date = today - timedelta(days=days_back)
                is_today = days_back == 0

                row = db.execute(
                    text("SELECT id FROM queues WHERE shop_id = :sid AND date = :d"),
                    {"sid": sid, "d": q_date}
                ).fetchone()

                if row:
                    qid = row[0]
                else:
                    result = db.execute(
                        text("""
                            INSERT INTO queues (shop_id, name, date, is_active, accepting_joins)
                            VALUES (:sid, :name, :d, :active, :accepting)
                            RETURNING id
                        """),
                        {
                            "sid": sid,
                            "name": f"Queue - {q_date.strftime('%b %d, %Y')}",
                            "d": q_date,
                            "active": is_today,
                            "accepting": is_today,
                        }
                    )
                    qid = result.scalar()

                # Add queue items (5-15 per queue)
                existing_count = db.execute(
                    text("SELECT COUNT(*) FROM queue_items WHERE queue_id = :qid"),
                    {"qid": qid}
                ).scalar()

                if existing_count == 0:
                    num_items = random.randint(5, 15)
                    for pos in range(1, num_items + 1):
                        cname = random.choice(customer_names)
                        svc_id = random.choice(svcs) if svcs else None
                        emp_id = random.choice(emps) if emps else None
                        cost = round(random.uniform(20, 120), 2)

                        if is_today and pos <= 2:
                            status = "COMPLETED"
                            checked_in = datetime.now() - timedelta(minutes=random.randint(90, 180))
                            started = checked_in + timedelta(minutes=random.randint(5, 15))
                            completed = started + timedelta(minutes=info["template"]["avg_time"] + random.randint(-5, 15))
                        elif is_today and pos == 3:
                            status = "BEING_SERVED"
                            checked_in = datetime.now() - timedelta(minutes=random.randint(30, 75))
                            started = checked_in + timedelta(minutes=random.randint(5, 15))
                            completed = None
                        elif is_today and pos > 3:
                            status = "WAITING"
                            checked_in = datetime.now() - timedelta(minutes=random.randint(5, 45))
                            started = None
                            completed = None
                        else:
                            status = random.choices(["COMPLETED", "CANCELLED", "CANCELLED"], weights=[70, 20, 10])[0]
                            base_time = datetime.combine(q_date, datetime.min.time()).replace(hour=9)
                            checked_in = base_time + timedelta(minutes=pos * 20 + random.randint(0, 10))
                            started = checked_in + timedelta(minutes=random.randint(5, 15))
                            completed = started + timedelta(minutes=info["template"]["avg_time"] + random.randint(-5, 15)) if status == "COMPLETED" else None

                        db.execute(
                            text("""
                                INSERT INTO queue_items
                                (queue_id, customer_name, customer_phone, customer_email, position,
                                 status, service_id, assigned_employee_id, service_cost,
                                 checked_in_at, service_started_at, completed_at)
                                VALUES (:qid, :cn, :cp, :ce, :pos, :status, :svc, :emp, :cost,
                                        :ci, :ss, :co)
                            """),
                            {
                                "qid": qid,
                                "cn": cname,
                                "cp": f"+1555{random.randint(1000000, 9999999)}",
                                "ce": f"{cname.lower().replace(' ', '.')}@example.com",
                                "pos": pos,
                                "status": status,
                                "svc": svc_id,
                                "emp": emp_id,
                                "cost": cost,
                                "ci": checked_in,
                                "ss": started,
                                "co": completed,
                            }
                        )

        db.commit()
        print(f"  ✓ Queues and queue items created for all shops (30 days of history)")

        # ---------------------------------------------------------------
        # Step 6: Create analytics history
        # ---------------------------------------------------------------
        print("\n[6/6] Creating analytics history (90 days)...")
        for info in created_shops:
            sid = info["shop_id"]
            for days_back in range(89, -1, -1):
                ana_date = today - timedelta(days=days_back)
                row = db.execute(
                    text("SELECT id FROM daily_analytics WHERE shop_id = :sid AND date = :d"),
                    {"sid": sid, "d": ana_date}
                ).fetchone()
                if not row:
                    total = random.randint(8, 35)
                    completed = int(total * random.uniform(0.65, 0.90))
                    cancelled = random.randint(1, max(1, total - completed - 2))
                    revenue = round(completed * random.uniform(35, 85), 2)
                    avg_wait = random.randint(8, 25)
                    avg_svc = info["template"]["avg_time"] + random.randint(-5, 10)
                    peak_hr = random.randint(10, 16)
                    peak_cust = random.randint(3, 8)
                    db.execute(
                        text("""
                            INSERT INTO daily_analytics
                            (shop_id, date, total_customers, completed_services, cancelled_services,
                             total_revenue, avg_wait_time_minutes, avg_service_time_minutes,
                             peak_hour_start, peak_hour_customers, created_at)
                            VALUES (:sid, :d, :tc, :cs, :canc, :rev, :awt, :ast, :ph, :pc, NOW())
                        """),
                        {
                            "sid": sid, "d": ana_date, "tc": total, "cs": completed,
                            "canc": cancelled, "rev": revenue, "awt": avg_wait,
                            "ast": avg_svc, "ph": peak_hr, "pc": peak_cust
                        }
                    )
        db.commit()
        print(f"  ✓ Analytics history created for all shops (90 days)")

        # ---------------------------------------------------------------
        # Summary
        # ---------------------------------------------------------------
        print("\n" + "=" * 60)
        print("SEEDING COMPLETE — Summary:")
        print("=" * 60)
        for acct in DEMO_ACCOUNTS:
            uid = user_ids[acct["email"]]
            sid = shop_ids[acct["email"]]
            svc_count = len(service_ids_by_shop.get(sid, []))
            emp_count = len(employee_ids_by_shop.get(sid, []))
            print(f"  {acct['email']:45s} | user_id={uid} | shop_id={sid} | svcs={svc_count} | emps={emp_count}")
        print()
        print("Login credentials: password = Test123!")
        print("Backend: http://localhost:30000")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        import traceback
        print(f"\n❌ SEEDING FAILED: {e}")
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
