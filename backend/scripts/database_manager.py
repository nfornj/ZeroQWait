"""
Multi-tenancy Database Manager

This module handles database connections for different subscription tiers:
- FREE tier: Shared database (default connection)
- PREMIUM tier: Dedicated database per shop owner

Database naming convention:
- Shared: main database (fastcuts)
- Dedicated: tenant_{user_id} (e.g., tenant_123)
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from typing import Optional, Dict
import os
from models import User, SubscriptionTier
from database import Base, DATABASE_URL

# Cache for tenant database engines
_tenant_engines: Dict[int, Engine] = {}
_tenant_session_locals: Dict[int, sessionmaker] = {}


def get_tenant_database_url(user_id: int) -> str:
    """
    Generate database URL for a tenant's dedicated database.
    
    Args:
        user_id: The user/tenant ID
        
    Returns:
        Database connection URL for the tenant
    """
    # Parse the base DATABASE_URL to get connection details
    # Format: postgresql://user:password@host:port/database
    base_url = DATABASE_URL.rsplit('/', 1)[0]  # Remove database name
    tenant_db_name = f"tenant_{user_id}"
    return f"{base_url}/{tenant_db_name}"


def create_tenant_database(user_id: int) -> bool:
    """
    Create a dedicated database for a premium/enterprise user.
    
    Args:
        user_id: The user ID to create database for
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Connect to default postgres database to create new database
        default_db_url = DATABASE_URL.rsplit('/', 1)[0] + '/postgres'
        engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")
        
        tenant_db_name = f"tenant_{user_id}"
        
        with engine.connect() as conn:
            # Check if database already exists
            result = conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname='{tenant_db_name}'")
            )
            if result.fetchone():
                print(f"Database {tenant_db_name} already exists")
                return True
            
            # Create the database
            conn.execute(text(f"CREATE DATABASE {tenant_db_name}"))
            print(f"Created database: {tenant_db_name}")
        
        # Create all tables in the new database
        tenant_url = get_tenant_database_url(user_id)
        tenant_engine = create_engine(tenant_url)
        Base.metadata.create_all(bind=tenant_engine)
        print(f"Created tables in {tenant_db_name}")
        
        return True
        
    except Exception as e:
        print(f"Error creating tenant database for user {user_id}: {e}")
        return False


def get_tenant_engine(user_id: int) -> Engine:
    """
    Get or create a database engine for a tenant.
    
    Args:
        user_id: The user ID
        
    Returns:
        SQLAlchemy engine for the tenant's database
    """
    if user_id not in _tenant_engines:
        tenant_url = get_tenant_database_url(user_id)
        _tenant_engines[user_id] = create_engine(
            tenant_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True
        )
    
    return _tenant_engines[user_id]


def get_tenant_session_local(user_id: int) -> sessionmaker:
    """
    Get or create a session maker for a tenant's database.
    
    Args:
        user_id: The user ID
        
    Returns:
        Session maker for the tenant's database
    """
    if user_id not in _tenant_session_locals:
        engine = get_tenant_engine(user_id)
        _tenant_session_locals[user_id] = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
    
    return _tenant_session_locals[user_id]


def get_database_for_user(user: User) -> Session:
    """
    Get the appropriate database session for a user based on their subscription tier.
    
    Args:
        user: The User object
        
    Returns:
        Database session (either shared or dedicated)
    """
    # Free tier users use shared database
    if user.subscription_tier == SubscriptionTier.FREE:
        from database import SessionLocal
        return SessionLocal()
    
    # Premium users get dedicated database
    else:
        # Ensure tenant database exists
        if user.id not in _tenant_engines:
            create_tenant_database(user.id)
        
        SessionLocal = get_tenant_session_local(user.id)
        return SessionLocal()


