-- Migration: Guarded AI Finance Query Agent
-- Date: 2026-05-02
--
-- This migration creates the read-only surface used by the dynamic finance SQL
-- agent. Views are tenant-scoped with app.current_shop_id so generated SQL
-- cannot cross shop boundaries even if it forgets to add a WHERE clause.

CREATE TABLE IF NOT EXISTS ai_query_logs (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    generated_sql TEXT NULL,
    validation_status VARCHAR NOT NULL DEFAULT 'not_run',
    execution_status VARCHAR NOT NULL DEFAULT 'not_run',
    error_class VARCHAR NULL,
    error_message TEXT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    mode VARCHAR NOT NULL DEFAULT 'enabled',
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_query_logs_shop_id ON ai_query_logs(shop_id);
CREATE INDEX IF NOT EXISTS idx_ai_query_logs_created_at ON ai_query_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_query_logs_status ON ai_query_logs(validation_status, execution_status);

CREATE OR REPLACE VIEW ai_daily_analytics AS
SELECT
    da.shop_id,
    da.date::date AS business_date,
    da.total_customers,
    da.completed_services,
    da.cancelled_services,
    da.total_revenue,
    da.avg_wait_time_minutes,
    da.avg_service_time_minutes,
    da.peak_hour_start,
    da.peak_hour_customers
FROM daily_analytics da
WHERE da.shop_id = NULLIF(current_setting('app.current_shop_id', true), '')::integer;

CREATE OR REPLACE VIEW ai_services AS
SELECT
    ss.shop_id,
    ss.id AS service_id,
    ss.name,
    ss.duration_minutes,
    ss.cost,
    ss.currency,
    ss.is_active,
    ss.created_at
FROM shop_services ss
WHERE ss.shop_id = NULLIF(current_setting('app.current_shop_id', true), '')::integer;

CREATE OR REPLACE VIEW ai_queue_visits AS
SELECT
    q.shop_id,
    qi.id AS visit_id,
    qi.queue_id,
    qi.service_id,
    ss.name AS service_name,
    qi.status::text AS status,
    qi.position,
    qi.checked_in_at,
    qi.service_started_at,
    qi.completed_at,
    qi.service_cost,
    qi.assigned_employee_id
FROM queue_items qi
JOIN queues q ON q.id = qi.queue_id
LEFT JOIN shop_services ss ON ss.id = qi.service_id AND ss.shop_id = q.shop_id
WHERE q.shop_id = NULLIF(current_setting('app.current_shop_id', true), '')::integer;

CREATE OR REPLACE VIEW ai_customers AS
SELECT
    sc.shop_id,
    sc.id AS customer_id,
    sc.name,
    sc.visit_count,
    sc.last_visit,
    sc.created_at
FROM shop_customers sc
WHERE sc.shop_id = NULLIF(current_setting('app.current_shop_id', true), '')::integer;

CREATE OR REPLACE VIEW ai_appointments AS
SELECT
    a.shop_id,
    a.id AS appointment_id,
    a.customer_id,
    a.service_id,
    ss.name AS service_name,
    a.employee_id,
    a.customer_name,
    a.scheduled_start,
    a.scheduled_end,
    a.actual_start,
    a.actual_end,
    a.status::text AS status,
    a.service_cost,
    a.cancelled_at,
    a.created_at
FROM appointments a
LEFT JOIN shop_services ss ON ss.id = a.service_id AND ss.shop_id = a.shop_id
WHERE a.shop_id = NULLIF(current_setting('app.current_shop_id', true), '')::integer;

CREATE OR REPLACE VIEW ai_invoices AS
SELECT
    i.shop_id,
    i.id AS invoice_id,
    i.customer_id,
    i.invoice_number,
    i.status::text AS status,
    i.subtotal,
    i.tax_amount,
    i.discount_amount,
    i.tip_amount,
    i.total,
    i.currency,
    i.due_date,
    i.paid_at,
    i.created_at,
    i.updated_at
FROM invoices i
WHERE i.shop_id = NULLIF(current_setting('app.current_shop_id', true), '')::integer;

CREATE OR REPLACE VIEW ai_invoice_line_items AS
SELECT
    i.shop_id,
    ili.id AS line_item_id,
    ili.invoice_id,
    ili.service_id,
    ili.queue_item_id,
    ili.appointment_id,
    ili.description,
    ili.quantity,
    ili.unit_price,
    ili.total,
    ili.created_at
FROM invoice_line_items ili
JOIN invoices i ON i.id = ili.invoice_id
WHERE i.shop_id = NULLIF(current_setting('app.current_shop_id', true), '')::integer;

CREATE OR REPLACE VIEW ai_payments AS
SELECT
    p.shop_id,
    p.id AS payment_id,
    p.invoice_id,
    p.customer_id,
    p.amount,
    p.tip_amount,
    p.currency,
    p.method::text AS method,
    p.status::text AS status,
    p.processed_by,
    p.processed_at,
    p.refunded_at,
    p.refund_amount,
    p.created_at,
    p.updated_at
FROM payments p
WHERE p.shop_id = NULLIF(current_setting('app.current_shop_id', true), '')::integer;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zeroqwait_ai_agent') THEN
        CREATE ROLE zeroqwait_ai_agent LOGIN;
    END IF;

    REVOKE ALL ON SCHEMA public FROM zeroqwait_ai_agent;
    GRANT USAGE ON SCHEMA public TO zeroqwait_ai_agent;
    GRANT SELECT ON
        ai_daily_analytics,
        ai_services,
        ai_queue_visits,
        ai_customers,
        ai_appointments,
        ai_invoices,
        ai_invoice_line_items,
        ai_payments
    TO zeroqwait_ai_agent;
    GRANT INSERT ON ai_query_logs TO zeroqwait_ai_agent;
    GRANT USAGE, SELECT ON SEQUENCE ai_query_logs_id_seq TO zeroqwait_ai_agent;
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE 'Skipping zeroqwait_ai_agent role setup because current DB user lacks role privileges.';
END $$;
