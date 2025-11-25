# Multi-Tenancy Architecture

## Overview

Nowait implements a **hybrid multi-tenancy model** based on subscription tiers:

- **FREE Tier**: Shared database (cost-effective, multi-tenant)
- **PREMIUM Tier**: Dedicated database (data isolation, better performance)

## Database Architecture

### Shared Database (FREE Tier)
```
┌─────────────────────────────────┐
│     PostgreSQL: fastcuts        │
├─────────────────────────────────┤
│  users (all users)              │
│  shops (owner_id foreign key)   │
│  queues (shop_id foreign key)   │
│  queue_items                    │
└─────────────────────────────────┘
```

### Dedicated Databases (PREMIUM)
```
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ PostgreSQL:          │  │ PostgreSQL:          │  │ PostgreSQL:          │
│ tenant_1             │  │ tenant_2             │  │ tenant_3             │
├──────────────────────┤  ├──────────────────────┤  ├──────────────────────┤
│ users (user_id=1)    │  │ users (user_id=2)    │  │ users (user_id=3)    │
│ shops (owner_id=1)   │  │ shops (owner_id=2)   │  │ shops (owner_id=3)   │
│ queues               │  │ queues               │  │ queues               │
│ queue_items          │  │ queue_items          │  │ queue_items          │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

## Benefits by Tier

### FREE Tier (Shared Database)
✅ **Cost-effective** - One database for all users
✅ **Simple** - No complex infrastructure
✅ **Fast onboarding** - Instant account creation
✅ **Adequate for small businesses**

### PREMIUM Tier (Dedicated Database)
🔒 **Data Isolation** - Your data in separate database
📊 **Better Performance** - No noisy neighbors
🛡️ **Enhanced Security** - Physical data separation
💾 **Custom Backups** - Individual backup schedules
📈 **Compliance Ready** - Easier GDPR/HIPAA compliance


## Implementation

### Key Components

1. **`database_manager.py`** - Multi-tenancy logic
   - `get_database_for_user(user)` - Returns correct DB session
   - `create_tenant_database(user_id)` - Creates dedicated DB
   - `migrate_user_to_dedicated_database(user, session)` - Handles upgrades

2. **`models.py`** - Subscription tiers
   ```python
   class SubscriptionTier(enum.Enum):
       FREE = "free"
       PREMIUM = "premium"
   ```

3. **User Model** - Tracks subscription
   ```python
   class User(Base):
       subscription_tier = Column(Enum(SubscriptionTier))
       subscription_started_at = Column(DateTime)
       subscription_expires_at = Column(DateTime)
   ```

### Usage in API Routes

```python
from database_manager import get_database_for_user
from auth_utils import get_current_user

@router.get("/shops/my-shops")
def get_my_shops(current_user: User = Depends(get_current_user)):
    # Automatically routes to correct database
    db = get_database_for_user(current_user)
    shops = db.query(Shop).filter(Shop.owner_id == current_user.id).all()
    db.close()
    return shops
```

## Upgrade Flow

When a user upgrades from FREE to PREMIUM:

1. **User purchases** PREMIUM subscription
2. **System creates** dedicated database: `tenant_{user_id}`
3. **Migration runs** - Copies all data:
   - User record
   - Shops owned by user
   - All queues and queue items
   - Custom branding/settings
4. **Switch happens** - Future requests use new database
5. **Old data** - Can be archived/deleted from shared DB

### Migration Function

```python
def migrate_user_to_dedicated_database(user: User, old_session: Session) -> bool:
    # 1. Create tenant database
    create_tenant_database(user.id)
    
    # 2. Copy all user's data
    # - User record
    # - Shops
    # - Queues
    # - Queue items
    
    # 3. Commit to new database
    new_session.commit()
    
    return True
```

## Database Naming Convention

- **Shared**: `fastcuts` (default)
- **Tenant**: `tenant_{user_id}` (e.g., `tenant_42`, `tenant_123`)

## Security Considerations

1. **Row-Level Security** (Shared DB)
   - All queries filtered by `owner_id` or `shop_id`
   - API middleware validates ownership

2. **Physical Separation** (Dedicated DB)
   - Separate PostgreSQL databases
   - No shared tables
   - Complete isolation

3. **Access Control**
   - Connection pooling per tenant
   - Credentials managed per database
   - API keys validate tier access

## Performance Optimization

### Shared Database
- Indexed foreign keys (`owner_id`, `shop_id`)
- Connection pooling
- Query optimization

### Dedicated Database
- Smaller tables = faster queries
- Custom indexes per tenant
- Dedicated connection pool
- No table contention

## Backup Strategy

### Shared Database
- Daily full backup
- Hourly incremental
- Point-in-time recovery

### Dedicated Databases (PREMIUM)
- Daily backups (7-day retention)
- Custom backup schedules available
- Export-on-demand

## Monitoring

- **Shared DB**: Monitor total connections, query performance
- **Dedicated DBs**: Per-tenant metrics
  - Database size
  - Query performance
  - Connection count
  - Storage usage

## Cost Implications

| Tier | Database Cost | Est. Monthly Cost |
|------|---------------|-------------------|
| FREE | Shared | $0 (included) |
| PREMIUM | Dedicated DB | ~$5-10/tenant |

## Future Enhancements

- [ ] Automatic tenant DB scaling
- [ ] Self-service DB backups
- [ ] Tenant DB health dashboard
- [ ] Automated failover
- [ ] Enterprise tier with database clusters (future)

## Troubleshooting

### User can't access their data after upgrade
```python
# Check which DB they're using
from database_manager import get_database_for_user
db = get_database_for_user(user)
print(f"Using database: {db.bind.url}")
```

### Migration failed
```python
# Rollback to shared database temporarily
user.subscription_tier = SubscriptionTier.FREE
db.commit()

# Retry migration
migrate_user_to_dedicated_database(user, shared_db)
```

### Tenant DB not found
```python
# Recreate tenant database
from database_manager import create_tenant_database
create_tenant_database(user.id)
```

## Best Practices

1. ✅ Always use `get_database_for_user()` in API routes
2. ✅ Test migrations in staging first
3. ✅ Monitor tenant DB sizes
4. ✅ Set up alerts for failed migrations
5. ✅ Document tenant-specific configurations
6. ✅ Regular backup testing
7. ✅ Capacity planning for new tenants

## Support

For issues with multi-tenancy:
1. Check user's subscription tier
2. Verify tenant database exists
3. Check connection pool health
4. Review migration logs
5. Contact DevOps team