def migrate_user_to_dedicated_database(user: User, old_session: Session) -> bool:
    """
    Migrate a user's data from shared database to dedicated database.
    This is called when a user upgrades from FREE to PREMIUM.
    
    Args:
        user: The User object
        old_session: Session to the shared database
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from models import Shop, Queue, QueueItem
        
        # Create the tenant database
        if not create_tenant_database(user.id):
            return False
        
        # Get new session for tenant database
        new_session = get_database_for_user(user)
        
        # Migrate user data
        # 1. Copy user record
        new_user = User(
            id=user.id,
            email=user.email,
            username=user.username,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
            role=user.role,
            subscription_tier=user.subscription_tier,
            subscription_started_at=user.subscription_started_at,
            subscription_expires_at=user.subscription_expires_at,
            stripe_customer_id=user.stripe_customer_id
        )
        new_session.add(new_user)
        
        # 2. Copy shops
        shops = old_session.query(Shop).filter(Shop.owner_id == user.id).all()
        for shop in shops:
            new_shop = Shop(
                id=shop.id,
                name=shop.name,
                description=shop.description,
                shop_type=shop.shop_type,
                address=shop.address,
                city=shop.city,
                state=shop.state,
                zip_code=shop.zip_code,
                country=shop.country,
                phone=shop.phone,
                email=shop.email,
                website=shop.website,
                logo_url=shop.logo_url,
                logo_data=shop.logo_data,
                logo_mime_type=shop.logo_mime_type,
                primary_color=shop.primary_color,
                secondary_color=shop.secondary_color,
                accent_color=shop.accent_color,
                background_color=shop.background_color,
                slug=shop.slug,
                average_service_time=shop.average_service_time,
                is_active=shop.is_active,
                created_at=shop.created_at,
                owner_id=user.id
            )
            new_session.add(new_shop)
            
            # 3. Copy queues for this shop
            queues = old_session.query(Queue).filter(Queue.shop_id == shop.id).all()
            for queue in queues:
                new_queue = Queue(
                    id=queue.id,
                    shop_id=shop.id,
                    name=queue.name,
                    date=queue.date,
                    is_active=queue.is_active
                )
                new_session.add(new_queue)
                
                # 4. Copy queue items
                items = old_session.query(QueueItem).filter(QueueItem.queue_id == queue.id).all()
                for item in items:
                    new_item = QueueItem(
                        id=item.id,
                        queue_id=queue.id,
                        customer_name=item.customer_name,
                        customer_phone=item.customer_phone,
                        customer_email=item.customer_email,
                        user_id=item.user_id,
                        position=item.position,
                        status=item.status,
                        checked_in_at=item.checked_in_at,
                        service_started_at=item.service_started_at,
                        completed_at=item.completed_at,
                        notes=item.notes
                    )
                    new_session.add(new_item)
        
        new_session.commit()
        new_session.close()
        
        print(f"Successfully migrated user {user.id} to dedicated database")
        return True
        
    except Exception as e:
        print(f"Error migrating user {user.id}: {e}")
        if new_session:
            new_session.rollback()
            new_session.close()
        return False


def delete_tenant_database(user_id: int) -> bool:
    """
    Delete a tenant's dedicated database.
    This might be called when downgrading or account deletion.
    
    Args:
        user_id: The user ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Close all connections to this database
        if user_id in _tenant_engines:
            _tenant_engines[user_id].dispose()
            del _tenant_engines[user_id]
            del _tenant_session_locals[user_id]
        
        # Connect to postgres database to drop tenant database
        default_db_url = DATABASE_URL.rsplit('/', 1)[0] + '/postgres'
        engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")
        
        tenant_db_name = f"tenant_{user_id}"
        
        with engine.connect() as conn:
            # Terminate all connections to the database
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{tenant_db_name}'
                AND pid <> pg_backend_pid()
            """))
            
            # Drop the database
            conn.execute(text(f"DROP DATABASE IF EXISTS {tenant_db_name}"))
            print(f"Deleted database: {tenant_db_name}")
        
        return True
        
    except Exception as e:
        print(f"Error deleting tenant database for user {user_id}: {e}")
        return False
