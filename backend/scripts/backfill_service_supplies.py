from __future__ import annotations

import argparse

from sqlalchemy import text

from agents.tools.service_supply_defaults import normalize_vertical, sync_shop_service_supplies
from database import SessionLocal


def _target_shops(shop_id: int | None, vertical: str | None) -> list[tuple[int, str, str]]:
    with SessionLocal() as session:
        if shop_id is not None:
            rows = session.execute(
                text("SELECT id, name, shop_type FROM platform.shops WHERE id = :shop_id"),
                {"shop_id": shop_id},
            ).fetchall()
        else:
            rows = session.execute(
                text("SELECT id, name, shop_type FROM platform.shops WHERE is_active = TRUE ORDER BY id"),
            ).fetchall()

    targets: list[tuple[int, str, str]] = []
    for row in rows:
        current_shop_id = int(row[0])
        name = str(row[1])
        shop_type = str(row[2] or "")
        normalized = normalize_vertical(shop_type)
        if vertical and normalized != vertical:
            continue
        targets.append((current_shop_id, name, shop_type))
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill default service supplies_used mappings for seeded shops.")
    parser.add_argument("--shop-id", type=int, help="Only backfill a single shop.")
    parser.add_argument(
        "--vertical",
        choices=["barbershop", "salon"],
        default="salon",
        help="Limit backfill to one normalized vertical.",
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Overwrite services that already have supplies_used configured.",
    )
    args = parser.parse_args()

    totals = {
        "shops": 0,
        "matched_services": 0,
        "updated_services": 0,
        "skipped_services": 0,
    }

    targets = _target_shops(args.shop_id, args.vertical)
    for current_shop_id, name, shop_type in targets:
        result = sync_shop_service_supplies(
            current_shop_id,
            shop_type,
            include_existing=args.include_existing,
        )
        totals["shops"] += 1
        totals["matched_services"] += int(result["matched_services"])
        totals["updated_services"] += int(result["updated_services"])
        totals["skipped_services"] += int(result["skipped_services"])
        print(
            f"shop={current_shop_id} name={name!r} vertical={result['vertical']} "
            f"matched={result['matched_services']} updated={result['updated_services']} skipped={result['skipped_services']}"
        )

    print(
        "SUMMARY "
        f"shops={totals['shops']} matched_services={totals['matched_services']} "
        f"updated_services={totals['updated_services']} skipped_services={totals['skipped_services']}"
    )


if __name__ == "__main__":
    main()