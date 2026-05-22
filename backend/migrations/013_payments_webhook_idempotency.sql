ALTER TABLE payments
ADD COLUMN IF NOT EXISTS stripe_event_id VARCHAR;

CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_stripe_event_id
ON payments (stripe_event_id)
WHERE stripe_event_id IS NOT NULL;