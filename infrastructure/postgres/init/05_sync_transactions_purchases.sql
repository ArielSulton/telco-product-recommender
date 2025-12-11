-- ==============================================
-- TRANSACTIONS <-> PURCHASES SYNCHRONIZATION
-- ==============================================
-- PostgreSQL sync script for dual-table purchase tracking
-- Created: 2025-01-20
-- Purpose: Maintain data consistency between ML pipeline (transactions)
--          and frontend system (purchases) tables
-- Dependencies: 01_init.sql, 03_add_rf_v2_features.sql
-- ==============================================

-- ==============================================
-- BACKGROUND
-- ==============================================
-- The system uses TWO purchase tracking tables:
--
-- 1. `transactions` table (from 01_init.sql)
--    - Used by ML pipeline (hybrid model: K-Means, LightFM, XGBoost)
--    - Schema: user_id (references users.user_id), product_id, amount, status
--    - Purpose: Collaborative filtering, segmentation, baseline recommendations
--
-- 2. `purchases` table (from backend purchases.py + 03_add_rf_v2_features.sql)
--    - Used by frontend and RF v2 model
--    - Schema: user_id (references app_users.id), product_name, product_family, quota_data_mb
--    - Purpose: Real-time feature tracking, behavioral inference, RF recommendations
--
-- This dual-table design exists because:
-- - ML pipeline uses `users` table (SHA-256 hashed msisdn)
-- - Frontend uses `app_users` table (authentication with phone, password, balance)
-- - Different schemas serve different purposes (amount vs quotas, product_id vs product_family)
--
-- ==============================================

-- ==============================================
-- SYNC STRATEGY: TRIGGER-BASED REPLICATION
-- ==============================================

-- Create sync function: purchases → transactions
-- When a purchase is inserted into `purchases`, replicate to `transactions` for ML pipeline
CREATE OR REPLACE FUNCTION sync_purchase_to_transaction()
RETURNS TRIGGER AS $$
DECLARE
    ml_user_id UUID;
BEGIN
    -- Map app_users.id to users.user_id using phone number
    -- This assumes users table has msisdn_hash and app_users has phone
    -- For MVP, we'll create a mapping table or use direct UUID mapping

    -- Option 1: Direct UUID mapping (if app_users.id == users.user_id)
    ml_user_id := NEW.user_id;

    -- Option 2: Lookup via phone (requires phone column in users table)
    -- SELECT user_id INTO ml_user_id FROM users WHERE phone = (
    --     SELECT phone FROM app_users WHERE id = NEW.user_id
    -- );

    -- Insert into transactions table for ML pipeline
    INSERT INTO transactions (
        user_id,
        product_id,
        transaction_date,
        amount,
        status
    ) VALUES (
        ml_user_id,
        NEW.product_id,
        NEW.purchase_date,
        NEW.price,
        NEW.status
    )
    ON CONFLICT DO NOTHING;  -- Avoid duplicates

    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        -- Log error but don't fail the purchase
        RAISE WARNING 'Failed to sync purchase to transactions: %', SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sync_purchase_to_transaction IS 'Sync purchases table to transactions table for ML pipeline';

-- Create trigger on purchases table
DROP TRIGGER IF EXISTS trigger_sync_purchase_to_transaction ON purchases;
CREATE TRIGGER trigger_sync_purchase_to_transaction
    AFTER INSERT ON purchases
    FOR EACH ROW
    EXECUTE FUNCTION sync_purchase_to_transaction();

COMMENT ON TRIGGER trigger_sync_purchase_to_transaction ON purchases IS 'Auto-sync purchases to transactions for ML pipeline';

-- ==============================================
-- RECONCILIATION VIEWS
-- ==============================================

-- View: Unified purchase history (combines both tables)
CREATE OR REPLACE VIEW v_unified_purchase_history AS
SELECT
    'purchase' AS source,
    p.id AS transaction_id,
    p.user_id,
    p.product_id,
    p.product_name,
    p.product_family,
    p.quota_data_mb,
    p.validity_days,
    p.price AS amount,
    p.payment_method,
    p.status,
    p.purchase_date AS transaction_date,
    p.created_at
FROM purchases p
WHERE p.status = 'completed'

UNION ALL

SELECT
    'transaction' AS source,
    t.transaction_id,
    t.user_id,
    t.product_id,
    pr.product_name,
    pr.product_family,
    pr.quota_data_mb,
    pr.validity_days,
    t.amount,
    'unknown' AS payment_method,
    t.status,
    t.transaction_date,
    t.created_at
FROM transactions t
LEFT JOIN products pr ON t.product_id = pr.product_id
WHERE t.status = 'completed'
  AND NOT EXISTS (
      -- Exclude transactions that have corresponding purchases (avoid duplicates)
      SELECT 1 FROM purchases p
      WHERE p.user_id = t.user_id
        AND p.product_id = t.product_id
        AND p.purchase_date = t.transaction_date
  );

COMMENT ON VIEW v_unified_purchase_history IS 'Unified view of all purchases from both tables (deduped)';

