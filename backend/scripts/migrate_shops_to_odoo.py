"""Migrate existing shops to Odoo multi-company.

Creates an Odoo ``res.company`` for every shop that doesn't yet have
an ``odoo_company_id`` and persists the mapping.

Run from inside the backend container (or locally with correct env vars):

    python migrate_shops_to_odoo.py          # dry-run (default)
    python migrate_shops_to_odoo.py --apply  # actually create companies
"""

import argparse
import os
import sys
import time

# Ensure backend package is importable when running as a script
sys.path.insert(0, os.path.dirname(__file__))

# Import models to ensure all SQLAlchemy relationships are resolved
import models  # noqa: F401 — re-exports all models
from database import SessionLocal
from modules.shops.models import Shop
from integrations.odoo_client import OdooClient, ODOO_ENABLED


def migrate(dry_run: bool = True, batch_size: int = 50):
    if not ODOO_ENABLED:
        print("ERROR: ODOO_ENABLED is not true. Set ODOO_ENABLED=true and try again.")
        sys.exit(1)

    client = OdooClient()
    health = client.health_check()
    if health.get("status") != "ok":
        print(f"ERROR: Odoo health check failed: {health}")
        sys.exit(1)
    print(f"Odoo connection OK (version {health.get('version')})")

    db = SessionLocal()
    try:
        shops = (
            db.query(Shop)
            .filter(Shop.odoo_company_id.is_(None))
            .order_by(Shop.id)
            .all()
        )
        total = len(shops)
        print(f"Found {total} shops without Odoo company mapping.")

        if total == 0:
            print("Nothing to migrate.")
            return

        if dry_run:
            print("[DRY-RUN] Would create Odoo companies for:")
            for s in shops[:10]:
                print(f"  shop_id={s.id}  name={s.name!r}  city={getattr(s, 'city', None)}")
            if total > 10:
                print(f"  ... and {total - 10} more")
            print("\nRe-run with --apply to execute.")
            return

        created = 0
        failed = 0
        for i, shop in enumerate(shops, 1):
            result = client.create_company(
                name=shop.name,
                phone=getattr(shop, "phone", None),
                email=getattr(shop, "email", None),
                city=getattr(shop, "city", None),
            )
            if "id" in result:
                shop.odoo_company_id = result["id"]
                created += 1
                if created % batch_size == 0:
                    db.commit()
                    print(f"  [{i}/{total}] committed batch ({created} created so far)")
            else:
                failed += 1
                print(f"  WARN: shop_id={shop.id} ({shop.name!r}) failed: {result}")

            # Small pause to avoid hammering Odoo
            if i % 100 == 0:
                time.sleep(0.5)

        db.commit()
        print(f"\nDone. Created={created}, Failed={failed}, Total={total}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate shops to Odoo multi-company")
    parser.add_argument("--apply", action="store_true", help="Actually create companies (default is dry-run)")
    args = parser.parse_args()
    migrate(dry_run=not args.apply)
