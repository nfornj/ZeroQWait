#!/usr/bin/env python3
"""Copy one premium shop from the shared database into its dedicated database.

The script assumes the dedicated DB has already been initialized with the normal
ZeroQwait schema. It copies the shop row, directly related platform rows, selected
user rows, and all tenant_<shop_id> tables.
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Iterable

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import NoSuchTableError

TENANT_TABLE_ORDER = [
    "shop_services",
    "shop_employees",
    "employee_shifts",
    "shop_close_days",
    "shop_customers",
    "daily_analytics",
    "queues",
    "queue_items",
]

PLATFORM_TABLE_ORDER = [
    "users",
    "shops",
    "shop_runtime_assignments",
]

PLATFORM_SHOP_SCOPED_TABLES = [
    "audit_logs",
    "notification_log",
]


def _env(prefix: str, key: str, default: str | None = None) -> str:
    value = os.getenv(f"{prefix}_{key}") or (os.getenv(key) if prefix == "SOURCE" else None) or default
    if value is None:
        raise RuntimeError(f"Missing {prefix}_{key}")
    return value


def _engine(prefix: str) -> Engine:
    host = _env(prefix, "DB_HOST")
    port = _env(prefix, "DB_PORT", "5432")
    name = _env(prefix, "DB_NAME")
    user = _env(prefix, "DB_USER")
    password = _env(prefix, "DB_PASSWORD")
    return create_engine(f"postgresql://{user}:{password}@{host}:{port}/{name}", pool_pre_ping=True)


def _table(engine: Engine, schema: str, name: str) -> Table:
    metadata = MetaData()
    return Table(name, metadata, schema=schema, autoload_with=engine)


def _rows(engine: Engine, schema: str, table_name: str, where_sql: str | None = None, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    table = _table(engine, schema, table_name)
    query = select(table)
    if where_sql:
        query = query.where(text(where_sql))
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(query, params or {}).mappings().all()]


def _insert_rows(engine: Engine, schema: str, table_name: str, rows: list[dict[str, Any]], dry_run: bool) -> int:
    if not rows:
        return 0
    table = _table(engine, schema, table_name)
    pk_columns = [column.name for column in table.primary_key.columns]
    if dry_run:
        return len(rows)
    statement = pg_insert(table).values(rows)
    if pk_columns:
        statement = statement.on_conflict_do_nothing(index_elements=pk_columns)
    else:
        statement = statement.on_conflict_do_nothing()
    with engine.begin() as conn:
        result = conn.execute(statement)
    return int(result.rowcount or 0)


def _sync_missing_columns(source: Engine, target: Engine, schema: str, table_name: str, dry_run: bool) -> None:
    source_table = _table(source, schema, table_name)
    target_table = _table(target, schema, table_name)
    target_columns = {column.name for column in target_table.columns}
    preparer = target.dialect.identifier_preparer
    statements: list[str] = []

    for column in source_table.columns:
        if column.name in target_columns:
            continue
        column_type = column.type.compile(dialect=target.dialect)
        if not column_type:
            column_type = "TEXT"
        statements.append(
            "ALTER TABLE "
            f"{preparer.quote_schema(schema)}.{preparer.quote(table_name)} "
            f"ADD COLUMN IF NOT EXISTS {preparer.quote(column.name)} {column_type}"
        )

    if not statements:
        return
    if dry_run:
        print(f"{schema}.{table_name}: would add {len(statements)} missing columns")
        return
    with target.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    print(f"{schema}.{table_name}: added {len(statements)} missing columns")


def _reset_sequence(engine: Engine, schema: str, table_name: str, dry_run: bool) -> None:
    if dry_run:
        return
    with engine.begin() as conn:
        sequence = conn.execute(
            text("SELECT pg_get_serial_sequence(:qualified_table, 'id')"),
            {"qualified_table": f"{schema}.{table_name}"},
        ).scalar()
        if not sequence:
            return
        conn.execute(
            text(
                "SELECT setval(:sequence_name, "
                "GREATEST(COALESCE((SELECT max(id) FROM " + schema + "." + table_name + "), 1), 1), true)"
            ),
            {"sequence_name": sequence},
        )


def _ensure_tenant_tables(target: Engine, tenant_schema: str, dry_run: bool) -> None:
    if dry_run:
        return
    with target.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {tenant_schema}"))
        for table_name in TENANT_TABLE_ORDER:
            conn.execute(text(
                f"CREATE TABLE IF NOT EXISTS {tenant_schema}.{table_name} "
                f"(LIKE platform.{table_name} INCLUDING ALL)"
            ))


def _user_ids_for_shop(source: Engine, shop_id: int, tenant_schema: str) -> set[int]:
    user_ids: set[int] = set()
    shop_rows = _rows(source, "platform", "shops", "id = :shop_id", {"shop_id": shop_id})
    for row in shop_rows:
        owner_id = row.get("owner_id")
        if owner_id is not None:
            user_ids.add(int(owner_id))

    inspector = inspect(source)
    tenant_tables = set(inspector.get_table_names(schema=tenant_schema))
    for table_name in ("shop_employees", "employee_shifts", "queue_items"):
        if table_name not in tenant_tables:
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name, schema=tenant_schema)}
        if "user_id" not in columns:
            continue
        for row in _rows(source, tenant_schema, table_name, "user_id IS NOT NULL"):
            user_ids.add(int(row["user_id"]))
    return user_ids


def _copy_table(source: Engine, target: Engine, schema: str, table_name: str, rows: list[dict[str, Any]], dry_run: bool) -> tuple[int, int]:
    _sync_missing_columns(source, target, schema, table_name, dry_run)
    inserted = _insert_rows(target, schema, table_name, rows, dry_run)
    _reset_sequence(target, schema, table_name, dry_run)
    return len(rows), inserted


def _copy_platform_shop_data(source: Engine, target: Engine, shop_id: int, tenant_schema: str, dry_run: bool) -> None:
    inspector = inspect(source)
    platform_tables = set(inspector.get_table_names(schema="platform"))

    user_ids = _user_ids_for_shop(source, shop_id, tenant_schema)
    if "users" in platform_tables and user_ids:
        rows = _rows(source, "platform", "users", "id = ANY(:user_ids)", {"user_ids": list(user_ids)})
        total, inserted = _copy_table(source, target, "platform", "users", rows, dry_run)
        print(f"platform.users: copied {inserted}/{total}")

    if "shops" in platform_tables:
        rows = _rows(source, "platform", "shops", "id = :shop_id", {"shop_id": shop_id})
        total, inserted = _copy_table(source, target, "platform", "shops", rows, dry_run)
        print(f"platform.shops: copied {inserted}/{total}")

    if "shop_runtime_assignments" in platform_tables:
        rows = _rows(source, "platform", "shop_runtime_assignments", "shop_id = :shop_id", {"shop_id": shop_id})
        total, inserted = _copy_table(source, target, "platform", "shop_runtime_assignments", rows, dry_run)
        print(f"platform.shop_runtime_assignments: copied {inserted}/{total}")

    for table_name in PLATFORM_SHOP_SCOPED_TABLES:
        if table_name not in platform_tables:
            continue
        rows = _rows(source, "platform", table_name, "shop_id = :shop_id", {"shop_id": shop_id})
        total, inserted = _copy_table(source, target, "platform", table_name, rows, dry_run)
        if total:
            print(f"platform.{table_name}: copied {inserted}/{total}")


def _copy_tenant_data(source: Engine, target: Engine, shop_id: int, tenant_schema: str, dry_run: bool) -> None:
    for table_name in TENANT_TABLE_ORDER:
        try:
            rows = _rows(source, tenant_schema, table_name)
            total, inserted = _copy_table(source, target, tenant_schema, table_name, rows, dry_run)
        except NoSuchTableError:
            print(f"{tenant_schema}.{table_name}: skipped missing table")
            continue
        print(f"{tenant_schema}.{table_name}: copied {inserted}/{total}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate one shop into its dedicated premium database")
    parser.add_argument("--shop-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tenant_schema = f"tenant_{args.shop_id}"
    source = _engine("SOURCE")
    target = _engine("TARGET")

    _ensure_tenant_tables(target, tenant_schema, args.dry_run)

    _copy_platform_shop_data(source, target, args.shop_id, tenant_schema, args.dry_run)
    _copy_tenant_data(source, target, args.shop_id, tenant_schema, args.dry_run)


if __name__ == "__main__":
    main()
