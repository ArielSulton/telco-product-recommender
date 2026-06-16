-- ADD PRODUCT RECOMMENDATION 
-- Keeps existing databases aligned with the product ORM/admin API.

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS kategori_rekomendasi VARCHAR(50),
    ADD COLUMN IF NOT EXISTS ikut_rekomendasi BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

COMMENT ON COLUMN products.kategori_rekomendasi IS 'Kategori rekomendasi produk untuk filtering kandidat';
COMMENT ON COLUMN products.ikut_rekomendasi IS 'Menentukan apakah produk boleh dipakai oleh recommendation engine';
COMMENT ON COLUMN products.metadata IS 'Metadata tambahan produk untuk UI dan aturan bisnis';

CREATE INDEX IF NOT EXISTS idx_products_kategori_rekomendasi
    ON products(kategori_rekomendasi)
    WHERE ikut_rekomendasi = TRUE AND is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_products_metadata ON products USING GIN(metadata);
