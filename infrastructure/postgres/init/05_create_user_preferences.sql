-- Migrasi: Buat tabel user_preferences
-- Tujuan: Menyimpan preferensi onboarding pengguna untuk personalisasi

-- Tabel preferensi pengguna
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id UUID PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
    preferences JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Trigger untuk auto-update kolom updated_at
CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE user_preferences IS 'Preferensi pengguna dari onboarding (budget, jenis penggunaan, dll.)';
