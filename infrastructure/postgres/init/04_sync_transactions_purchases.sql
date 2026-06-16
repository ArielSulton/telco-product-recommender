-- ==============================================
-- SINKRONISASI TRANSACTIONS <-> PURCHASES
-- ==============================================
-- Skrip sinkronisasi PostgreSQL untuk pelacakan pembelian dua tabel
-- Dibuat: 2025-01-20
-- Tujuan: Menjaga konsistensi data antara tabel ML pipeline (transactions)
--         dan sistem frontend (purchases)
-- Ketergantungan: 01_init.sql, 03_add_rf_v2_features.sql
-- ==============================================

-- ==============================================
-- LATAR BELAKANG
-- ==============================================
-- Sistem menggunakan DUA tabel pelacakan pembelian:
--
-- 1. Tabel `transactions` (dari 01_init.sql)
--    - Digunakan oleh ML pipeline (model hybrid: K-Means, LightFM, XGBoost)
--    - Skema: user_id (referensi users.user_id), product_id, amount, status
--    - Tujuan: Collaborative filtering, segmentasi, rekomendasi dasar
--
-- 2. Tabel `purchases` (dari backend purchases.py + 03_add_rf_v2_features.sql)
--    - Digunakan oleh frontend dan model RF v2
--    - Skema: user_id (referensi app_users.id), product_name, product_family, quota_data_mb
--    - Tujuan: Pelacakan fitur real-time, inferensi perilaku, rekomendasi RF
--
-- Desain dua tabel ini ada karena:
-- - ML pipeline menggunakan tabel `users` (msisdn di-hash SHA-256)
-- - Frontend menggunakan tabel `app_users` (autentikasi dengan phone, password, balance)
-- - Skema berbeda melayani tujuan berbeda (amount vs kuota, product_id vs product_family)
--
-- ==============================================

-- ==============================================
-- STRATEGI SINKRONISASI: REPLIKASI BERBASIS TRIGGER
-- ==============================================

-- Buat fungsi sinkronisasi: purchases → transactions
-- Ketika pembelian dimasukkan ke `purchases`, replikasi ke `transactions` untuk ML pipeline
CREATE OR REPLACE FUNCTION sync_purchase_to_transaction()
RETURNS TRIGGER AS $$
DECLARE
    ml_user_id UUID;
BEGIN
    -- Petakan app_users.id ke users.user_id menggunakan nomor telepon
    -- Ini mengasumsikan tabel users memiliki msisdn_hash dan app_users memiliki phone
    -- Untuk MVP, kita gunakan pemetaan UUID langsung

    -- Opsi 1: Pemetaan UUID langsung (jika app_users.id == users.user_id)
    ml_user_id := NEW.user_id;

    -- Opsi 2: Pencarian via phone (membutuhkan kolom phone di tabel users)
    -- SELECT user_id INTO ml_user_id FROM users WHERE phone = (
    --     SELECT phone FROM app_users WHERE id = NEW.user_id
    -- );

    -- Masukkan ke tabel transactions untuk ML pipeline
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
    ON CONFLICT DO NOTHING;  -- Hindari duplikasi

    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        -- Catat error tapi jangan gagalkan pembelian
        RAISE WARNING 'Gagal sinkronisasi pembelian ke transactions: %', SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sync_purchase_to_transaction IS 'Sinkronisasi tabel purchases ke tabel transactions untuk ML pipeline';

-- Buat trigger pada tabel purchases
DROP TRIGGER IF EXISTS trigger_sync_purchase_to_transaction ON purchases;
CREATE TRIGGER trigger_sync_purchase_to_transaction
    AFTER INSERT ON purchases
    FOR EACH ROW
    EXECUTE FUNCTION sync_purchase_to_transaction();

COMMENT ON TRIGGER trigger_sync_purchase_to_transaction ON purchases IS 'Auto-sinkronisasi purchases ke transactions untuk ML pipeline';

-- ==============================================
-- VIEW REKONSILIASI
-- ==============================================

-- View: Riwayat pembelian terpadu (menggabungkan kedua tabel)
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
      -- Kecualikan transaksi yang sudah ada di purchases (hindari duplikasi)
      SELECT 1 FROM purchases p
      WHERE p.user_id = t.user_id
        AND p.product_id = t.product_id
        AND p.purchase_date = t.transaction_date
  );

COMMENT ON VIEW v_unified_purchase_history IS 'View terpadu semua pembelian dari kedua tabel (tanpa duplikasi)';

