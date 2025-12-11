-- Migration: Create users table for authentication
-- Created: 2025-01-17
-- Purpose: Real database-based authentication to replace mock auth

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- App users table (authentication - separate from ML customer data)
CREATE TABLE IF NOT EXISTS app_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(15) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    balance INTEGER DEFAULT 100000,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for faster phone lookups
CREATE INDEX IF NOT EXISTS idx_app_users_phone ON app_users(phone);
CREATE INDEX IF NOT EXISTS idx_app_users_role ON app_users(role);

-- Seed data will be added via backend API using /auth/register endpoint
-- This ensures proper password hashing with bcrypt
--
-- To create admin account:
-- POST /api/v1/auth/register with {"phone": "admin", "password": "admin123", "name": "Admin User"}
-- Then manually update role to 'admin' in database:
-- UPDATE users SET role = 'admin' WHERE phone = 'admin';

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER update_app_users_updated_at
    BEFORE UPDATE ON app_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
