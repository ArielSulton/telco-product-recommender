# Backend - Paketify Telco Recommendation API

Backend ini adalah service FastAPI untuk autentikasi, katalog produk, pembelian, keluhan, admin dashboard, dan serving rekomendasi Random Forest v2.

## Stack

- FastAPI
- PostgreSQL
- Redis
- SQLAlchemy / asyncpg / psycopg2
- JWT authentication
- MLflow client
- Random Forest inference service

## Peran Backend Saat Ini

- Menyediakan REST API untuk frontend React.
- Mengambil fitur pengguna dari database.
- Memanggil `RFRecommenderService`.
- Memetakan label model ke produk aktif di katalog.
- Mengelola metadata produk admin:
  - `kategori_rekomendasi`
  - `tags`
  - `ikut_rekomendasi`
- Menghapus cache rekomendasi setelah perubahan penting seperti pembelian, update produk, dan keluhan.
- Menggunakan `complaint_count` sebagai sinyal retensi.

## Struktur Folder

```text
backend/
|-- app/
|   |-- api/v1/endpoints/      Route FastAPI
|   |-- core/                  Config, security, middleware, logging
|   |-- db/                    Koneksi database dan model user
|   |-- ml/                    RF recommender dan model legacy
|   |-- models/                SQLAlchemy model dan schema
|   `-- services/              Business logic dan cache invalidation
|-- scripts/                   Script seed admin
|-- tests/                     Unit/integration tests
|-- requirements.txt
|-- requirements-dev.txt
`-- Dockerfile
```

## Endpoint Utama

### Auth

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/sync-ml-users`

### Rekomendasi

- `POST /api/v1/recommend/v2`
- `GET /api/v1/recommend/v2/model-info`
- `POST /api/v1/recommend`

### Produk

- `GET /api/v1/products`
- `GET /api/v1/products/{product_id}`
- `GET /api/v1/admin/products`
- `POST /api/v1/admin/products`
- `PUT /api/v1/admin/products/{product_id}`
- `DELETE /api/v1/admin/products/{product_id}`

### Pembelian

- `POST /api/v1/purchases`
- `GET /api/v1/purchases/history`

### Keluhan

- `POST /api/v1/complaints`
- `GET /api/v1/complaints/me`
- `GET /api/v1/admin/complaints`
- `PUT /api/v1/admin/complaints/{complaint_id}`

### Admin

- `GET /api/v1/admin/stats`
- `GET /api/v1/admin/user-recommendations`

## Menjalankan Dengan Docker

Dari root project:

```bash
docker compose -f compose.dev.yaml up -d postgres redis mlflow backend
```

Dokumentasi API:

```text
http://localhost:8000/api/v1/docs
```

Health check:

```text
http://localhost:8000/health
```

## Menjalankan Lokal Tanpa Docker

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Pastikan PostgreSQL, Redis, dan environment variable sudah tersedia. Untuk development penuh, cara Docker lebih direkomendasikan.

## Kredensial Development

Admin otomatis dibuat saat backend start:

```text
Phone/Username: admin
Password: admin123
```

## Model Serving

File utama:

```text
backend/app/ml/rf_recommender.py
backend/app/services/recommendation_service.py
backend/app/api/v1/endpoints/recommendations_v2.py
```

Artifact model yang dibaca:

```text
ml/models/kaggle_rf/kaggle_rf_recommender.pkl
ml/models/kaggle_rf/metadata.json
```

Alur singkat:

1. Endpoint `/recommend/v2` menerima `user_id`.
2. Backend mengambil fitur pengguna.
3. Random Forest memprediksi label rekomendasi.
4. Backend memilih produk aktif yang paling cocok.
5. Produk dikembalikan ke frontend.

## Testing dan Build Check

Compile cepat:

```bash
python -m compileall app
```

Test:

```bash
pytest tests/ -v
```

## Catatan

Pipeline lama K-Means, LightFM, dan XGBoost masih ada di codebase sebagai fallback atau arsip arsitektur awal. Sistem web aktif saat ini diarahkan ke Random Forest v2.