-- View: Laporan ketidaksesuaian pembelian (untuk monitoring)
CREATE OR REPLACE VIEW v_purchase_discrepancy_report AS
SELECT
    'ada_di_purchases_tidak_di_transactions' AS jenis_ketidaksesuaian,
    COUNT(*) AS jumlah
FROM purchases p
LEFT JOIN transactions t ON p.user_id = t.user_id
    AND p.product_id = t.product_id
    AND p.purchase_date = t.transaction_date
WHERE t.transaction_id IS NULL
  AND p.status = 'completed'
  AND p.purchase_date >= NOW() - INTERVAL '7 days'

UNION ALL

SELECT
    'ada_di_transactions_tidak_di_purchases' AS jenis_ketidaksesuaian,
    COUNT(*) AS jumlah
FROM transactions t
LEFT JOIN purchases p ON t.user_id = p.user_id
    AND t.product_id = p.product_id
    AND t.transaction_date = p.purchase_date
WHERE p.id IS NULL
  AND t.status = 'completed'
  AND t.transaction_date >= NOW() - INTERVAL '7 days';

COMMENT ON VIEW v_purchase_discrepancy_report IS 'Pantau masalah sinkronisasi antara tabel purchases dan transactions';

-- ==============================================
-- FUNGSI REKONSILIASI DATA
-- ==============================================

-- Fungsi untuk merekonsiliasi transaksi yang hilang secara manual
-- Jalankan secara berkala via cron atau Airflow untuk mengisi ulang sinkronisasi yang terlewat
CREATE OR REPLACE FUNCTION reconcile_purchases_to_transactions()
RETURNS TABLE(inserted_count INTEGER, error_count INTEGER) AS $$
DECLARE
    v_inserted INTEGER := 0;
    v_errors INTEGER := 0;
    v_purchase RECORD;
BEGIN
    -- Cari pembelian yang belum ada di transactions
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
                RAISE WARNING 'Gagal memasukkan pembelian %: %', v_purchase.id, SQLERRM;
        END;
    END LOOP;

    RETURN QUERY SELECT v_inserted, v_errors;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION reconcile_purchases_to_transactions IS 'Rekonsiliasi manual purchases ke transactions (backfill)';

-- ==============================================
-- QUERY MONITORING
-- ==============================================

-- Query untuk memeriksa kesehatan sinkronisasi
-- Jalankan secara berkala untuk memantau konsistensi data
COMMENT ON VIEW v_purchase_discrepancy_report IS 'Diharapkan: 0 ketidaksesuaian. Jalankan: SELECT * FROM v_purchase_discrepancy_report;';

-- ==============================================
-- PESAN SELESAI
-- ==============================================

DO $$
DECLARE
    purchase_count INTEGER;
    transaction_count INTEGER;
    discrepancy_count INTEGER;
BEGIN
    -- Hitung jumlah record
    SELECT COUNT(*) INTO purchase_count FROM purchases WHERE status = 'completed';
    SELECT COUNT(*) INTO transaction_count FROM transactions WHERE status = 'completed';

    -- Periksa ketidaksesuaian
    SELECT SUM(jumlah) INTO discrepancy_count FROM v_purchase_discrepancy_report;

    RAISE NOTICE '✅ Konfigurasi sinkronisasi Purchases <-> Transactions selesai';
    RAISE NOTICE '';
    RAISE NOTICE '📊 Status Saat Ini:';
    RAISE NOTICE '   Purchases (frontend): % record', purchase_count;
    RAISE NOTICE '   Transactions (ML pipeline): % record', transaction_count;
    RAISE NOTICE '   Ketidaksesuaian (7 hari terakhir): %', COALESCE(discrepancy_count, 0);
    RAISE NOTICE '';
    RAISE NOTICE '🔧 Mekanisme Sinkronisasi:';
    RAISE NOTICE '   ✅ Trigger: purchases INSERT → transactions INSERT';
    RAISE NOTICE '   ✅ View: v_unified_purchase_history (tanpa duplikasi)';
    RAISE NOTICE '   ✅ Monitor: v_purchase_discrepancy_report';
    RAISE NOTICE '   ✅ Rekonsiliasi: reconcile_purchases_to_transactions()';
    RAISE NOTICE '';
    RAISE NOTICE '🎯 Langkah Selanjutnya:';
    RAISE NOTICE '   1. Test alur pembelian: POST /api/v1/purchases';
    RAISE NOTICE '   2. Verifikasi sinkronisasi: SELECT * FROM v_purchase_discrepancy_report;';
    RAISE NOTICE '   3. Backfill jika perlu: SELECT * FROM reconcile_purchases_to_transactions();';
    RAISE NOTICE '   4. Jadwalkan rekonsiliasi berkala di Airflow';
END $$;
