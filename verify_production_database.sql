-- Comprehensive Database Verification and Setup Script
-- Run this in your Supabase SQL Editor to ensure all tables exist

-- ============================================
-- 1. USERS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'customer',
    is_active BOOLEAN DEFAULT true,
    subscription_tier VARCHAR(50) DEFAULT 'free',
    profile_photo_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================
-- 2. SHOPS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS shops (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    shop_type VARCHAR(100),
    address VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    zip_code VARCHAR(20),
    country VARCHAR(100) DEFAULT 'United States',
    phone VARCHAR(50),
    email VARCHAR(255),
    website VARCHAR(255),
    average_service_time INTEGER DEFAULT 30,
    logo_url TEXT,
    primary_color VARCHAR(20) DEFAULT '#1976d2',
    secondary_color VARCHAR(20),
    accent_color VARCHAR(20),
    background_color VARCHAR(20),
    slug VARCHAR(255) UNIQUE,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shops_owner_id ON shops(owner_id);
CREATE INDEX IF NOT EXISTS idx_shops_slug ON shops(slug);

-- ============================================
-- 3. QUEUES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS queues (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    name VARCHAR(255) DEFAULT 'Main Queue',
    date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_queues_shop_id ON queues(shop_id);
CREATE INDEX IF NOT EXISTS idx_queues_is_active ON queues(is_active);

-- ============================================
-- 4. QUEUE ITEMS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS queue_items (
    id SERIAL PRIMARY KEY,
    queue_id INTEGER NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    customer_name VARCHAR(255) NOT NULL,
    customer_phone VARCHAR(50),
    customer_email VARCHAR(255),
    position INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'waiting',
    notes TEXT,
    checked_in_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    service_started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    assigned_employee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_queue_items_queue_id ON queue_items(queue_id);
CREATE INDEX IF NOT EXISTS idx_queue_items_status ON queue_items(status);

-- ============================================
-- 5. SHOP EMPLOYEES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS shop_employees (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(shop_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_shop_employees_shop_id ON shop_employees(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_employees_user_id ON shop_employees(user_id);

-- ============================================
-- 6. EMPLOYEE SHIFTS TABLE (for clock in/out)
-- ============================================
CREATE TABLE IF NOT EXISTS employee_shifts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    clock_in TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    clock_out TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT check_clock_out_after_clock_in CHECK (clock_out IS NULL OR clock_out > clock_in)
);

CREATE INDEX IF NOT EXISTS idx_employee_shifts_user_id ON employee_shifts(user_id);
CREATE INDEX IF NOT EXISTS idx_employee_shifts_shop_id ON employee_shifts(shop_id);
CREATE INDEX IF NOT EXISTS idx_employee_shifts_clock_in ON employee_shifts(clock_in);

-- ============================================
-- 7. PASSWORD RESET TOKENS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

-- Check if all tables exist
DO $$
BEGIN
    RAISE NOTICE '=== DATABASE VERIFICATION ===';
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users') THEN
        RAISE NOTICE '✓ users table exists';
    ELSE
        RAISE WARNING '✗ users table MISSING';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'shops') THEN
        RAISE NOTICE '✓ shops table exists';
    ELSE
        RAISE WARNING '✗ shops table MISSING';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'queues') THEN
        RAISE NOTICE '✓ queues table exists';
    ELSE
        RAISE WARNING '✗ queues table MISSING';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'queue_items') THEN
        RAISE NOTICE '✓ queue_items table exists';
    ELSE
        RAISE WARNING '✗ queue_items table MISSING';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'shop_employees') THEN
        RAISE NOTICE '✓ shop_employees table exists';
    ELSE
        RAISE WARNING '✗ shop_employees table MISSING';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'employee_shifts') THEN
        RAISE NOTICE '✓ employee_shifts table exists';
    ELSE
        RAISE WARNING '✗ employee_shifts table MISSING';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'password_reset_tokens') THEN
        RAISE NOTICE '✓ password_reset_tokens table exists';
    ELSE
        RAISE WARNING '✗ password_reset_tokens table MISSING';
    END IF;
    
    RAISE NOTICE '=== VERIFICATION COMPLETE ===';
END $$;

-- Show table counts
SELECT 'users' as table_name, COUNT(*) as count FROM users
UNION ALL
SELECT 'shops', COUNT(*) FROM shops
UNION ALL
SELECT 'queues', COUNT(*) FROM queues
UNION ALL
SELECT 'queue_items', COUNT(*) FROM queue_items
UNION ALL
SELECT 'shop_employees', COUNT(*) FROM shop_employees
UNION ALL
SELECT 'employee_shifts', COUNT(*) FROM employee_shifts
UNION ALL
SELECT 'password_reset_tokens', COUNT(*) FROM password_reset_tokens;
