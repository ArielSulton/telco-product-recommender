-- ==============================================
-- DUKUNGAN MODEL RF V2 - MIGRASI DATABASE
-- ==============================================
-- migrasi PostgreSQL untuk model rekomendasi RandomForest v2
-- Dibuat: 2025-01-20
-- Tujuan: Menambahkan fitur perilaku untuk rekomendasi personal berbasis RF
-- Ketergantungan: 02_create_users_table.sql
-- ==============================================

-- ==============================================
-- FITUR PERILAKU UNTUK MODEL RF V2
-- ==============================================

-- Tambahkan kolom fitur perilaku ke tabel app_users
-- Fitur ini disimpulkan dari perilaku pembelian dan digunakan oleh model RF
ALTER TABLE app_users
  ADD COLUMN IF NOT EXISTS plan_type VARCHAR(20) DEFAULT 'Prepaid' CHECK (plan_type IN ('Prepaid', 'Postpaid')),
  ADD COLUMN IF NOT EXISTS device_brand VARCHAR(50) DEFAULT 'Samsung',
  ADD COLUMN IF NOT EXISTS avg_data_usage_gb FLOAT DEFAULT 5.0 CHECK (avg_data_usage_gb >= 0),
  ADD COLUMN IF NOT EXISTS pct_video_usage FLOAT DEFAULT 0.4 CHECK (pct_video_usage >= 0 AND pct_video_usage <= 1),
  ADD COLUMN IF NOT EXISTS avg_call_duration FLOAT DEFAULT 10.0 CHECK (avg_call_duration >= 0),
  ADD COLUMN IF NOT EXISTS sms_freq INTEGER DEFAULT 15 CHECK (sms_freq >= 0),
  ADD COLUMN IF NOT EXISTS monthly_spend INTEGER DEFAULT 0 CHECK (monthly_spend >= 0),
  ADD COLUMN IF NOT EXISTS topup_freq INTEGER DEFAULT 0 CHECK (topup_freq >= 0),
  ADD COLUMN IF NOT EXISTS travel_score FLOAT DEFAULT 0.3 CHECK (travel_score >= 0 AND travel_score <= 1),
  ADD COLUMN IF NOT EXISTS complaint_count INTEGER DEFAULT 0 CHECK (complaint_count >= 0),
  ADD COLUMN IF NOT EXISTS last_purchase_date TIMESTAMP,
  ADD COLUMN IF NOT EXISTS total_purchases INTEGER DEFAULT 0 CHECK (total_purchases >= 0);

-- Komentar kolom untuk dokumentasi
COMMENT ON COLUMN app_users.plan_type IS 'Jenis paket pengguna: Prepaid atau Postpaid (fitur kategorikal)';
COMMENT ON COLUMN app_users.device_brand IS 'Merek perangkat pengguna: Samsung, Apple, Xiaomi, dll. (fitur kategorikal)';
COMMENT ON COLUMN app_users.avg_data_usage_gb IS 'Rata-rata penggunaan data dalam GB/bulan (disimpulkan dari kuota yang dibeli)';
COMMENT ON COLUMN app_users.pct_video_usage IS 'Persentase data yang digunakan untuk streaming video (disimpulkan dari jenis produk)';
COMMENT ON COLUMN app_users.avg_call_duration IS 'Rata-rata durasi panggilan dalam menit (disimpulkan dari paket voice)';
COMMENT ON COLUMN app_users.sms_freq IS 'Frekuensi SMS per bulan (disimpulkan dari jenis produk)';
COMMENT ON COLUMN app_users.monthly_spend IS 'Total pengeluaran dalam 30 hari terakhir (dihitung dari pembelian)';
COMMENT ON COLUMN app_users.topup_freq IS 'Frekuensi top-up dalam 30 hari terakhir (dihitung dari pembelian)';
COMMENT ON COLUMN app_users.travel_score IS 'Skor kecenderungan bepergian 0-1 (disimpulkan dari paket roaming)';
COMMENT ON COLUMN app_users.complaint_count IS 'Total jumlah komplain (statis atau dari sistem support)';
COMMENT ON COLUMN app_users.last_purchase_date IS 'Waktu pembelian terakhir';
COMMENT ON COLUMN app_users.total_purchases IS 'Jumlah total pembelian sepanjang waktu';

-- ==============================================
-- TABEL PURCHASES UNTUK PELACAKAN RF V2
-- ==============================================

