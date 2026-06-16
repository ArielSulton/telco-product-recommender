-- Migrasi: Buat tabel users untuk autentikasi
-- Dibuat: 2025-01-17
-- Tujuan: Autentikasi berbasis database nyata untuk menggantikan mock auth

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabel app_users (autentikasi - terpisah dari data pelanggan ML)
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

-- Index untuk pencarian nomor telepon yang lebih cepat
CREATE INDEX IF NOT EXISTS idx_app_users_phone ON app_users(phone);
CREATE INDEX IF NOT EXISTS idx_app_users_role ON app_users(role);

-- Data awal akan ditambahkan melalui API backend menggunakan endpoint /auth/register
-- Ini memastikan password di-hash dengan benar menggunakan bcrypt
--
-- Untuk membuat akun admin:
-- POST /api/v1/auth/register dengan {"phone": "admin", "password": "admin123", "name": "Admin User"}
-- Kemudian ubah role secara manual di database:
-- UPDATE users SET role = 'admin' WHERE phone = 'admin';

-- Fungsi untuk memperbarui kolom updated_at secara otomatis
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger untuk auto-update updated_at
CREATE TRIGGER update_app_users_updated_at
    BEFORE UPDATE ON app_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
