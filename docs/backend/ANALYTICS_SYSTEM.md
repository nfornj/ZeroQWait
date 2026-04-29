# Analytics and Archival System

## Overview
This document describes the analytics and queue archival system implemented to address database design issues with queue data management.

## Problem Statement
The original design had three key issues:
1. **Queue table growth**: The `queue_items` table would grow indefinitely, causing performance issues
2. **No analytics aggregation**: Every analytics query had to scan and aggregate raw queue data
3. **No historical data management**: No system to archive old queue items

## Solution

### New Tables

#### 1. `queue_analytics_daily`
Stores pre-aggregated daily analytics per shop.

**Columns:**
- `id` - Primary key
- `shop_id` - Foreign key to shops table
- `date` - Date of the analytics (unique per shop)
- `total_customers` - Total number of customers that day
- `total_completed` - Number of completed queue items
- `total_cancelled` - Number of cancelled queue items
- `avg_wait_time_minutes` - Average wait time from check-in to service start
- `avg_service_time_minutes` - Average service time from start to completion
- `peak_hour` - Busiest hour (0-23)
- `customers_by_hour` - JSONB object with hourly breakdown
- `created_at` - Record creation timestamp
- `updated_at` - Last update timestamp

**Benefits:**
- Fast analytics queries (no need to scan raw queue_items)
- Historical analytics preserved even after archival
- Pre-calculated metrics reduce computation

#### 2. `queue_items_archive`
Stores archived queue items older than 7 days.

**Structure:** Same as `queue_items` table, plus:
- `shop_id` - Denormalized for faster queries without joins
- `archived_at` - Timestamp when archived

**Benefits:**
- Keeps `queue_items` table small and fast
- Preserves historical data for long-term analysis
- Separate table means no impact on active queue queries

### Automated Processes

#### Daily Aggregation Function
**Function:** `aggregate_daily_analytics(target_date)`
- Runs daily at 00:30 (configurable)
- Aggregates previous day's queue data
- Calculates all metrics and stores in `queue_analytics_daily`
- Idempotent (can be run multiple times safely)

#### Archival Function
**Function:** `archive_old_queue_items(days_old)`
- Runs daily at 00:30 (after aggregation)
- Archives completed/cancelled items older than 7 days
- Copies to `queue_items_archive`
- Deletes from `queue_items`
- Returns count of archived items

### Components

#### 1. `analytics_processor.py`
Core analytics processing logic:
- `AnalyticsProcessor` class for running maintenance tasks
- `get_analytics_summary()` - Get aggregated stats for date range
- `get_peak_hours_analysis()` - Analyze busiest hours
- `run_daily_maintenance()` - Execute all daily tasks

#### 2. `scheduler.py`
Background task scheduler:
- `DailyScheduler` class for scheduling tasks
- Runs at 00:30 daily by default
- `start_scheduler()` - Start on app startup
- `stop_scheduler()` - Stop on app shutdown
- `trigger_maintenance_now()` - Manual trigger for testing

#### 3. `migrations/001_analytics_and_archival.sql`
Database migration script:
- Creates both new tables
- Creates PostgreSQL functions
- Creates indexes for performance
- Includes documentation comments

### API Endpoints

#### New Analytics Endpoints

1. **GET /api/analytics/daily/{shop_id}**
   - Fast analytics from pre-aggregated data
   - Query params: `start_date`, `end_date`
   - Returns summary with total customers, wait times, service times

2. **GET /api/analytics/peak-hours/{shop_id}**
   - Peak hours analysis
   - Query param: `days` (default: 7)
   - Returns hourly distribution and busiest hour

3. **POST /api/analytics/maintenance/run**
   - Manually trigger aggregation and archival
   - Useful for testing or manual runs
   - Requires authentication

4. **GET /api/analytics/archive/stats/{shop_id}**
   - Statistics about archived vs active items
   - Shows counts and oldest archived date
   - Helps monitor archival system health

5. **GET /api/analytics/{shop_id}** (existing)
   - Legacy endpoint, still works
   - Calculates from raw data
   - Use new `/daily/` endpoint for better performance

## Deployment And Operations

### 1. Run The Migration

Apply the analytics migration against the active PostgreSQL database:

```bash
psql "$DATABASE_URL" -f backend/migrations/001_analytics_and_archival.sql
```

If you are running through the repo-managed local stack, ensure the backend database settings in `backend/.env` match the active PostgreSQL container or deployment target.

### 2. Backend Environment

The active backend uses the current PostgreSQL configuration model, for example:

```env
DB_HOST=db
DB_PORT=5432
DB_NAME=zeroqwait
DB_USER=postgres
DB_PASSWORD=zeroqwait_dev
```

Do not follow older database setup instructions that predate the current PostgreSQL workflow for this feature.

### 3. Dependencies

Use the backend dependency set already declared in `pyproject.toml` and `uv.lock`:

