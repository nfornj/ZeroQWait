"""
Tenant Manager — Schema-based multi-tenancy for ZeroQWait.

Architecture:
  - Free tier shops: data lives in the `public` schema (shared tables).
  - Premium shops: data lives in a dedicated `tenant_<shop_id>` schema.
  - Central tables (users, shops, agent data) always remain in `public`.

Isolated tables per tenant schema:
  queues, queue_items, shop_services, shop_employees, employee_shifts,
  daily_analytics, shop_close_days, shop_customers
"""

import logging
import re
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from database import engine, SessionLocal

logger = logging.getLogger(__name__)

# Tables that get their own copy in each tenant schema.
# These are all shop-scoped (every row has a shop_id FK).
TENANT_TABLES = [
    "shop_services",
    "shop_employees",
    "employee_shifts",
    "shop_close_days",
    "shop_customers",
    "daily_analytics",
    "queues",
    "queue_items",
]

# Regex to validate schema names (prevent SQL injection)
_SCHEMA_RE = re.compile(r"^tenant_\d+$")


def _schema_name(shop_id: int) -> str:
    return f"tenant_{shop_id}"


def _validate_schema(name: str) -> str:
    """Ensure the schema name is safe for use in SQL statements."""
    if not _SCHEMA_RE.match(name):
        raise ValueError(f"Invalid tenant schema name: {name}")
    return name


# ── Schema lifecycle ────────────────────────────────────────────────

def create_tenant_schema(db: Session, shop_id: int) -> str:
    """
    Provision an isolated schema for a premium shop.
    Creates the schema and replicates the structure of all TENANT_TABLES.
    Returns the schema name.
    """
    schema = _validate_schema(_schema_name(shop_id))
    logger.info("Creating tenant schema %s for shop %d", schema, shop_id)

    # Create the schema
    db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

    # Replicate each tenant table's structure (no data) into the new schema.
    for table in TENANT_TABLES:
        db.execute(text(
            f"CREATE TABLE IF NOT EXISTS {schema}.{table} "
            f"(LIKE public.{table} INCLUDING ALL)"
        ))

    db.commit()
    logger.info("Tenant schema %s created with %d tables", schema, len(TENANT_TABLES))
    return schema


def drop_tenant_schema(db: Session, shop_id: int) -> None:
    """
    Remove a tenant schema entirely.  Used during downgrade or cleanup.
    """
    schema = _validate_schema(_schema_name(shop_id))
    logger.warning("Dropping tenant schema %s for shop %d", schema, shop_id)
    db.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    db.commit()


def tenant_schema_exists(db: Session, shop_id: int) -> bool:
    schema = _schema_name(shop_id)
    result = db.execute(text(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"
    ), {"s": schema})
    return result.scalar() is not None


# ── Data migration ──────────────────────────────────────────────────

def migrate_to_premium(db: Session, shop_id: int) -> str:
    """
    Upgrade a shop from free (shared) to premium (isolated schema).

    Steps:
      1. Create the tenant schema + empty tables.
      2. Copy all shop-scoped rows from public → tenant schema.
      3. Delete the copied rows from public tables.
      4. Update shop.tenant_schema pointer.

    Returns the new schema name.
    """
    from modules.shops.models import Shop

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")
    if shop.tenant_schema:
        raise ValueError(f"Shop {shop_id} is already premium (schema: {shop.tenant_schema})")

    schema = create_tenant_schema(db, shop_id)

    # Order matters due to FK constraints.
    # queue_items depends on queues, so move queues first, then items.
    _copy_table(db, "shop_services",   schema, shop_id)
    _copy_table(db, "shop_employees",  schema, shop_id)
    _copy_table(db, "employee_shifts", schema, shop_id)
    _copy_table(db, "shop_close_days", schema, shop_id)
    _copy_table(db, "shop_customers",  schema, shop_id)
    _copy_table(db, "daily_analytics", schema, shop_id)
    _copy_table(db, "queues",          schema, shop_id)
    _copy_table(db, "queue_items",     schema, shop_id, fk_column="queue_id",
                fk_subquery=f"SELECT id FROM public.queues WHERE shop_id = {shop_id}")

    # Delete from public in reverse FK order
    _delete_from_public(db, "queue_items", shop_id, fk_column="queue_id",
                        fk_subquery=f"SELECT id FROM public.queues WHERE shop_id = {shop_id}")
    _delete_from_public(db, "queues",          shop_id)
    _delete_from_public(db, "daily_analytics", shop_id)
    _delete_from_public(db, "shop_customers",  shop_id)
    _delete_from_public(db, "shop_close_days", shop_id)
    _delete_from_public(db, "employee_shifts", shop_id)
    _delete_from_public(db, "shop_employees",  shop_id)
    _delete_from_public(db, "shop_services",   shop_id)

    # Point the shop to its new schema
    shop.tenant_schema = schema
    db.commit()

    logger.info("Shop %d migrated to premium schema %s", shop_id, schema)
    return schema


