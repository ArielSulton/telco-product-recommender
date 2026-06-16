-- ==============================================
-- INDONESIAN CATALOG FOR RF RECOMMENDATION CLASSES
-- ==============================================
-- Provides three active products for each Random Forest output class.

INSERT INTO products (
    product_id,
    product_name,
    product_family,
    price,
    quota_data_mb,
    quota_voice_min,
    quota_sms,
    validity_days,
    kategori_rekomendasi,
    tags,
    ikut_rekomendasi,
    is_active,
    metadata
) VALUES
    ('IDN001', 'Paket Awal Hemat 2GB', 'data', 15000, 2048, 0, 0, 7, 'starter', ARRAY['starter', 'trial', 'budget'], TRUE, TRUE, '{"benefit":"2GB - 7 Hari","kelas_model":"Paket Pemula"}'),
    ('IDN002', 'Paket Awal Sosmed 4GB', 'data', 25000, 4096, 0, 0, 14, 'starter', ARRAY['starter', 'social', 'budget'], TRUE, TRUE, '{"benefit":"4GB - 14 Hari","kelas_model":"Paket Pemula"}'),
    ('IDN003', 'Paket Awal Kombo 5GB', 'combo', 35000, 5120, 30, 30, 30, 'starter', ARRAY['starter', 'combo', 'value'], TRUE, TRUE, '{"benefit":"5GB + 30 Menit - 30 Hari","kelas_model":"Paket Pemula"}'),

    ('IDN004', 'Paket Kuota Besar 25GB', 'data', 75000, 25600, 0, 0, 30, 'data', ARRAY['data', 'quota', 'heavy-usage'], TRUE, TRUE, '{"benefit":"25GB - 30 Hari","kelas_model":"Paket Kuota Besar"}'),
    ('IDN005', 'Paket Kuota Besar 50GB', 'data', 115000, 51200, 0, 0, 30, 'data', ARRAY['data', 'quota', 'streaming'], TRUE, TRUE, '{"benefit":"50GB - 30 Hari","kelas_model":"Paket Kuota Besar"}'),
    ('IDN006', 'Paket Kuota Besar 100GB', 'data', 165000, 102400, 0, 0, 30, 'data', ARRAY['data', 'quota', 'heavy-usage'], TRUE, TRUE, '{"benefit":"100GB - 30 Hari","kelas_model":"Paket Kuota Besar"}'),

    ('IDN007', 'Paket Telepon Hemat 300 Menit', 'voice', 20000, 0, 300, 50, 30, 'voice', ARRAY['voice', 'call', 'budget'], TRUE, TRUE, '{"benefit":"300 Menit + 50 SMS - 30 Hari","kelas_model":"Paket Telepon"}'),
    ('IDN008', 'Paket Telepon Bebas 750 Menit', 'voice', 40000, 0, 750, 100, 30, 'voice', ARRAY['voice', 'call', 'talk'], TRUE, TRUE, '{"benefit":"750 Menit + 100 SMS - 30 Hari","kelas_model":"Paket Telepon"}'),
    ('IDN009', 'Paket Telepon Maksimal 1000 Menit', 'voice', 60000, 1024, 1000, 200, 30, 'voice', ARRAY['voice', 'call', 'premium'], TRUE, TRUE, '{"benefit":"1000 Menit + 1GB - 30 Hari","kelas_model":"Paket Telepon"}'),

    ('IDN010', 'Paket Keluarga Kombo 20GB', 'combo', 85000, 20480, 300, 200, 30, 'combo', ARRAY['combo', 'family', 'shared'], TRUE, TRUE, '{"benefit":"20GB + 300 Menit - 30 Hari","kelas_model":"Paket Keluarga/Kombo"}'),
    ('IDN011', 'Paket Keluarga Berbagi 40GB', 'combo', 135000, 40960, 600, 500, 30, 'combo', ARRAY['combo', 'family', 'shared'], TRUE, TRUE, '{"benefit":"40GB + 600 Menit - 30 Hari","kelas_model":"Paket Keluarga/Kombo"}'),
    ('IDN012', 'Paket Keluarga Maksimal 75GB', 'combo', 195000, 76800, 1000, 1000, 30, 'combo', ARRAY['combo', 'family', 'premium'], TRUE, TRUE, '{"benefit":"75GB + 1000 Menit - 30 Hari","kelas_model":"Paket Keluarga/Kombo"}'),

    ('IDN013', 'Paket Setia Hemat 8GB', 'combo', 30000, 8192, 50, 50, 45, 'retention', ARRAY['retention', 'loyalty', 'budget'], TRUE, TRUE, '{"benefit":"8GB + Bonus Masa Aktif - 45 Hari","kelas_model":"Paket Retensi"}'),
    ('IDN014', 'Paket Setia Kombo 15GB', 'combo', 50000, 15360, 150, 100, 45, 'retention', ARRAY['retention', 'loyalty', 'promo'], TRUE, TRUE, '{"benefit":"15GB + 150 Menit - 45 Hari","kelas_model":"Paket Retensi"}'),
    ('IDN015', 'Paket Kembali Aktif 25GB', 'combo', 65000, 25600, 200, 200, 60, 'retention', ARRAY['retention', 'loyalty', 'promo'], TRUE, TRUE, '{"benefit":"25GB + Bonus Masa Aktif - 60 Hari","kelas_model":"Paket Retensi"}'),

    ('IDN016', 'Paket Premium Streaming 50GB', 'data', 135000, 51200, 0, 0, 30, 'premium', ARRAY['premium', 'streaming', 'video'], TRUE, TRUE, '{"benefit":"50GB Streaming - 30 Hari","kelas_model":"Paket Data Premium"}'),
    ('IDN017', 'Paket Premium Tanpa Batas', 'data', 185000, 102400, 0, 0, 30, 'premium', ARRAY['premium', 'unlimited', 'streaming'], TRUE, TRUE, '{"benefit":"Internet Tanpa Batas FUP 100GB - 30 Hari","kelas_model":"Paket Data Premium"}'),
    ('IDN018', 'Paket Premium Jelajah 75GB', 'data', 210000, 76800, 100, 100, 30, 'premium', ARRAY['premium', 'roaming', 'travel'], TRUE, TRUE, '{"benefit":"75GB + Roaming - 30 Hari","kelas_model":"Paket Data Premium"}')
ON CONFLICT (product_id) DO UPDATE SET
    product_name = EXCLUDED.product_name,
    product_family = EXCLUDED.product_family,
    price = EXCLUDED.price,
    quota_data_mb = EXCLUDED.quota_data_mb,
    quota_voice_min = EXCLUDED.quota_voice_min,
    quota_sms = EXCLUDED.quota_sms,
    validity_days = EXCLUDED.validity_days,
    kategori_rekomendasi = EXCLUDED.kategori_rekomendasi,
    tags = EXCLUDED.tags,
    ikut_rekomendasi = EXCLUDED.ikut_rekomendasi,
    is_active = EXCLUDED.is_active,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Keep legacy sample packages for old transaction references, but retire them
-- from the visible and recommendation-ready catalog.
UPDATE products
SET is_active = FALSE,
    ikut_rekomendasi = FALSE,
    updated_at = NOW()
WHERE product_id IN ('PKG001', 'PKG002', 'PKG003', 'PKG004', 'PKG005', 'PKG006', 'PKG007', 'PKG008');
