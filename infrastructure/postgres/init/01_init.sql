-- ==============================================
-- TELCO PRODUCT RECOMMENDER - SKEMA DATABASE
-- ==============================================
-- Skrip inisialisasi PostgreSQL 14+
-- Dibuat: Sprint 1 - Infrastruktur Database
-- Tujuan: Tabel inti untuk OLTP, feature store, dan pelacakan data streaming
-- ==============================================

-- Aktifkan ekstensi UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================
-- TABEL INTI
-- ==============================================

-- Tabel users (data master pelanggan)
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    msisdn_hash VARCHAR(64) UNIQUE NOT NULL,
    registration_date TIMESTAMP NOT NULL,
    segment_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_segment_id CHECK (segment_id >= 0 AND segment_id < 10)
);

COMMENT ON TABLE users IS 'Data master pelanggan dengan pelacakan segmen';
COMMENT ON COLUMN users.msisdn_hash IS 'Hash SHA-256 dari nomor telepon untuk privasi';
COMMENT ON COLUMN users.segment_id IS 'ID kluster K-Means (0-9)';

-- Tabel products (katalog paket telko)
CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    product_family VARCHAR(50),
    price DECIMAL(10,2) NOT NULL,
    quota_data_mb INTEGER DEFAULT 0,
    quota_voice_min INTEGER DEFAULT 0,
    quota_sms INTEGER DEFAULT 0,
    validity_days INTEGER DEFAULT 30,
    tags TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_price CHECK (price >= 0),
    CONSTRAINT check_quotas CHECK (
        quota_data_mb >= 0 AND
        quota_voice_min >= 0 AND
        quota_sms >= 0
    ),
    CONSTRAINT check_validity CHECK (validity_days > 0)
);

COMMENT ON TABLE products IS 'Katalog produk telko beserta kuota dan harga';
COMMENT ON COLUMN products.product_family IS 'Kategori produk: data, voice, combo, internet';
COMMENT ON COLUMN products.tags IS 'Array tag untuk filter: [premium, youth, family]';

-- Tabel transactions (riwayat pembelian)
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    product_id VARCHAR(50) NOT NULL REFERENCES products(product_id) ON DELETE RESTRICT,
    transaction_date TIMESTAMP NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_amount CHECK (amount >= 0),
    CONSTRAINT check_status CHECK (status IN ('pending', 'completed', 'failed', 'refunded'))
);

COMMENT ON TABLE transactions IS 'Riwayat pembelian untuk collaborative filtering';
COMMENT ON COLUMN transactions.status IS 'Status transaksi: pending, completed, failed, refunded';

-- Tabel events (interaksi pengguna di web)
CREATE TABLE IF NOT EXISTS events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    product_id VARCHAR(50) REFERENCES products(product_id) ON DELETE SET NULL,
    event_type VARCHAR(20) NOT NULL,
    ab_variant VARCHAR(20),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    session_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_event_type CHECK (event_type IN ('view', 'click', 'subscribe', 'impression', 'conversion'))
);

COMMENT ON TABLE events IS 'Event interaksi pengguna untuk pelacakan CTR/CVR';
COMMENT ON COLUMN events.event_type IS 'Jenis event: view, click, subscribe, impression, conversion';
COMMENT ON COLUMN events.ab_variant IS 'Varian A/B test: control, variant_a, variant_b';
COMMENT ON COLUMN events.metadata IS 'Konteks tambahan event (channel, lokasi, perangkat)';

-- ==============================================
-- FEATURE STORE
-- ==============================================

