# Phase 2: Analytics System Deployment Guide

## Summary of Changes

### New Files Created
1. `backend/database.py` - SQLAlchemy database connection
2. `backend/analytics_processor.py` - Analytics aggregation and archival logic
3. `backend/scheduler.py` - Daily maintenance scheduler
4. `backend/apply_migration.py` - Migration application script
5. `backend/migrations/001_analytics_and_archival.sql` - Database migration
6. `ANALYTICS_SYSTEM_README.md` - Complete analytics system documentation

### Modified Files
1. `backend/main.py` - Added lifespan handler for scheduler startup/shutdown
2. `backend/routers/analytics.py` - Added 4 new endpoints for analytics
3. `backend/requirements.txt` - Added sqlalchemy and psycopg2-binary
4. `backend/pyproject.toml` - Added dependencies

### Database Changes
- New table: `queue_analytics_daily`
- New table: `queue_items_archive`
- New function: `aggregate_daily_analytics()`
- New function: `archive_old_queue_items()`

## Deployment Steps

### Step 1: Find Pi IP Address

Since the Pi is not reachable at 192.168.0.118, first find its current IP:

```bash
# Option 1: Check your router's DHCP client list

# Option 2: Scan network (if nmap installed)
nmap -sn 192.168.0.0/24 | grep -B 2 "Raspberry"

# Option 3: Try the hostname
ping raspberrypi.local
ssh pi@raspberrypi.local
```

### Step 2: Deploy Code to Pi

Once you have the correct IP/hostname:

```bash
cd /Users/neekrish/FastCuts

# Replace PI_HOST with actual IP or hostname
export PI_HOST=192.168.0.118  # or raspberrypi.local

rsync -avz \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude 'build' \
  --exclude '.pytest_cache' \
  ./ pi@$PI_HOST:/home/pi/Documents/projects/apps/zeroqwait/
```

### Step 3: SSH to Pi

```bash
ssh pi@$PI_HOST
cd /home/pi/Documents/projects/apps/zeroqwait
```

### Step 4: Update .env File

Add database connection details to `.env`:

```bash
# Edit .env file
nano backend/.env

# Add these lines (get password from Supabase dashboard):
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.yuxfpspyzyhesfuspjns.supabase.co:5432/postgres

# Or add individual components:
DB_HOST=db.yuxfpspyzyhesfuspjns.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=YOUR_PASSWORD_HERE

# Save and exit (Ctrl+X, Y, Enter)
```

### Step 5: Rebuild Docker Containers

```bash
# Stop existing containers
docker compose -f docker-compose.prod.simple.yml down

# Rebuild with new dependencies
docker compose -f docker-compose.prod.simple.yml build --no-cache backend

# Start containers
docker compose -f docker-compose.prod.simple.yml up -d

# Check logs
docker logs zeroqwait-backend-1
```

### Step 6: Run Database Migration

Option A: From within the running container:

```bash
# Enter container
docker exec -it zeroqwait-backend-1 bash

# Run migration script
cd /app
python apply_migration.py

# Exit container
exit
```

Option B: From Supabase Dashboard:

```bash
# 1. Copy migration SQL to clipboard
cat backend/migrations/001_analytics_and_archival.sql

# 2. Go to https://supabase.com/dashboard
# 3. Select your project
# 4. Go to SQL Editor
# 5. Paste the SQL and click "Run"
```

### Step 7: Verify Deployment

```bash
# Check if scheduler started
docker logs zeroqwait-backend-1 | grep -i scheduler
# Expected: "Scheduler started - will run daily at 00:30:00"

# Check if app is running
curl -I https://zeroqwait.com
# Expected: HTTP/1.1 200 OK

# Check backend health
curl https://zeroqwait.com/api/
# Expected: {"message":"Welcome to Universal Queue System API"}
```

### Step 8: Test New Endpoints

Get an auth token first (login via frontend or API), then test:

```bash
# Set your token
export TOKEN="your_jwt_token_here"

# Test new analytics endpoint
curl "https://zeroqwait.com/api/analytics/daily/1?start_date=2024-12-01&end_date=2024-12-07" \
  -H "Authorization: Bearer $TOKEN"

# Test peak hours
curl "https://zeroqwait.com/api/analytics/peak-hours/1?days=7" \
  -H "Authorization: Bearer $TOKEN"

# Test archive stats
curl "https://zeroqwait.com/api/analytics/archive/stats/1" \
  -H "Authorization: Bearer $TOKEN"

# Manually trigger maintenance (to test immediately)
curl -X POST "https://zeroqwait.com/api/analytics/maintenance/run" \
  -H "Authorization: Bearer $TOKEN"
```

### Step 9: Verify Database Tables

Connect to Supabase and verify:

```sql
-- Check tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('queue_analytics_daily', 'queue_items_archive');

-- Check functions exist
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public' 
AND routine_name IN ('aggregate_daily_analytics', 'archive_old_queue_items');

-- Check if analytics data is being generated (after running maintenance)
SELECT * FROM queue_analytics_daily ORDER BY date DESC LIMIT 5;

-- Check archive stats
SELECT COUNT(*) as active_count FROM queue_items;
SELECT COUNT(*) as archived_count FROM queue_items_archive;
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs zeroqwait-backend-1

# Common issues:
# 1. Missing DATABASE_URL in .env
# 2. Wrong password
# 3. Syntax errors in new Python files

# Fix and rebuild:
docker compose -f docker-compose.prod.simple.yml down
docker compose -f docker-compose.prod.simple.yml build --no-cache
docker compose -f docker-compose.prod.simple.yml up -d
```

### Migration Fails

```bash
# Check if tables already exist
# If so, drop them first (CAUTION: only if testing)
# Run in Supabase SQL Editor:
DROP TABLE IF EXISTS queue_analytics_daily CASCADE;
DROP TABLE IF EXISTS queue_items_archive CASCADE;
DROP FUNCTION IF EXISTS aggregate_daily_analytics(date);
DROP FUNCTION IF EXISTS archive_old_queue_items(integer);

# Then re-run migration
```

### Scheduler Not Running

```bash
# Check app logs
docker logs zeroqwait-backend-1 | tail -100

# Look for errors in lifespan startup
# Check if asyncio is working properly

# Restart container
docker restart zeroqwait-backend-1
```

### Can't Connect to Database

```bash
# Verify connection string
docker exec -it zeroqwait-backend-1 bash
cat /app/.env | grep -i db

# Test connection manually
python3 << EOF
from database import engine
with engine.connect() as conn:
    result = conn.execute("SELECT 1")
    print(result.fetchone())
EOF
```

## Monitoring After Deployment

### 1. Check Scheduler Runs Daily

```bash
# Each day at 00:30, check logs:
docker logs zeroqwait-backend-1 | grep "Daily maintenance"

# You should see entries like:
# "Starting daily maintenance tasks"
# "Daily maintenance completed: {'timestamp': ..., 'analytics_success': True, ...}"
```

### 2. Monitor Table Growth

```sql
-- Run this query weekly to monitor
SELECT 
    'queue_items' as table,
    COUNT(*) as count,
    pg_size_pretty(pg_total_relation_size('queue_items')) as size
FROM queue_items
UNION ALL
SELECT 
    'queue_items_archive',
    COUNT(*),
    pg_size_pretty(pg_total_relation_size('queue_items_archive'))
FROM queue_items_archive
UNION ALL
SELECT 
    'queue_analytics_daily',
    COUNT(*),
    pg_size_pretty(pg_total_relation_size('queue_analytics_daily'))
FROM queue_analytics_daily;
```

### 3. Check Analytics Coverage

```sql
-- Verify all shops have analytics
SELECT 
    s.id,
    s.name,
    COUNT(qad.id) as analytics_days,
    MIN(qad.date) as first_analytics,
    MAX(qad.date) as last_analytics
FROM shops s
LEFT JOIN queue_analytics_daily qad ON qad.shop_id = s.id
GROUP BY s.id, s.name
ORDER BY s.id;
```

## Rollback Plan (If Needed)

If something goes wrong and you need to rollback:

### 1. Revert Code

```bash
# On Pi
cd /home/pi/Documents/projects/apps/zeroqwait
git checkout HEAD~1  # Or specific commit before changes

# Rebuild
docker compose -f docker-compose.prod.simple.yml down
docker compose -f docker-compose.prod.simple.yml build --no-cache
docker compose -f docker-compose.prod.simple.yml up -d
```

### 2. Remove Database Changes (Optional)

```sql
-- Only if you need to clean up
DROP TABLE IF EXISTS queue_analytics_daily CASCADE;
DROP TABLE IF EXISTS queue_items_archive CASCADE;
DROP FUNCTION IF EXISTS aggregate_daily_analytics(date);
DROP FUNCTION IF EXISTS archive_old_queue_items(integer);
```

### 3. Restore queue_items (if archived data was deleted)

```sql
-- If you need to restore archived items
INSERT INTO queue_items (
    id, queue_id, user_id, customer_name, customer_phone, customer_email,
    position, status, notes, checked_in_at, service_started_at, 
    completed_at, assigned_employee_id
)
SELECT 
    id, queue_id, user_id, customer_name, customer_phone, customer_email,
    position, status, notes, checked_in_at, service_started_at, 
    completed_at, assigned_employee_id
FROM queue_items_archive
WHERE NOT EXISTS (SELECT 1 FROM queue_items qi WHERE qi.id = queue_items_archive.id);
```

## Next Steps (Phase 3)

After Phase 2 is successfully deployed and tested:

1. Monitor for 2-3 days to ensure scheduler works correctly
2. Verify archival happens automatically
3. Check analytics endpoints return correct data
4. Then proceed to Phase 3: User Duplicate Cleanup

See plan for Phase 3 details.
