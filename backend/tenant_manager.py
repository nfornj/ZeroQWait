"""
Tenant Manager — shop-scoped schema isolation primitives for ZeroQWait.

Current runtime behavior remains legacy-compatible:
    - Shared/public data plane: shop rows live in `public`
    - Shop-schema data plane: shop rows live in `tenant_<shop_id>`
    - Central tables (users, shops, agent data) always remain in `public`

The newer `shops.data_isolation_mode` and `shops.compute_mode` fields make the
runtime topology explicit so the platform no longer has to infer everything
from subscription tier and `tenant_schema` nullability alone.

Isolated tables per shop schema:
    queues, queue_items, shop_services, shop_employees, employee_shifts,
    daily_analytics, shop_close_days, shop_customers
"""

import logging
import re
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from database import engine, SessionLocal
from redis_client import redis_client

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


def data_isolation_mode_for_shop(shop) -> str:
    """Return the effective data isolation mode for a shop row."""
    if getattr(shop, "data_isolation_mode", None):
        return str(shop.data_isolation_mode)
    if getattr(shop, "tenant_schema", None):
        return "shop_schema"
    return "shared_public"


def compute_mode_for_shop(shop) -> str:
    """Return the effective compute mode for a shop row."""
    return str(getattr(shop, "compute_mode", None) or "shared_instance")


def resolve_shop_schema(shop) -> Optional[str]:
    """Resolve the schema name to use for a shop-scoped request, if any."""
    schema = getattr(shop, "tenant_schema", None)
    if schema:
        return _validate_schema(schema)
    if data_isolation_mode_for_shop(shop) == "shop_schema":
        return _validate_schema(_schema_name(int(shop.id)))
    return None


def resolve_shop_schema_from_metadata(shop: dict) -> Optional[str]:
    """Resolve a schema name from direct-SQL shop metadata."""
    schema = shop.get("tenant_schema")
    if schema:
        return _validate_schema(str(schema))
    if shop.get("data_isolation_mode") == "shop_schema":
        return _validate_schema(_schema_name(int(shop["id"])))
    return None


def _load_orm_registry() -> None:
    """Ensure SQLAlchemy relationship targets are registered for scripts."""
    import models  # noqa: F401


def _get_shop_metadata(db: Session, shop_id: int) -> Optional[dict]:
    row = db.execute(text(
        """
        SELECT id, owner_id, name, slug, tenant_schema, data_isolation_mode, compute_mode
        FROM platform.shops
        WHERE id = :sid
        """
    ), {"sid": shop_id}).mappings().first()
    return dict(row) if row else None


# ── Schema lifecycle ────────────────────────────────────────────────

