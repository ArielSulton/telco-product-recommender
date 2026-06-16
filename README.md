# ASAH Capstone - Paketify Telco Recommendation System

![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen)
![Recommender](https://img.shields.io/badge/Recommender-Random%20Forest%20v2-2f855a)
![Backend](https://img.shields.io/badge/Backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61dafb)
![Infra](https://img.shields.io/badge/Infra-Docker%20Compose-2496ed)

Paketify adalah aplikasi web rekomendasi produk telekomunikasi. Sistem ini membantu pengguna memilih paket data, telepon, combo, premium, starter, dan retensi berdasarkan perilaku serta preferensi pengguna.

## Ringkasan Sistem

Sistem aktif saat ini menggunakan:

- Frontend: React + Vite
- Backend: FastAPI
- Database: PostgreSQL
- Cache: Redis
- Model rekomendasi utama: Random Forest v2
- Model artifact: `ml/models/kaggle_rf/kaggle_rf_recommender.pkl`
- Monitoring dan pendukung: MLflow, Airflow, Prometheus, Grafana, Adminer

Jalur rekomendasi utama:

```text
POST /api/v1/recommend/v2
```

Jalur lama:

```text
POST /api/v1/recommend
```

masih dipertahankan sebagai fallback dan referensi arsitektur lama.

## Fitur Utama

- Autentikasi pengguna dan admin berbasis JWT.
- Onboarding preferensi pengguna.
- Rekomendasi paket berbasis Random Forest v2.
- Katalog produk dengan metadata rekomendasi:
  - `kategori_rekomendasi`
  - `tags`
  - `ikut_rekomendasi`
- Pembelian paket dan riwayat transaksi.
- Dashboard pengguna untuk rekomendasi, paket aktif, transaksi, dan keluhan.
- Dashboard admin untuk mengelola produk, melihat rekomendasi pengguna, dan memantau keluhan.
- Sinyal keluhan pengguna melalui `complaint_count` untuk memprioritaskan paket retensi.
- Adminer untuk melihat PostgreSQL melalui browser.

## Kelas Rekomendasi

Model memprediksi label rekomendasi berikut:

- `Paket Pemula`
- `Paket Kuota Besar`
- `Paket Telepon`
- `Paket Keluarga/Kombo`
- `Paket Retensi`
- `Paket Data Premium`

Label tersebut dipetakan ke produk aktif berdasarkan metadata produk, harga, kuota, masa aktif, tag, riwayat pembelian, dan sinyal keluhan.

## Struktur Project

```text
.
|-- backend/                 FastAPI API dan serving rekomendasi
|-- frontend/                React + Vite web app
|-- infrastructure/          PostgreSQL init, Airflow, MLflow, monitoring
|-- ml/                      Dataset, preprocessing, training, artifact model
|-- services/                Supporting services
|-- compose.dev.yaml         Docker Compose development
|-- compose.prod.yaml        Docker Compose production-oriented
`-- README.md
```

## Quick Start Dengan Docker

### 1. Siapkan environment

```bash
cp .env.example .env
```

Pastikan nilai database development sesuai:

```text
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres123
DATABASE_NAME=telco_recommender
```

### 2. Jalankan stack development

```bash
docker compose -f compose.dev.yaml up -d
```

Jika hanya ingin menjalankan service inti:

```bash
docker compose -f compose.dev.yaml up -d postgres redis mlflow backend frontend adminer
```

### 3. Akses service

| Service | URL |
| --- | --- |
| Frontend | `http://localhost:5173` |
| Backend API docs | `http://localhost:8000/api/v1/docs` |
| Backend health | `http://localhost:8000/health` |
| Adminer PostgreSQL UI | `http://localhost:8081` |
| MLflow | `http://localhost:5000` |
| Jupyter ML | `http://localhost:8888` |
| Airflow | `http://localhost:8080` |
| Grafana | `http://localhost:3000` |
| Prometheus | `http://localhost:9090` |

Login Adminer:

```text
System: PostgreSQL
Server: postgres
Username: postgres
Password: postgres123
Database: telco_recommender
```

## Akun Development

Admin dibuat otomatis saat backend start:

```text
Phone/Username: admin
Password: admin123
Role: admin
```

## Endpoint Penting

### Auth

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

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

## Model dan Data

Artifact utama:

```text
ml/models/kaggle_rf/kaggle_rf_recommender.pkl
ml/models/kaggle_rf/metadata.json
```

Dataset dan fitur hasil pipeline:

```text
ml/data/processed/telco_customer_churn_clean.csv
ml/data/features/telco_user_profile_features.csv
ml/data/features/telco_training_dataset_with_targets.csv
ml/data/features/telco_synthetic_transactions.csv
ml/data/features/telco_synthetic_events.csv
```

Notebook utama:

```text
ml/notebook/kaggle_rf_retraining.ipynb
```

Hasil evaluasi terbaru:

```text
Accuracy: 86.8%
Top-3 Accuracy: 99.57%
```

## Validasi Setelah Menjalankan Project

1. Buka `http://localhost:8000/health`.
2. Buka Swagger di `http://localhost:8000/api/v1/docs`.
3. Login sebagai admin.
4. Cek produk di dashboard admin.
5. Login atau register user.
6. Isi onboarding preferensi.
7. Cek rekomendasi.
8. Lakukan pembelian paket.
9. Kirim keluhan dua kali untuk menguji paket retensi muncul sebagai prioritas.
10. Buka Adminer dan cek tabel `products`, `app_users`, `purchases`, `complaints`, dan `user_preferences`.

## File Penting

Backend:

- `backend/app/api/v1/endpoints/recommendations_v2.py`
- `backend/app/api/v1/endpoints/purchases.py`
- `backend/app/api/v1/endpoints/admin.py`
- `backend/app/api/v1/endpoints/complaints.py`
- `backend/app/services/recommendation_service.py`
- `backend/app/ml/rf_recommender.py`

Frontend:

- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/pages/AdminDashboardPage.jsx`
- `frontend/src/pages/ProductsPage.jsx`
- `frontend/src/components/RecommendationWidget.jsx`

ML:

- `ml/scripts/preprocess_telco_kaggle.py`
- `ml/scripts/build_telco_recommendation_targets.py`
- `ml/scripts/generate_telco_synthetic_behavior.py`
- `ml/scripts/generate_rf_evaluation_plots.py`
- `ml/notebook/kaggle_rf_retraining.ipynb`

Infrastructure:

- `compose.dev.yaml`
- `infrastructure/postgres/init/01_init.sql`
- `infrastructure/postgres/init/06_add_product_metadata.sql`
- `infrastructure/postgres/init/07_seed_indonesian_recommendation_products.sql`
- `infrastructure/postgres/init/08_create_complaints.sql`

## License

Capstone Project - Dicoding ASAH Program.