-- Buat tabel purchases (terpisah dari tabel transactions ML)
-- Tabel ini melacak pembelian dari frontend beserta product_family untuk inferensi fitur
CREATE TABLE IF NOT EXISTS purchases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    product_id VARCHAR(50) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    product_family VARCHAR(100),
    quota_data_mb INTEGER DEFAULT 0 CHECK (quota_data_mb >= 0),
    validity_days INTEGER DEFAULT 30 CHECK (validity_days > 0),
    price INTEGER NOT NULL CHECK (price >= 0),
    payment_method VARCHAR(50) DEFAULT 'pulsa' CHECK (payment_method IN ('pulsa', 'gopay', 'ovo', 'dana', 'credit_card')),
    status VARCHAR(50) DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
    purchase_date TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE purchases IS 'Riwayat pembelian untuk pelacakan fitur RF v2 dan inferensi perilaku';
COMMENT ON COLUMN purchases.product_family IS 'Kategori produk: Data Booster, Streaming Partner Pack, Voice Bundle, dll.';
COMMENT ON COLUMN purchases.quota_data_mb IS 'Kuota data dalam MB (digunakan untuk menyimpulkan avg_data_usage_gb)';
COMMENT ON COLUMN purchases.payment_method IS 'Metode pembayaran: pulsa, gopay, ovo, dana, credit_card';

-- ==============================================
-- INDEX UNTUK PERFORMA
-- ==============================================

-- Index untuk fitur perilaku app_users
CREATE INDEX IF NOT EXISTS idx_app_users_plan_device ON app_users(plan_type, device_brand);
CREATE INDEX IF NOT EXISTS idx_app_users_monthly_spend ON app_users(monthly_spend DESC);
CREATE INDEX IF NOT EXISTS idx_app_users_last_purchase ON app_users(last_purchase_date DESC);
CREATE INDEX IF NOT EXISTS idx_app_users_total_purchases ON app_users(total_purchases DESC);

-- Index untuk tabel purchases
CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_purchases_product_id ON purchases(product_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date DESC);
CREATE INDEX IF NOT EXISTS idx_purchases_user_date ON purchases(user_id, purchase_date DESC);
CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status);
CREATE INDEX IF NOT EXISTS idx_purchases_family ON purchases(product_family) WHERE product_family IS NOT NULL;

-- ==============================================
-- TRIGGER UNTUK AUTO-UPDATE TIMESTAMP
-- ==============================================

-- Catatan: Tabel purchases tidak memiliki kolom updated_at karena bersifat immutable (tidak bisa diubah)

-- ==============================================
-- VIEW UNTUK ANALITIK RF V2
-- ==============================================

-- View: Ringkasan fitur pengguna untuk model RF
CREATE OR REPLACE VIEW v_rf_user_features AS
SELECT
    u.id,
    u.phone,
    u.name,
    u.plan_type,
    u.device_brand,
    u.avg_data_usage_gb,
    u.pct_video_usage,
    u.avg_call_duration,
    u.sms_freq,
    u.monthly_spend,
    u.topup_freq,
    u.travel_score,
    u.complaint_count,
    u.last_purchase_date,
    u.total_purchases,
    u.balance,
    u.created_at,
    u.updated_at
FROM app_users u
WHERE u.total_purchases >= 1;  -- Hanya pengguna yang sudah pernah membeli

COMMENT ON VIEW v_rf_user_features IS 'Fitur perilaku pengguna untuk inferensi model RF v2';

-- View: Analitik pembelian berdasarkan product_family
CREATE OR REPLACE VIEW v_purchase_analytics AS
SELECT
    p.user_id,
    p.product_family,
    COUNT(*) as purchase_count,
    SUM(p.price) as total_spent,
    AVG(p.price) as avg_transaction_value,
    AVG(p.quota_data_mb) as avg_quota_mb,
    MAX(p.purchase_date) as last_purchase_date,
    MIN(p.purchase_date) as first_purchase_date,
    EXTRACT(EPOCH FROM (MAX(p.purchase_date) - MIN(p.purchase_date))) / 86400 as customer_lifetime_days
FROM purchases p
WHERE p.status = 'completed'
GROUP BY p.user_id, p.product_family;

COMMENT ON VIEW v_purchase_analytics IS 'Analitik pembelian per pengguna dan product_family untuk rekayasa fitur';

