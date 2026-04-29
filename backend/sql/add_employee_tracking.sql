-- Add employee time tracking and profile photo support
-- Run this against the current PostgreSQL database

-- Add profile photo and time tracking columns to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS profile_photo_url TEXT,
ADD COLUMN IF NOT EXISTS clock_in_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS clock_out_time TIMESTAMP WITH TIME ZONE;

-- Create employee_shifts table for tracking work hours
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