def create_tenant_schema(db: Session, shop_id: int) -> str:
    """
    Provision an isolated schema for a shop.
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


def ensure_shop_schema(db: Session, shop_id: int, *, mark_isolated: bool = True) -> str:
    """
    Ensure a shop has an isolated schema and tenant metadata.

    This is the tier-neutral primitive for the new model: free and premium shops
    both use one schema per shop. Premium compute assignment is handled
    separately by runtime-assignment helpers below.
    """
    shop = _get_shop_metadata(db, shop_id)
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")

    schema = shop.get("tenant_schema") or _schema_name(shop_id)
    schema = _validate_schema(schema)
    create_tenant_schema(db, shop_id)

    if mark_isolated:
        db.execute(text(
            """
            UPDATE platform.shops
            SET tenant_schema = :schema, data_isolation_mode = 'shop_schema'
            WHERE id = :sid
            """
        ), {"schema": schema, "sid": shop_id})
        db.commit()

    return schema


def validate_shop_schema_copy(db: Session, shop_id: int) -> dict:
    """Return source/target row counts for a shop schema backfill."""
    shop = _get_shop_metadata(db, shop_id)
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")

    schema = resolve_shop_schema_from_metadata(shop) or _schema_name(shop_id)
    schema = _validate_schema(schema)
    if not tenant_schema_exists(db, shop_id):
        raise ValueError(f"Schema {schema} does not exist for shop {shop_id}")

    counts = {}
    for table in TENANT_TABLES:
        if table == "queue_items":
            public_count = _count_table(
                db,
                "queue_items",
                "public",
                shop_id,
                fk_column="queue_id",
                fk_subquery=f"SELECT id FROM public.queues WHERE shop_id = {shop_id}",
            )
            schema_count = _count_table(
                db,
                "queue_items",
                schema,
                shop_id,
                fk_column="queue_id",
                fk_subquery=f"SELECT id FROM {schema}.queues WHERE shop_id = {shop_id}",
            )
        else:
            public_count = _count_table(db, table, "public", shop_id)
            schema_count = _count_table(db, table, schema, shop_id)
        counts[table] = {
            "public": public_count,
            "schema": schema_count,
            "matches": schema_count >= public_count,
        }

    return {
        "shop_id": shop_id,
        "schema": schema,
        "valid": all(v["matches"] for v in counts.values()),
        "tables": counts,
    }


def migrate_shop_to_schema(db: Session, shop_id: int, *, delete_public: bool = False) -> dict:
    """
    Copy shop-scoped rows from public into the shop schema.

    The default is non-destructive so a free-shop backfill can be validated
    before public copies are removed. Set delete_public=True only after counts
    are verified for the target environment.
    """
    schema = ensure_shop_schema(db, shop_id, mark_isolated=False)

    _copy_table(db, "shop_services", schema, shop_id)
    _copy_table(db, "shop_employees", schema, shop_id)
    _copy_table(db, "employee_shifts", schema, shop_id)
    _copy_table(db, "shop_close_days", schema, shop_id)
    _copy_table(db, "shop_customers", schema, shop_id)
    _copy_table(db, "daily_analytics", schema, shop_id)
    _copy_table(db, "queues", schema, shop_id)
    _copy_table(
        db,
        "queue_items",
        schema,
        shop_id,
        fk_column="queue_id",
        fk_subquery=f"SELECT id FROM public.queues WHERE shop_id = {shop_id}",
    )

    validation = validate_shop_schema_copy(db, shop_id)
    if not validation["valid"]:
        db.rollback()
        raise ValueError(f"Schema copy validation failed for shop {shop_id}: {validation}")

    if delete_public:
        _delete_from_public(
            db,
            "queue_items",
            shop_id,
            fk_column="queue_id",
            fk_subquery=f"SELECT id FROM public.queues WHERE shop_id = {shop_id}",
        )
        _delete_from_public(db, "queues", shop_id)
        _delete_from_public(db, "daily_analytics", shop_id)
        _delete_from_public(db, "shop_customers", shop_id)
        _delete_from_public(db, "shop_close_days", shop_id)
        _delete_from_public(db, "employee_shifts", shop_id)
        _delete_from_public(db, "shop_employees", shop_id)
        _delete_from_public(db, "shop_services", shop_id)

    db.execute(text(
        """
        UPDATE platform.shops
        SET tenant_schema = :schema, data_isolation_mode = 'shop_schema'
        WHERE id = :sid
        """
    ), {"schema": schema, "sid": shop_id})
    db.commit()

    validation = validate_shop_schema_copy(db, shop_id)
    validation["public_deleted"] = delete_public
    return validation


def assign_dedicated_runtime(
    db: Session,
    shop_id: int,
    *,
    instance_key: Optional[str] = None,
    namespace: str = "zeroqwait",
    backend_service: Optional[str] = None,
    worker_service: Optional[str] = None,
    route_host: Optional[str] = None,
    runtime_status: str = "pending_deploy",
) -> dict:
    """Record that a shop should run on dedicated backend/agent compute."""
    shop = _get_shop_metadata(db, shop_id)
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")

    schema = resolve_shop_schema_from_metadata(shop)
    if not schema:
        schema = migrate_shop_to_schema(db, shop_id, delete_public=False)["schema"]
        shop = _get_shop_metadata(db, shop_id) or shop
    safe_slug = re.sub(r"[^a-z0-9-]", "-", ((shop.get("slug") or f"shop-{shop_id}").lower())).strip("-")
    key = instance_key or f"premium-{safe_slug or shop_id}"
    backend_service_value = backend_service or f"backend-{key}"
    worker_service_value = worker_service or f"temporal-worker-{key}"
    route_host_value = route_host or (f"{shop.get('slug')}.zeroqwait.com" if shop.get("slug") else None)
    assigned_at = datetime.utcnow()
    db.execute(text(
        """
        INSERT INTO platform.shop_runtime_assignments (
            shop_id, runtime_mode, instance_key, namespace, backend_service,
            worker_service, route_host, runtime_status, assigned_at, created_at, updated_at
        ) VALUES (
            :shop_id, 'dedicated_instance', :instance_key, :namespace,
            :backend_service, :worker_service, :route_host, :runtime_status,
            :assigned_at, :assigned_at, :assigned_at
        )
        ON CONFLICT (shop_id) DO UPDATE SET
            runtime_mode = EXCLUDED.runtime_mode,
            instance_key = EXCLUDED.instance_key,
            namespace = EXCLUDED.namespace,
            backend_service = EXCLUDED.backend_service,
            worker_service = EXCLUDED.worker_service,
            route_host = EXCLUDED.route_host,
            runtime_status = EXCLUDED.runtime_status,
            assigned_at = EXCLUDED.assigned_at,
            updated_at = EXCLUDED.updated_at
        """
    ), {
        "shop_id": shop_id,
        "instance_key": key,
        "namespace": namespace,
        "backend_service": backend_service_value,
        "worker_service": worker_service_value,
        "route_host": route_host_value,
        "runtime_status": runtime_status,
        "assigned_at": assigned_at,
    })
    db.execute(text(
        "UPDATE platform.shops SET compute_mode = 'dedicated_instance' WHERE id = :sid"
    ), {"sid": shop_id})
    db.commit()

    return {
        "shop_id": shop_id,
        "schema": schema,
        "runtime_mode": "dedicated_instance",
        "instance_key": key,
        "namespace": namespace,
        "backend_service": backend_service_value,
        "worker_service": worker_service_value,
        "route_host": route_host_value,
        "runtime_status": runtime_status,
    }


def assign_shared_runtime(db: Session, shop_id: int, *, runtime_status: str = "shared") -> dict:
    """Record that a shop should run on the shared backend/agent compute.

    This intentionally does not create or switch schemas. Data isolation is a
    separate operation; shared compute can serve either legacy public data or an
    already schema-isolated shop during the transition.
    """
    shop = _get_shop_metadata(db, shop_id)
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")

    schema = resolve_shop_schema_from_metadata(shop)
    db.execute(text("DELETE FROM platform.shop_runtime_assignments WHERE shop_id = :sid"), {"sid": shop_id})
    db.execute(text(
        "UPDATE platform.shops SET compute_mode = 'shared_instance' WHERE id = :sid"
    ), {"sid": shop_id})
    db.commit()

    return {
        "shop_id": shop_id,
        "schema": schema,
        "runtime_mode": "shared_instance",
        "backend_service": "backend",
        "worker_service": "temporal-worker",
        "runtime_status": runtime_status,
    }


# ── Data migration ──────────────────────────────────────────────────

def migrate_to_premium(db: Session, shop_id: int) -> str:
    """
    Legacy helper: migrate a shared/public shop into a shop-specific schema.

    Steps:
      1. Create the tenant schema + empty tables.
      2. Copy all shop-scoped rows from public → tenant schema.
      3. Delete the copied rows from public tables.
      4. Update shop.tenant_schema pointer.

    Returns the new schema name.
    """
    shop = _get_shop_metadata(db, shop_id)
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")
    if shop.get("tenant_schema"):
        raise ValueError(f"Shop {shop_id} is already schema-isolated (schema: {shop['tenant_schema']})")

    result = migrate_shop_to_schema(db, shop_id, delete_public=True)
    schema = result["schema"]

    logger.info("Shop %d migrated to premium schema %s", shop_id, schema)
    return schema


def migrate_to_free(db: Session, shop_id: int) -> None:
    """
    Legacy helper: migrate a shop-specific schema back into public.

    Steps:
      1. Copy rows from tenant schema → public.
      2. Drop tenant schema.
      3. Clear shop.tenant_schema.
    """
    shop = _get_shop_metadata(db, shop_id)
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")
    if not shop.get("tenant_schema"):
        raise ValueError(f"Shop {shop_id} is already on the free tier")

    schema = _validate_schema(shop["tenant_schema"])

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

    # Flush all tenant-scoped Redis keys
    redis_client.tenant_flush(shop_id)

    db.execute(text(
        """
        UPDATE platform.shops
        SET tenant_schema = NULL,
            data_isolation_mode = 'shared_public',
            compute_mode = 'shared_instance'
        WHERE id = :sid
        """
    ), {"sid": shop_id})
    db.execute(text("DELETE FROM platform.shop_runtime_assignments WHERE shop_id = :sid"), {"sid": shop_id})
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

    If the shop is schema-isolated → search_path = 'tenant_<shop_id>, public'
    Otherwise                      → search_path = 'public'  (default)
    """
    own_session = db is None
    session = db or SessionLocal()

    try:
        schema = None
        if shop_id:
            shop = _get_shop_metadata(session, shop_id)
            if shop:
                schema = resolve_shop_schema_from_metadata(shop)

        if schema:
            session.execute(text(f"SET search_path TO {schema}, platform, public"))
        else:
            session.execute(text("SET search_path TO platform, public"))

        yield session

        if own_session:
            session.commit()
    except Exception:
        if own_session:
            session.rollback()
        raise
    finally:
        # Always reset search_path to avoid leaking tenant context
        session.execute(text("SET search_path TO platform, public"))
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
        sql = f"INSERT INTO {schema}.{table} SELECT * FROM public.{table} WHERE {fk_column} IN ({fk_subquery}) ON CONFLICT DO NOTHING"
    else:
        sql = f"INSERT INTO {schema}.{table} SELECT * FROM public.{table} WHERE {fk_column} = :sid ON CONFLICT DO NOTHING"
    db.execute(text(sql), {"sid": shop_id} if not fk_subquery else {})


