-- Add employee assignment to queue items
-- Run this against the current PostgreSQL database

-- Add assigned_employee_id column to queue_items table
ALTER TABLE queue_items 
ADD COLUMN IF NOT EXISTS assigned_employee_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_queue_items_assigned_employee ON queue_items(assigned_employee_id);

-- Add comment for documentation
COMMENT ON COLUMN queue_items.assigned_employee_id IS 'ID of the employee assigned to serve this customer';
