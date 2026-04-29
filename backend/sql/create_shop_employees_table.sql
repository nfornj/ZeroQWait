-- Create shop_employees table for employee management
-- Run this against the current PostgreSQL database

CREATE TABLE IF NOT EXISTS shop_employees (
  id SERIAL PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_by INTEGER REFERENCES users(id),
  is_active BOOLEAN DEFAULT TRUE,
  UNIQUE(shop_id, user_id)
);

-- Create indexes for better query performance
CREATE INDEX idx_shop_employees_shop_id ON shop_employees(shop_id);
CREATE INDEX idx_shop_employees_user_id ON shop_employees(user_id);
CREATE INDEX idx_shop_employees_is_active ON shop_employees(is_active);

-- Add comment for documentation
COMMENT ON TABLE shop_employees IS 'Links employees to shops they work at';
COMMENT ON COLUMN shop_employees.shop_id IS 'Shop the employee works at';
COMMENT ON COLUMN shop_employees.user_id IS 'User with employee role';
COMMENT ON COLUMN shop_employees.created_by IS 'Shop owner who added this employee';
COMMENT ON COLUMN shop_employees.is_active IS 'Whether employee is currently active (soft delete)';