def _count_table(db: Session, table: str, schema: str, shop_id: int,
                 fk_column: str = "shop_id", fk_subquery: Optional[str] = None) -> int:
    """Count rows for a shop in public or a validated tenant schema."""
    if schema != "public":
        _validate_schema(schema)
    if fk_subquery:
        sql = f"SELECT COUNT(*) FROM {schema}.{table} WHERE {fk_column} IN ({fk_subquery})"
        return int(db.execute(text(sql)).scalar() or 0)
    sql = f"SELECT COUNT(*) FROM {schema}.{table} WHERE {fk_column} = :sid"
    return int(db.execute(text(sql), {"sid": shop_id}).scalar() or 0)


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
    """List all schema-isolated shops and their associated schemas."""
    rows = db.execute(text(
        """
        SELECT id, name, slug, tenant_schema, data_isolation_mode, compute_mode
        FROM platform.shops
        ORDER BY id
        """
    )).mappings().all()
    result = []
    for row in rows:
        shop = dict(row)
        schema = resolve_shop_schema_from_metadata(shop)
        if schema:
            result.append({
                "shop_id": shop["id"],
                "name": shop["name"],
                "schema": schema,
                "slug": shop["slug"],
                "data_isolation_mode": shop.get("data_isolation_mode") or "shared_public",
                "compute_mode": shop.get("compute_mode") or "shared_instance",
            })
    return result


