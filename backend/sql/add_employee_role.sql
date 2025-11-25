-- Add 'employee' role to the user_role enum
-- Run this in Supabase SQL Editor BEFORE creating shop_employees table

-- Check if 'employee' role already exists, if not add it
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_enum 
    WHERE enumlabel = 'employee' 
    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'user_role')
  ) THEN
    ALTER TYPE user_role ADD VALUE 'employee';
  END IF;
END $$;

-- Verify the enum now has all three values
SELECT enumlabel FROM pg_enum 
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'user_role')
ORDER BY enumlabel;