-- View: Pembelian terbaru dalam 30 hari untuk pembaruan fitur
CREATE OR REPLACE VIEW v_recent_purchases_30d AS
SELECT
    p.user_id,
    COUNT(*) as purchase_count_30d,
    SUM(p.price) as total_spent_30d,
    AVG(p.quota_data_mb) as avg_quota_30d,
    STRING_AGG(DISTINCT p.product_family, ', ' ORDER BY p.product_family) as product_families_30d
FROM purchases p
WHERE p.status = 'completed'
  AND p.purchase_date >= NOW() - INTERVAL '30 days'
GROUP BY p.user_id;

COMMENT ON VIEW v_recent_purchases_30d IS 'Statistik pembelian agregat 30 hari terakhir (digunakan untuk pembaruan fitur)';

-- ==============================================
-- BATASAN INTEGRITAS DATA
-- ==============================================

-- Tambahkan foreign key constraint untuk purchases.product_id (jika tabel products ada)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'products') THEN
        ALTER TABLE purchases
        ADD CONSTRAINT fk_purchases_product_id
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE RESTRICT;

        RAISE NOTICE '✅ Foreign key constraint ditambahkan: purchases.product_id → products.product_id';
    ELSE
        RAISE NOTICE '⚠️  Foreign key constraint dilewati: tabel products tidak ditemukan';
    END IF;
END $$;

-- ==============================================
-- DATA CONTOH UNTUK TESTING (OPSIONAL)
-- ==============================================

-- Masukkan contoh pengguna dengan fitur perilaku untuk testing inferensi model RF
INSERT INTO app_users (
    phone, password_hash, name, role, balance,
    plan_type, device_brand, avg_data_usage_gb, pct_video_usage,
    avg_call_duration, sms_freq, monthly_spend, topup_freq,
    travel_score, complaint_count, total_purchases
) VALUES (
    'test_rf_user',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYIYMEZJ0YW',  -- password: test123
    'RF Test User',
    'user',
    500000,
    'Prepaid',
    'Samsung',
    8.5,    -- Pengguna data tinggi
    0.65,   -- 65% penggunaan video
    12.0,   -- Durasi panggilan sedang
    18,     -- Frekuensi SMS
    150000, -- Pengeluaran bulanan
    3,      -- Frekuensi top-up
    0.4,    -- Skor perjalanan
    0,      -- Tidak ada komplain
    5       -- 5 pembelian
) ON CONFLICT (phone) DO NOTHING;

-- ==============================================
-- PESAN SELESAI
-- ==============================================

DO $$
BEGIN
    RAISE NOTICE '✅ Migrasi database RF v2 berhasil diselesaikan';
    RAISE NOTICE '   - Menambahkan 12 kolom fitur perilaku ke app_users';
    RAISE NOTICE '   - Membuat tabel purchases untuk pelacakan pembelian';
    RAISE NOTICE '   - Membuat 10 index performa';
    RAISE NOTICE '   - Membuat 3 view analitik untuk rekayasa fitur';
    RAISE NOTICE '   - Pengguna test dimasukkan (phone: test_rf_user, password: test123)';
    RAISE NOTICE '';
    RAISE NOTICE '📊 Fitur Model RF v2 (total 21):';
    RAISE NOTICE '   Dasar: plan_type, device_brand, avg_data_usage_gb, pct_video_usage,';
    RAISE NOTICE '          avg_call_duration, sms_freq, monthly_spend, topup_freq,';
    RAISE NOTICE '          travel_score, complaint_count (10 fitur)';
    RAISE NOTICE '   Rekayasa: recency, frequency, monetary, arpu, avg_spend_per_topup,';
    RAISE NOTICE '             data_intensity, communication_intensity, churn_score,';
    RAISE NOTICE '             freq_x_monetary, arpu_per_data, loyalty_score (11 fitur)';
    RAISE NOTICE '';
    RAISE NOTICE '🎯 Langkah Selanjutnya:';
    RAISE NOTICE '   1. Deploy Airflow DAG: rf_v2_retraining.py';
    RAISE NOTICE '   2. Jalankan pelatihan model awal';
    RAISE NOTICE '   3. Pantau alur pembelian → pembaruan fitur';
    RAISE NOTICE '   4. Validasi rekomendasi RF v2 via /api/v1/recommend/v2';
END $$;
