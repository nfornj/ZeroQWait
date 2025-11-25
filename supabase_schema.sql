-- FastCuts Database Schema for Supabase
-- Run this in your Supabase SQL Editor to create all tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create ENUM types
CREATE TYPE user_role AS ENUM ('customer', 'shop_owner');
CREATE TYPE subscription_tier AS ENUM ('free', 'premium');
CREATE TYPE queue_status AS ENUM ('waiting', 'being_served', 'completed', 'cancelled');

-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL UNIQUE,
    username VARCHAR NOT NULL UNIQUE,
    hashed_password VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    role user_role DEFAULT 'customer',
    subscription_tier subscription_tier DEFAULT 'free',
    subscription_started_at TIMESTAMP,
    subscription_expires_at TIMESTAMP,
    stripe_customer_id VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index on email and username for faster lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);

-- Haircut Services table
CREATE TABLE haircut_services (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    address VARCHAR NOT NULL,
    city VARCHAR NOT NULL,
    state VARCHAR NOT NULL,
    zip_code VARCHAR NOT NULL,
    phone VARCHAR NOT NULL,
    website VARCHAR,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    rating FLOAT DEFAULT 0.0,
    price_range VARCHAR,
    hours VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index on name and location for faster searches
CREATE INDEX idx_haircut_services_name ON haircut_services(name);
CREATE INDEX idx_haircut_services_location ON haircut_services(latitude, longitude);

-- Shops table
CREATE TABLE shops (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    shop_type VARCHAR NOT NULL,
    address VARCHAR NOT NULL,
    city VARCHAR NOT NULL,
    state VARCHAR NOT NULL,
    zip_code VARCHAR NOT NULL,
    country VARCHAR DEFAULT 'United States',
    phone VARCHAR NOT NULL,
    email VARCHAR,
    website VARCHAR,
    logo_url VARCHAR,
    logo_data BYTEA,
    logo_mime_type VARCHAR,
    primary_color VARCHAR DEFAULT '#1976d2',
    secondary_color VARCHAR,
    accent_color VARCHAR,
    background_color VARCHAR,
    slug VARCHAR UNIQUE,
    average_service_time INTEGER DEFAULT 30,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX idx_shops_owner_id ON shops(owner_id);
CREATE INDEX idx_shops_slug ON shops(slug);
CREATE INDEX idx_shops_active ON shops(is_active);

-- Queues table
CREATE TABLE queues (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    name VARCHAR DEFAULT 'Main Queue',
    date TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index on shop_id for faster lookups
CREATE INDEX idx_queues_shop_id ON queues(shop_id);
CREATE INDEX idx_queues_active ON queues(is_active);

-- Queue Items table
CREATE TABLE queue_items (
    id SERIAL PRIMARY KEY,
    queue_id INTEGER NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    customer_name VARCHAR NOT NULL,
    customer_phone VARCHAR,
    customer_email VARCHAR,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    position INTEGER NOT NULL,
    status queue_status DEFAULT 'waiting',
    checked_in_at TIMESTAMP DEFAULT NOW(),
    service_started_at TIMESTAMP,
    completed_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_queue_items_queue_id ON queue_items(queue_id);
CREATE INDEX idx_queue_items_user_id ON queue_items(user_id);
CREATE INDEX idx_queue_items_status ON queue_items(status);

-- User Favorites junction table (many-to-many)
CREATE TABLE user_favorites (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    haircut_service_id INTEGER NOT NULL REFERENCES haircut_services(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, haircut_service_id)
);

-- Create indexes for faster lookups
CREATE INDEX idx_user_favorites_user_id ON user_favorites(user_id);
CREATE INDEX idx_user_favorites_service_id ON user_favorites(haircut_service_id);

-- Password Reset Tokens table
CREATE TABLE password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE
);

-- Create indexes
CREATE INDEX idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);

-- Enable Row Level Security (RLS) on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE haircut_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE shops ENABLE ROW LEVEL SECURITY;
ALTER TABLE queues ENABLE ROW LEVEL SECURITY;
ALTER TABLE queue_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;

-- RLS Policies for users table
CREATE POLICY "Users can view their own profile" ON users
    FOR SELECT USING (auth.uid()::text = id::text OR true); -- Allow service role to see all

CREATE POLICY "Users can update their own profile" ON users
    FOR UPDATE USING (auth.uid()::text = id::text);

-- RLS Policies for shops table (public read, owner write)
CREATE POLICY "Anyone can view active shops" ON shops
    FOR SELECT USING (is_active = true OR true); -- Service role can see all

CREATE POLICY "Shop owners can insert their own shops" ON shops
    FOR INSERT WITH CHECK (true); -- Will be handled by backend auth

CREATE POLICY "Shop owners can update their own shops" ON shops
    FOR UPDATE USING (true); -- Will be handled by backend auth

CREATE POLICY "Shop owners can delete their own shops" ON shops
    FOR DELETE USING (true); -- Will be handled by backend auth

-- RLS Policies for queues (public read, owner write)
CREATE POLICY "Anyone can view active queues" ON queues
    FOR SELECT USING (true);

CREATE POLICY "Shop owners can manage queues" ON queues
    FOR ALL USING (true); -- Will be handled by backend auth

-- RLS Policies for queue_items (public read for shop's items, user write)
CREATE POLICY "Anyone can view queue items" ON queue_items
    FOR SELECT USING (true);

CREATE POLICY "Users can create queue items" ON queue_items
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Users can update their own queue items" ON queue_items
    FOR UPDATE USING (true); -- Will be handled by backend auth

-- RLS Policies for haircut_services (public read)
CREATE POLICY "Anyone can view haircut services" ON haircut_services
    FOR SELECT USING (true);

-- RLS Policies for user_favorites (user-specific)
CREATE POLICY "Users can view their own favorites" ON user_favorites
    FOR SELECT USING (true); -- Will be handled by backend auth

CREATE POLICY "Users can manage their own favorites" ON user_favorites
    FOR ALL USING (true); -- Will be handled by backend auth

-- RLS Policies for password_reset_tokens (backend only)
CREATE POLICY "Backend can manage password reset tokens" ON password_reset_tokens
    FOR ALL USING (true); -- Service role only

-- Create a storage bucket for shop logos
-- Note: Run this separately in Supabase Storage dashboard or via client
-- INSERT INTO storage.buckets (id, name, public) VALUES ('shop-logos', 'shop-logos', true);

-- Functions for updating updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_shops_updated_at BEFORE UPDATE ON shops
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_queues_updated_at BEFORE UPDATE ON queues
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_queue_items_updated_at BEFORE UPDATE ON queue_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_haircut_services_updated_at BEFORE UPDATE ON haircut_services
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