-- Tabel user_features (fitur yang sudah dihitung sebelumnya)
CREATE TABLE IF NOT EXISTS user_features (
    user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    recency INTEGER NOT NULL DEFAULT 0,
    frequency INTEGER NOT NULL DEFAULT 0,
    monetary DECIMAL(10,2) NOT NULL DEFAULT 0,
    arpu_bucket VARCHAR(20),
    usage_7d_mb INTEGER DEFAULT 0,
    usage_30d_mb INTEGER DEFAULT 0,
    churn_score DECIMAL(5,4) DEFAULT 0.0000,
    segment_id INTEGER,
    rfm_score VARCHAR(3),
    last_purchase_date TIMESTAMP,
    avg_transaction_value DECIMAL(10,2),
    product_diversity_score DECIMAL(3,2),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_recency CHECK (recency >= 0),
    CONSTRAINT check_frequency CHECK (frequency >= 0),
    CONSTRAINT check_monetary CHECK (monetary >= 0),
    CONSTRAINT check_arpu_bucket CHECK (arpu_bucket IN ('low', 'medium', 'high', 'premium')),
    CONSTRAINT check_churn_score CHECK (churn_score >= 0 AND churn_score <= 1),
    CONSTRAINT check_product_diversity CHECK (product_diversity_score >= 0 AND product_diversity_score <= 1)
);

COMMENT ON TABLE user_features IS 'Fitur pengguna yang sudah dihitung untuk inferensi real-time';
COMMENT ON COLUMN user_features.recency IS 'Jumlah hari sejak pembelian terakhir';
COMMENT ON COLUMN user_features.frequency IS 'Total jumlah pembelian';
COMMENT ON COLUMN user_features.monetary IS 'Total pendapatan dari pengguna';
COMMENT ON COLUMN user_features.arpu_bucket IS 'Segmen ARPU: low, medium, high, premium';
COMMENT ON COLUMN user_features.churn_score IS 'Probabilitas churn (0-1)';
COMMENT ON COLUMN user_features.rfm_score IS 'Skor RFM (contoh: 555, 111)';

-- ==============================================
-- PELACAKAN DATA STREAMING
-- ==============================================

-- Tabel ingestion_batches (pelacakan batch data streaming)
CREATE TABLE IF NOT EXISTS ingestion_batches (
    batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_start_time TIMESTAMP NOT NULL,
    batch_end_time TIMESTAMP,
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    error_message TEXT,
    source_file VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_records CHECK (records_processed >= 0 AND records_failed >= 0),
    CONSTRAINT check_status CHECK (status IN ('running', 'completed', 'failed', 'partial'))
);

COMMENT ON TABLE ingestion_batches IS 'Pelacakan batch ingesti data streaming';
COMMENT ON COLUMN ingestion_batches.status IS 'Status batch: running, completed, failed, partial';

-- ==============================================
-- INDEX UNTUK PERFORMA
-- ==============================================

-- Index tabel users
CREATE INDEX IF NOT EXISTS idx_users_segment ON users(segment_id) WHERE segment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_registration ON users(registration_date);

-- Index tabel products
CREATE INDEX IF NOT EXISTS idx_products_family ON products(product_family) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);
CREATE INDEX IF NOT EXISTS idx_products_tags ON products USING GIN(tags);

-- Index tabel transactions
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_product ON transactions(product_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);

