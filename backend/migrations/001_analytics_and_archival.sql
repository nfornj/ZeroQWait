-- Migration: Analytics and Queue Archival System
-- Purpose: Create tables for daily analytics aggregation and historical queue archival

-- 1. Create queue_analytics_daily table
CREATE TABLE IF NOT EXISTS queue_analytics_daily (
    id BIGSERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_customers INTEGER DEFAULT 0,
    total_completed INTEGER DEFAULT 0,
    total_cancelled INTEGER DEFAULT 0,
    avg_wait_time_minutes FLOAT DEFAULT 0,
    avg_service_time_minutes FLOAT DEFAULT 0,
    peak_hour INTEGER, -- 0-23
    customers_by_hour JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(shop_id, date)
);

-- Index for fast queries
CREATE INDEX idx_analytics_shop_date ON queue_analytics_daily(shop_id, date DESC);
CREATE INDEX idx_analytics_date ON queue_analytics_daily(date DESC);

-- 2. Create queue_items_archive table (same structure as queue_items)
CREATE TABLE IF NOT EXISTS queue_items_archive (
    id BIGSERIAL PRIMARY KEY,
    queue_id INTEGER NOT NULL,
    shop_id INTEGER NOT NULL, -- Denormalized for faster queries
    user_id INTEGER,
    customer_name VARCHAR(255) NOT NULL,
    customer_phone VARCHAR(50),
    customer_email VARCHAR(255),
    position INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,
    notes TEXT,
    checked_in_at TIMESTAMP NOT NULL,
    service_started_at TIMESTAMP,
    completed_at TIMESTAMP,
    assigned_employee_id INTEGER,
    archived_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for archive queries
CREATE INDEX idx_archive_shop_date ON queue_items_archive(shop_id, completed_at DESC);
CREATE INDEX idx_archive_date ON queue_items_archive(completed_at DESC);
CREATE INDEX idx_archive_status ON queue_items_archive(status);

-- 3. Function to aggregate daily analytics
CREATE OR REPLACE FUNCTION aggregate_daily_analytics(target_date DATE DEFAULT CURRENT_DATE - INTERVAL '1 day')
RETURNS void AS $$
DECLARE
    shop_record RECORD;
    analytics_data RECORD;
    hour_data JSONB;
BEGIN
    -- Loop through each shop that had queue activity on target date
    FOR shop_record IN 
        SELECT DISTINCT q.shop_id 
        FROM queues q
        JOIN queue_items qi ON qi.queue_id = q.id
        WHERE DATE(qi.checked_in_at) = target_date
    LOOP
        -- Calculate analytics for this shop
        SELECT 
            COUNT(*) as total_customers,
            COUNT(CASE WHEN qi.status = 'completed' THEN 1 END) as total_completed,
            COUNT(CASE WHEN qi.status = 'cancelled' THEN 1 END) as total_cancelled,
            AVG(EXTRACT(EPOCH FROM (qi.service_started_at - qi.checked_in_at))/60) 
                FILTER (WHERE qi.service_started_at IS NOT NULL) as avg_wait_time,
            AVG(EXTRACT(EPOCH FROM (qi.completed_at - qi.service_started_at))/60)
                FILTER (WHERE qi.completed_at IS NOT NULL AND qi.service_started_at IS NOT NULL) as avg_service_time
        INTO analytics_data
        FROM queue_items qi
        JOIN queues q ON qi.queue_id = q.id
        WHERE q.shop_id = shop_record.shop_id
          AND DATE(qi.checked_in_at) = target_date;
        
        -- Calculate customers by hour
        SELECT jsonb_object_agg(hour, count)
        INTO hour_data
        FROM (
            SELECT 
                EXTRACT(HOUR FROM qi.checked_in_at)::TEXT as hour,
                COUNT(*)::INTEGER as count
            FROM queue_items qi
            JOIN queues q ON qi.queue_id = q.id
            WHERE q.shop_id = shop_record.shop_id
              AND DATE(qi.checked_in_at) = target_date
            GROUP BY EXTRACT(HOUR FROM qi.checked_in_at)
        ) hourly_counts;
        
        -- Find peak hour
        DECLARE peak_hr INTEGER;
        BEGIN
            SELECT CAST(key AS INTEGER)
            INTO peak_hr
            FROM jsonb_each_text(hour_data)
            ORDER BY CAST(value AS INTEGER) DESC
            LIMIT 1;
        END;
        
        -- Insert or update analytics
        INSERT INTO queue_analytics_daily (
            shop_id, date, total_customers, total_completed, total_cancelled,
            avg_wait_time_minutes, avg_service_time_minutes, peak_hour, customers_by_hour, updated_at
        ) VALUES (
            shop_record.shop_id, target_date, analytics_data.total_customers,
            analytics_data.total_completed, analytics_data.total_cancelled,
            COALESCE(analytics_data.avg_wait_time, 0),
            COALESCE(analytics_data.avg_service_time, 0),
            peak_hr, COALESCE(hour_data, '{}'::jsonb), NOW()
        )
        ON CONFLICT (shop_id, date) 
        DO UPDATE SET
            total_customers = EXCLUDED.total_customers,
            total_completed = EXCLUDED.total_completed,
            total_cancelled = EXCLUDED.total_cancelled,
            avg_wait_time_minutes = EXCLUDED.avg_wait_time_minutes,
            avg_service_time_minutes = EXCLUDED.avg_service_time_minutes,
            peak_hour = EXCLUDED.peak_hour,
            customers_by_hour = EXCLUDED.customers_by_hour,
            updated_at = NOW();
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- 4. Function to archive old queue items
CREATE OR REPLACE FUNCTION archive_old_queue_items(days_old INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    archived_count INTEGER;
BEGIN
    -- Copy old completed/cancelled items to archive
    INSERT INTO queue_items_archive (
        id, queue_id, shop_id, user_id, customer_name, customer_phone, customer_email,
        position, status, notes, checked_in_at, service_started_at, completed_at, assigned_employee_id
    )
    SELECT 
        qi.id, qi.queue_id, q.shop_id, qi.user_id, qi.customer_name, qi.customer_phone, 
        qi.customer_email, qi.position, qi.status, qi.notes, qi.checked_in_at, 
        qi.service_started_at, qi.completed_at, qi.assigned_employee_id
    FROM queue_items qi
    JOIN queues q ON qi.queue_id = q.id
    WHERE qi.status IN ('completed', 'cancelled')
      AND qi.completed_at < NOW() - INTERVAL '1 day' * days_old
      AND NOT EXISTS (
          SELECT 1 FROM queue_items_archive qia WHERE qia.id = qi.id
      );
    
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    
    -- Delete archived items from main table
    DELETE FROM queue_items
    WHERE id IN (
        SELECT id FROM queue_items_archive
        WHERE archived_at >= NOW() - INTERVAL '1 minute'
    );
    
    RETURN archived_count;
END;
$$ LANGUAGE plpgsql;

-- 5. Comments for documentation
COMMENT ON TABLE queue_analytics_daily IS 'Daily aggregated analytics for queue performance per shop';
COMMENT ON TABLE queue_items_archive IS 'Historical archive of completed/cancelled queue items older than 7 days';
COMMENT ON FUNCTION aggregate_daily_analytics IS 'Run daily to aggregate yesterday''s queue metrics';
COMMENT ON FUNCTION archive_old_queue_items IS 'Run daily to move old queue items to archive table';