def list_shop_runtimes(db: Session) -> list[dict]:
    """List every shop with data-isolation and compute-runtime metadata."""
    rows = db.execute(text(
        """
        SELECT
            s.id AS shop_id,
            s.name,
            s.slug,
            s.tenant_schema,
            s.data_isolation_mode,
            s.compute_mode,
            r.runtime_mode,
            r.instance_key,
            r.namespace,
            r.backend_service,
            r.worker_service,
            r.route_host,
            r.runtime_status,
            r.assigned_at
        FROM platform.shops s
        LEFT JOIN platform.shop_runtime_assignments r ON r.shop_id = s.id
        ORDER BY s.id
        """
    )).mappings().all()
    result = []
    for row in rows:
        shop = {
            "id": row["shop_id"],
            "tenant_schema": row["tenant_schema"],
            "data_isolation_mode": row["data_isolation_mode"],
        }
        result.append({
            "shop_id": row["shop_id"],
            "name": row["name"],
            "slug": row["slug"],
            "schema": resolve_shop_schema_from_metadata(shop),
            "data_isolation_mode": row["data_isolation_mode"] or "shared_public",
            "compute_mode": row["compute_mode"] or "shared_instance",
            "runtime": None if row["runtime_mode"] is None else {
                "runtime_mode": row["runtime_mode"],
                "instance_key": row["instance_key"],
                "namespace": row["namespace"],
                "backend_service": row["backend_service"],
                "worker_service": row["worker_service"],
                "route_host": row["route_host"],
                "runtime_status": row["runtime_status"],
                "assigned_at": row["assigned_at"].isoformat() if row["assigned_at"] else None,
            },
        })
    return result


def get_tenant_stats(db: Session, shop_id: int) -> dict:
    """Get row counts for all tenant tables (useful for monitoring)."""
    shop = _get_shop_metadata(db, shop_id)
    if not shop:
        raise ValueError(f"Shop {shop_id} not found")

    schema = resolve_shop_schema_from_metadata(shop) or "public"

    stats = {"shop_id": shop_id, "schema": schema, "tables": {}}
    for table in TENANT_TABLES:
        result = db.execute(text(f"SELECT COUNT(*) FROM {schema}.{table}"))
        stats["tables"][table] = result.scalar()
    return stats
