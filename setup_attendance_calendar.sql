-- SQL script to set up attendance calendar feature
-- Run this in your Supabase SQL Editor if the employee_shifts table doesn't exist

-- Create employee_shifts table for tracking work hours (if not exists)
CREATE TABLE IF NOT EXISTS employee_shifts (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  clock_in TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  clock_out TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  CONSTRAINT check_clock_out_after_clock_in CHECK (clock_out IS NULL OR clock_out > clock_in)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_employee_shifts_user_id ON employee_shifts(user_id);
CREATE INDEX IF NOT EXISTS idx_employee_shifts_shop_id ON employee_shifts(shop_id);
CREATE INDEX IF NOT EXISTS idx_employee_shifts_clock_in ON employee_shifts(clock_in);

-- Add comments for documentation
COMMENT ON TABLE employee_shifts IS 'Tracks employee clock in/out times for shifts';
COMMENT ON COLUMN employee_shifts.user_id IS 'Employee user ID';
COMMENT ON COLUMN employee_shifts.shop_id IS 'Shop where employee is working';
COMMENT ON COLUMN employee_shifts.clock_in IS 'Time employee clocked in';
COMMENT ON COLUMN employee_shifts.clock_out IS 'Time employee clocked out (NULL if still clocked in)';

-- Optional: Insert some sample data for testing (adjust user_id and shop_id to match your data)
-- Uncomment the lines below if you want to add test data

-- INSERT INTO employee_shifts (user_id, shop_id, clock_in, clock_out) VALUES
-- (2, 1, NOW() - INTERVAL '5 hours', NOW() - INTERVAL '30 minutes'),
-- (2, 1, NOW() - INTERVAL '1 day' - INTERVAL '6 hours', NOW() - INTERVAL '1 day'),
-- (3, 1, NOW() - INTERVAL '2 days' - INTERVAL '7 hours', NOW() - INTERVAL '2 days' - INTERVAL '30 minutes'),
-- (2, 1, NOW() - INTERVAL '3 days' - INTERVAL '5 hours', NOW() - INTERVAL '3 days');
