-- ==============================================
-- RF V2 MODEL SUPPORT - DATABASE MIGRATION
-- ==============================================
-- PostgreSQL migration script for RandomForest v2 recommendation model
-- Created: 2025-01-20
-- Purpose: Add behavioral features for RF-based personalized recommendations
-- Dependencies: 02_create_users_table.sql
-- ==============================================

-- ==============================================
-- BEHAVIORAL FEATURES FOR RF V2 MODEL
-- ==============================================

-- Add behavioral feature columns to app_users table
-- These features are inferred from purchase behavior and used by RF model
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

-- Column comments for documentation
COMMENT ON COLUMN app_users.plan_type IS 'User plan type: Prepaid or Postpaid (categorical feature)';
COMMENT ON COLUMN app_users.device_brand IS 'User device brand: Samsung, Apple, Xiaomi, etc. (categorical feature)';
COMMENT ON COLUMN app_users.avg_data_usage_gb IS 'Average data usage in GB/month (inferred from purchased quotas)';
COMMENT ON COLUMN app_users.pct_video_usage IS 'Percentage of data used for video streaming (inferred from product family)';
COMMENT ON COLUMN app_users.avg_call_duration IS 'Average call duration in minutes (inferred from voice packages)';
COMMENT ON COLUMN app_users.sms_freq IS 'SMS frequency per month (inferred from product type)';
COMMENT ON COLUMN app_users.monthly_spend IS 'Total spending in last 30 days (calculated from purchases)';
COMMENT ON COLUMN app_users.topup_freq IS 'Top-up frequency in last 30 days (calculated from purchases)';
COMMENT ON COLUMN app_users.travel_score IS 'Travel propensity score 0-1 (inferred from roaming packages)';
COMMENT ON COLUMN app_users.complaint_count IS 'Total complaint count (static or from support system)';
COMMENT ON COLUMN app_users.last_purchase_date IS 'Timestamp of most recent purchase';
COMMENT ON COLUMN app_users.total_purchases IS 'Lifetime purchase count';

-- ==============================================
-- PURCHASES TABLE FOR RF V2 TRACKING
-- ==============================================

-- Create purchases table (separate from ML transactions table)
-- This table tracks frontend purchases with product family for feature inference
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

COMMENT ON TABLE purchases IS 'Purchase history for RF v2 feature tracking and behavioral inference';
COMMENT ON COLUMN purchases.product_family IS 'Product category: Data Booster, Streaming Partner Pack, Voice Bundle, etc.';
COMMENT ON COLUMN purchases.quota_data_mb IS 'Data quota in MB (used to infer avg_data_usage_gb)';
COMMENT ON COLUMN purchases.payment_method IS 'Payment method: pulsa, gopay, ovo, dana, credit_card';

-- ==============================================
-- PERFORMANCE INDEXES
-- ==============================================

-- Indexes for app_users behavioral features
CREATE INDEX IF NOT EXISTS idx_app_users_plan_device ON app_users(plan_type, device_brand);
CREATE INDEX IF NOT EXISTS idx_app_users_monthly_spend ON app_users(monthly_spend DESC);
CREATE INDEX IF NOT EXISTS idx_app_users_last_purchase ON app_users(last_purchase_date DESC);
CREATE INDEX IF NOT EXISTS idx_app_users_total_purchases ON app_users(total_purchases DESC);

-- Indexes for purchases table
CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_purchases_product_id ON purchases(product_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date DESC);
CREATE INDEX IF NOT EXISTS idx_purchases_user_date ON purchases(user_id, purchase_date DESC);
CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status);
CREATE INDEX IF NOT EXISTS idx_purchases_family ON purchases(product_family) WHERE product_family IS NOT NULL;

-- ==============================================
-- TRIGGERS FOR AUTOMATIC TIMESTAMP UPDATES
-- ==============================================

-- Trigger to auto-update updated_at on purchases (if updated_at column exists)
-- Note: purchases table doesn't have updated_at by design (immutable records)

-- ==============================================
-- VIEWS FOR RF V2 ANALYTICS
-- ==============================================

-- View: User features summary for RF model
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
WHERE u.total_purchases >= 1;  -- Only users with purchase history

COMMENT ON VIEW v_rf_user_features IS 'User behavioral features for RF v2 model inference';

-- View: Purchase analytics with product family
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

COMMENT ON VIEW v_purchase_analytics IS 'Purchase analytics by user and product family for feature engineering';

-- View: Recent purchases for feature updates
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

COMMENT ON VIEW v_recent_purchases_30d IS 'Aggregated purchase stats for last 30 days (used in feature updates)';

-- ==============================================
-- DATA INTEGRITY CONSTRAINTS
-- ==============================================

-- Add foreign key constraint for purchases.product_id (if products table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'products') THEN
        ALTER TABLE purchases
        ADD CONSTRAINT fk_purchases_product_id
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE RESTRICT;

        RAISE NOTICE '✅ Added foreign key constraint: purchases.product_id → products.product_id';
    ELSE
        RAISE NOTICE '⚠️  Skipped foreign key constraint: products table not found';
    END IF;
END $$;

-- ==============================================
-- SAMPLE DATA FOR TESTING (OPTIONAL)
-- ==============================================

-- Insert sample user with behavioral features for testing
-- This is useful for development and testing RF model inference
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
    8.5,    -- High data user
    0.65,   -- 65% video usage
    12.0,   -- Moderate call duration
    18,     -- SMS frequency
    150000, -- Monthly spend
    3,      -- Top-up frequency
    0.4,    -- Travel score
    0,      -- No complaints
    5       -- 5 purchases
) ON CONFLICT (phone) DO NOTHING;

-- ==============================================
-- COMPLETION MESSAGE
-- ==============================================

DO $$
BEGIN
    RAISE NOTICE '✅ RF v2 database migration completed successfully';
    RAISE NOTICE '   - Added 12 behavioral feature columns to app_users';
    RAISE NOTICE '   - Created purchases table for purchase tracking';
    RAISE NOTICE '   - Created 10 performance indexes';
    RAISE NOTICE '   - Created 3 analytics views for feature engineering';
    RAISE NOTICE '   - Sample test user inserted (phone: test_rf_user, password: test123)';
    RAISE NOTICE '';
    RAISE NOTICE '📊 RF v2 Model Features (21 total):';
    RAISE NOTICE '   Base: plan_type, device_brand, avg_data_usage_gb, pct_video_usage,';
    RAISE NOTICE '         avg_call_duration, sms_freq, monthly_spend, topup_freq,';
    RAISE NOTICE '         travel_score, complaint_count (10 features)';
    RAISE NOTICE '   Engineered: recency, frequency, monetary, arpu, avg_spend_per_topup,';
    RAISE NOTICE '               data_intensity, communication_intensity, churn_score,';
    RAISE NOTICE '               freq_x_monetary, arpu_per_data, loyalty_score (11 features)';
    RAISE NOTICE '';
    RAISE NOTICE '🎯 Next Steps:';
    RAISE NOTICE '   1. Deploy Airflow DAG: rf_v2_retraining.py';
    RAISE NOTICE '   2. Run initial model training';
    RAISE NOTICE '   3. Monitor purchase → feature update flow';
    RAISE NOTICE '   4. Validate RF v2 recommendations via /api/v1/recommend/v2';
END $$;