def migrate_to_free(db: Session, shop_id: int) -> None:
    """
    Downgrade a shop from premium back to free (shared).

    Steps:
      1. Copy rows from tenant schema → public.
      2. Drop tenant schema.
      3. Clear shop.tenant_schema.
    """
    from modules.shops.models import Shop

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")
    if not shop.tenant_schema:
        raise ValueError(f"Shop {shop_id} is already on the free tier")

    schema = _validate_schema(shop.tenant_schema)

    # Copy back to public (order: parents first)
    _copy_table_reverse(db, "shop_services",   schema, shop_id)
    _copy_table_reverse(db, "shop_employees",  schema, shop_id)
    _copy_table_reverse(db, "employee_shifts", schema, shop_id)
    _copy_table_reverse(db, "shop_close_days", schema, shop_id)
    _copy_table_reverse(db, "shop_customers",  schema, shop_id)
    _copy_table_reverse(db, "daily_analytics", schema, shop_id)
    _copy_table_reverse(db, "queues",          schema, shop_id)
    _copy_table_reverse(db, "queue_items",     schema, shop_id, fk_column="queue_id",
                        fk_subquery=f"SELECT id FROM {schema}.queues WHERE shop_id = {shop_id}")

    # Drop the entire schema
    drop_tenant_schema(db, shop_id)

    shop.tenant_schema = None
    db.commit()
    logger.info("Shop %d migrated back to free tier (shared)", shop_id)


# ── Session routing ─────────────────────────────────────────────────

@contextmanager
def tenant_session(shop_id: Optional[int] = None, db: Optional[Session] = None):
    """
    Context manager that yields a Session with the correct search_path.

    Usage:
        with tenant_session(shop_id=42) as session:
            queues = session.query(Queue).filter(Queue.shop_id == 42).all()

    If the shop has a tenant schema → search_path = 'tenant_42, public'
    Otherwise                       → search_path = 'public'  (default)
    """
    from modules.shops.models import Shop

    own_session = db is None
    session = db or SessionLocal()

    try:
        schema = None
        if shop_id:
            shop = session.query(Shop).filter(Shop.id == shop_id).first()
            if shop and shop.tenant_schema:
                schema = _validate_schema(shop.tenant_schema)

        if schema:
            session.execute(text(f"SET search_path TO {schema}, public"))
        else:
            session.execute(text("SET search_path TO public"))

        yield session

        if own_session:
            session.commit()
    except Exception:
        if own_session:
            session.rollback()
        raise
    finally:
        # Always reset search_path to avoid leaking tenant context
        session.execute(text("SET search_path TO public"))
        if own_session:
            session.close()


def get_tenant_session(shop_id: int):
    """
    FastAPI dependency generator — yields a session scoped to the given shop's
    tenant schema.  Use in endpoint signatures:

        @router.get("/shop/{shop_id}/queues")
        async def get_queues(shop_id: int, db: Session = Depends(get_tenant_session(shop_id))):
            ...

    For dynamic shop_id, use the `tenant_session()` context manager instead.
    """
    def _dep():
        with tenant_session(shop_id) as session:
            yield session
    return _dep


# ── Internal helpers ────────────────────────────────────────────────

def _copy_table(db: Session, table: str, schema: str, shop_id: int,
                fk_column: str = "shop_id", fk_subquery: Optional[str] = None):
    """Copy rows for a shop from public.<table> → <schema>.<table>."""
    _validate_schema(schema)
    if fk_subquery:
        sql = f"INSERT INTO {schema}.{table} SELECT * FROM public.{table} WHERE {fk_column} IN ({fk_subquery})"
    else:
        sql = f"INSERT INTO {schema}.{table} SELECT * FROM public.{table} WHERE {fk_column} = :sid"
    db.execute(text(sql), {"sid": shop_id} if not fk_subquery else {})


def _delete_from_public(db: Session, table: str, shop_id: int,
                        fk_column: str = "shop_id", fk_subquery: Optional[str] = None):
    """Delete rows for a shop from public.<table>."""
    if fk_subquery:
        sql = f"DELETE FROM public.{table} WHERE {fk_column} IN ({fk_subquery})"
    else:
        sql = f"DELETE FROM public.{table} WHERE {fk_column} = :sid"
    db.execute(text(sql), {"sid": shop_id} if not fk_subquery else {})


def _copy_table_reverse(db: Session, table: str, schema: str, shop_id: int,
                        fk_column: str = "shop_id", fk_subquery: Optional[str] = None):
    """Copy rows from <schema>.<table> → public.<table>."""
    _validate_schema(schema)
    if fk_subquery:
        sql = f"INSERT INTO public.{table} SELECT * FROM {schema}.{table} WHERE {fk_column} IN ({fk_subquery})"
    else:
        sql = f"INSERT INTO public.{table} SELECT * FROM {schema}.{table} WHERE {fk_column} = :sid"
    db.execute(text(sql), {"sid": shop_id} if not fk_subquery else {})


# ── Bulk operations ─────────────────────────────────────────────────

def list_tenant_schemas(db: Session) -> list[dict]:
    """List all tenant schemas and their associated shops."""
    from modules.shops.models import Shop
    shops = db.query(Shop).filter(Shop.tenant_schema.isnot(None)).all()
    return [
        {"shop_id": s.id, "name": s.name, "schema": s.tenant_schema, "slug": s.slug}
        for s in shops
    ]


def get_tenant_stats(db: Session, shop_id: int) -> dict:
    """Get row counts for all tenant tables (useful for monitoring)."""
    from modules.shops.models import Shop
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")

    schema = shop.tenant_schema or "public"
    if shop.tenant_schema:
        _validate_schema(schema)

    stats = {"shop_id": shop_id, "schema": schema, "tables": {}}
    for table in TENANT_TABLES:
        result = db.execute(text(f"SELECT COUNT(*) FROM {schema}.{table}"))
        stats["tables"][table] = result.scalar()
    return stats