-- View: Purchase discrepancy report (for monitoring)
CREATE OR REPLACE VIEW v_purchase_discrepancy_report AS
SELECT
    'in_purchases_not_transactions' AS discrepancy_type,
    COUNT(*) AS count
FROM purchases p
LEFT JOIN transactions t ON p.user_id = t.user_id
    AND p.product_id = t.product_id
    AND p.purchase_date = t.transaction_date
WHERE t.transaction_id IS NULL
  AND p.status = 'completed'
  AND p.purchase_date >= NOW() - INTERVAL '7 days'

UNION ALL

SELECT
    'in_transactions_not_purchases' AS discrepancy_type,
    COUNT(*) AS count
FROM transactions t
LEFT JOIN purchases p ON t.user_id = p.user_id
    AND t.product_id = p.product_id
    AND t.transaction_date = p.purchase_date
WHERE p.id IS NULL
  AND t.status = 'completed'
  AND t.transaction_date >= NOW() - INTERVAL '7 days';

COMMENT ON VIEW v_purchase_discrepancy_report IS 'Monitor sync issues between purchases and transactions tables';

-- ==============================================
-- DATA RECONCILIATION FUNCTION
-- ==============================================

-- Function to manually reconcile missing transactions
-- Run this periodically via cron or Airflow to backfill any missed syncs
CREATE OR REPLACE FUNCTION reconcile_purchases_to_transactions()
RETURNS TABLE(inserted_count INTEGER, error_count INTEGER) AS $$
DECLARE
    v_inserted INTEGER := 0;
    v_errors INTEGER := 0;
    v_purchase RECORD;
BEGIN
    -- Find purchases not in transactions
    FOR v_purchase IN
        SELECT p.*
        FROM purchases p
        LEFT JOIN transactions t ON p.user_id = t.user_id
            AND p.product_id = t.product_id
            AND p.purchase_date = t.transaction_date
        WHERE t.transaction_id IS NULL
          AND p.status = 'completed'
          AND p.purchase_date >= NOW() - INTERVAL '30 days'
    LOOP
        BEGIN
            INSERT INTO transactions (
                user_id,
                product_id,
                transaction_date,
                amount,
                status
            ) VALUES (
                v_purchase.user_id,
                v_purchase.product_id,
                v_purchase.purchase_date,
                v_purchase.price,
                v_purchase.status
            )
            ON CONFLICT DO NOTHING;

            v_inserted := v_inserted + 1;

        EXCEPTION
            WHEN OTHERS THEN
                v_errors := v_errors + 1;
                RAISE WARNING 'Failed to insert purchase %: %', v_purchase.id, SQLERRM;
        END;
    END LOOP;

    RETURN QUERY SELECT v_inserted, v_errors;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION reconcile_purchases_to_transactions IS 'Manually reconcile purchases to transactions (backfill)';

-- ==============================================
-- MONITORING QUERIES
-- ==============================================

-- Query to check sync health
-- Run periodically to monitor data consistency
COMMENT ON VIEW v_purchase_discrepancy_report IS 'Expected: 0 discrepancies. Run: SELECT * FROM v_purchase_discrepancy_report;';

-- ==============================================
-- COMPLETION MESSAGE
-- ==============================================

DO $$
DECLARE
    purchase_count INTEGER;
    transaction_count INTEGER;
    discrepancy_count INTEGER;
BEGIN
    -- Count records
    SELECT COUNT(*) INTO purchase_count FROM purchases WHERE status = 'completed';
    SELECT COUNT(*) INTO transaction_count FROM transactions WHERE status = 'completed';

    -- Check discrepancies
    SELECT SUM(count) INTO discrepancy_count FROM v_purchase_discrepancy_report;

    RAISE NOTICE '✅ Purchases <-> Transactions sync configuration complete';
    RAISE NOTICE '';
    RAISE NOTICE '📊 Current Status:';
    RAISE NOTICE '   Purchases (frontend): % records', purchase_count;
    RAISE NOTICE '   Transactions (ML pipeline): % records', transaction_count;
    RAISE NOTICE '   Discrepancies (last 7 days): %', COALESCE(discrepancy_count, 0);
    RAISE NOTICE '';
    RAISE NOTICE '🔧 Sync Mechanism:';
    RAISE NOTICE '   ✅ Trigger: purchases INSERT → transactions INSERT';
    RAISE NOTICE '   ✅ View: v_unified_purchase_history (deduped)';
    RAISE NOTICE '   ✅ Monitor: v_purchase_discrepancy_report';
    RAISE NOTICE '   ✅ Reconciliation: reconcile_purchases_to_transactions()';
    RAISE NOTICE '';
    RAISE NOTICE '🎯 Next Steps:';
    RAISE NOTICE '   1. Test purchase flow: POST /api/v1/purchases';
    RAISE NOTICE '   2. Verify sync: SELECT * FROM v_purchase_discrepancy_report;';
    RAISE NOTICE '   3. Backfill if needed: SELECT * FROM reconcile_purchases_to_transactions();';
    RAISE NOTICE '   4. Schedule periodic reconciliation in Airflow';
END $$;