```bash
cd backend
uv sync --dev
```

### 4. Deploy Or Run

For local source-run validation:

```bash
docker compose up -d db redis
cd backend
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

For the full non-prod deployment flow:

```bash
bash deployment/scripts/deploy-test.sh
```

For production deployment, use the active K3s deployment path documented in `deployment/docs/README.md`.

### 5. Verify Scheduler

Check logs to confirm scheduler started:

```bash
docker logs zeroqwait-backend-1 | grep -i scheduler
# Should see: "Scheduler started - will run daily at 00:30:00"
```

### 6. Test The System

```bash
# Option 1: Wait for scheduled run (00:30)

# Option 2: Manually trigger maintenance
curl -X POST http://localhost:8000/api/analytics/maintenance/run \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check analytics
curl "http://localhost:8000/api/analytics/daily/1?start_date=2024-01-01" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check archive stats
curl http://localhost:8000/api/analytics/archive/stats/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Testing Scenarios

### Scenario 1: Fresh Installation
1. Run migration
2. Add some queue items with completed status
3. Manually trigger maintenance: `POST /api/analytics/maintenance/run`
4. Query analytics: `GET /api/analytics/daily/{shop_id}`
5. Verify data in `queue_analytics_daily` table

### Scenario 2: Archival Testing
1. Create queue items with `completed_at` > 7 days old
2. Trigger maintenance
3. Check archive stats: `GET /api/analytics/archive/stats/{shop_id}`
4. Verify items moved to `queue_items_archive`
5. Verify items removed from `queue_items`

### Scenario 3: Peak Hours Analysis
1. Create queue items at various hours
2. Trigger maintenance to aggregate
3. Query peak hours: `GET /api/analytics/peak-hours/{shop_id}?days=7`
4. Verify hourly distribution is correct

### Scenario 4: Multiple Shops
1. Create queue items for multiple shops
2. Trigger maintenance
3. Verify each shop has separate analytics records
4. Verify shop isolation (shop owners can't see other shops' data)

## Monitoring

### Health Checks

1. **Scheduler Status**
   ```bash
   docker logs zeroqwait-backend-1 | grep "Daily maintenance completed"
   ```

2. **Database Table Sizes**
   ```sql
   SELECT 
       schemaname,
       tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables
   WHERE tablename IN ('queue_items', 'queue_items_archive', 'queue_analytics_daily')
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
   ```

3. **Analytics Coverage**
   ```sql
   SELECT shop_id, MIN(date) as oldest, MAX(date) as newest, COUNT(*) as days
   FROM queue_analytics_daily
   GROUP BY shop_id;
   ```

4. **Archive Progress**
   ```sql
   SELECT 
       COUNT(CASE WHEN qi.id IS NOT NULL THEN 1 END) as active_items,
       COUNT(CASE WHEN qia.id IS NOT NULL THEN 1 END) as archived_items
   FROM shops s
   LEFT JOIN queues q ON q.shop_id = s.id
   LEFT JOIN queue_items qi ON qi.queue_id = q.id
   LEFT JOIN queue_items_archive qia ON qia.shop_id = s.id;
   ```

## Troubleshooting

### Scheduler Not Running
- Check Docker logs: `docker logs zeroqwait-backend-1`
- Verify application startup: Look for "Scheduler started" message
- Check for errors in lifespan function

### Aggregation Not Working
- Verify PostgreSQL function exists: `\df aggregate_daily_analytics`
- Test function manually: `SELECT aggregate_daily_analytics('2024-01-01');`
- Check database permissions
- Verify queue_items have completed_at timestamps

### Archival Not Working
- Test function manually: `SELECT archive_old_queue_items(7);`
- Check for foreign key constraints
- Verify items are actually > 7 days old
- Check completed_at vs archived_at timestamps

### Performance Issues
- Check index usage: `EXPLAIN ANALYZE SELECT * FROM queue_analytics_daily WHERE shop_id = 1;`
- Monitor table sizes
- Consider adjusting archival threshold (7 days)
- Review scheduler run frequency

## Future Enhancements

1. **Configurable Archival Window**: Allow shops to configure retention period
2. **Real-time Analytics**: WebSocket updates for live dashboard
3. **Advanced Metrics**: Customer retention, repeat visits, service type analysis
4. **Export Features**: CSV/PDF export of analytics
5. **Predictive Analytics**: ML-based wait time predictions
6. **Multi-timezone Support**: Handle shops in different timezones
7. **Aggregate Archive Queries**: Query archived data efficiently

## Performance Impact

**Before:**
- Analytics queries scanned entire queue_items table
- Response times increased with data size
- No automatic cleanup

**After:**
- Analytics queries use pre-aggregated data (O(1) lookups)
- queue_items table stays small (< 7 days of data)
- Automatic nightly maintenance
- 10-100x faster analytics queries (depending on data size)