-- Index tabel events
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_product ON events(product_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_variant ON events(ab_variant) WHERE ab_variant IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_user_product ON events(user_id, product_id, event_type);

-- Index tabel user_features
CREATE INDEX IF NOT EXISTS idx_user_features_segment ON user_features(segment_id) WHERE segment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_features_arpu ON user_features(arpu_bucket);
CREATE INDEX IF NOT EXISTS idx_user_features_updated ON user_features(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_features_rfm ON user_features(rfm_score) WHERE rfm_score IS NOT NULL;

-- Index tabel ingestion_batches
CREATE INDEX IF NOT EXISTS idx_ingestion_status ON ingestion_batches(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_start_time ON ingestion_batches(batch_start_time DESC);

-- ==============================================
-- TRIGGER UNTUK AUTO-UPDATE TIMESTAMP
-- ==============================================

-- Fungsi untuk memperbarui kolom updated_at secara otomatis
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Pasang trigger ke tabel yang memiliki kolom updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_features_updated_at
    BEFORE UPDATE ON user_features
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ingestion_batches_updated_at
    BEFORE UPDATE ON ingestion_batches
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==============================================
-- DATA AWAL (OPSIONAL)
-- ==============================================

-- Contoh produk untuk keperluan testing
INSERT INTO products (product_id, product_name, product_family, price, quota_data_mb, quota_voice_min, quota_sms, validity_days, tags) VALUES
    ('PKG001', 'Internet Freedom 10GB', 'data', 50000, 10240, 0, 0, 30, ARRAY['data-only', 'youth']),
    ('PKG002', 'Internet Freedom 25GB', 'data', 100000, 25600, 0, 0, 30, ARRAY['data-only', 'premium']),
    ('PKG003', 'Combo Hemat 5GB', 'combo', 45000, 5120, 100, 100, 30, ARRAY['combo', 'budget']),
    ('PKG004', 'Combo Super 15GB', 'combo', 85000, 15360, 300, 200, 30, ARRAY['combo', 'family']),
    ('PKG005', 'Voice Only 500 min', 'voice', 30000, 0, 500, 100, 30, ARRAY['voice-only', 'senior']),
    ('PKG006', 'Internet Unlimited', 'data', 150000, 51200, 0, 0, 30, ARRAY['unlimited', 'premium']),
    ('PKG007', 'Family Pack 30GB', 'combo', 120000, 30720, 500, 500, 30, ARRAY['family', 'combo']),
    ('PKG008', 'Starter Pack 2GB', 'data', 25000, 2048, 50, 50, 7, ARRAY['starter', 'trial'])
ON CONFLICT (product_id) DO NOTHING;

-- ==============================================
-- VIEW UNTUK QUERY UMUM
-- ==============================================

-- View: Ringkasan pengguna dengan fitur terbaru
CREATE OR REPLACE VIEW v_user_summary AS
SELECT
    u.user_id,
    u.msisdn_hash,
    u.registration_date,
    u.segment_id,
    uf.recency,
    uf.frequency,
    uf.monetary,
    uf.arpu_bucket,
    uf.churn_score,
    uf.rfm_score,
    uf.last_purchase_date,
    uf.updated_at AS features_updated_at
FROM users u
LEFT JOIN user_features uf ON u.user_id = uf.user_id;

COMMENT ON VIEW v_user_summary IS 'Profil pengguna lengkap dengan fitur terbaru';

-- View: Metrik performa produk
CREATE OR REPLACE VIEW v_product_metrics AS
SELECT
    p.product_id,
    p.product_name,
    p.product_family,
    p.price,
    COUNT(DISTINCT t.transaction_id) AS total_purchases,
    COUNT(DISTINCT t.user_id) AS unique_customers,
    SUM(t.amount) AS total_revenue,
    AVG(t.amount) AS avg_transaction_value,
    COUNT(e.event_id) FILTER (WHERE e.event_type = 'view') AS total_views,
    COUNT(e.event_id) FILTER (WHERE e.event_type = 'click') AS total_clicks,
    COUNT(e.event_id) FILTER (WHERE e.event_type = 'subscribe') AS total_subscribes
FROM products p
LEFT JOIN transactions t ON p.product_id = t.product_id AND t.status = 'completed'
LEFT JOIN events e ON p.product_id = e.product_id
WHERE p.is_active = TRUE
GROUP BY p.product_id, p.product_name, p.product_family, p.price;

COMMENT ON VIEW v_product_metrics IS 'KPI performa produk untuk monitoring';

-- ==============================================
-- HAK AKSES (UNTUK USER APLIKASI)
-- ==============================================

-- Catatan: Sesuaikan nama user dengan konfigurasi kamu
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO telco_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO telco_app_user;

-- ==============================================
-- PESAN SELESAI
-- ==============================================

DO $$
BEGIN
    RAISE NOTICE '✅ Skema database berhasil diinisialisasi';
    RAISE NOTICE 'Tabel dibuat: users, products, transactions, events, user_features, ingestion_batches';
    RAISE NOTICE 'Index dibuat untuk optimasi performa';
    RAISE NOTICE 'Trigger dikonfigurasi untuk pembaruan timestamp otomatis';
    RAISE NOTICE 'Contoh produk sudah dimasukkan untuk testing';
END $$;
