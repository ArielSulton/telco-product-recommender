# Infrastructure - Paketify Telco Recommendation System

Folder ini berisi konfigurasi Docker, PostgreSQL init scripts, MLflow, Airflow, Prometheus, Grafana, dan service pendukung untuk development project Paketify.

## Stack Development

- Docker Compose
- PostgreSQL 14
- Redis 7
- FastAPI backend
- React + Vite frontend
- Adminer PostgreSQL UI
- MLflow
- Jupyter Notebook
- Apache Airflow
- Prometheus
- Grafana

## Struktur Folder

```text
infrastructure/
|-- postgres/
|   `-- init/                 SQL init schema dan seed data
|-- mlflow/                   Dockerfile/config MLflow
|-- airflow/
|   |-- dags/                 DAG Airflow
|   `-- plugins/              Plugin Airflow
`-- monitoring/
    |-- prometheus/           Prometheus config dan alert rules
    `-- grafana/              Dashboard dan provisioning
```

## Menjalankan Development Stack

Dari root project:

```bash
docker compose -f compose.dev.yaml up -d
```

Menjalankan service inti saja:

```bash
docker compose -f compose.dev.yaml up -d postgres redis mlflow backend frontend adminer
```

Melihat status:

```bash
docker compose -f compose.dev.yaml ps
```

Melihat log:

```bash
docker compose -f compose.dev.yaml logs -f backend
```

Stop container tanpa menghapus volume:

```bash
docker compose -f compose.dev.yaml down
```

Hindari `-v` jika tidak ingin data PostgreSQL, Redis, MLflow, Grafana, dan Airflow terhapus.

## Service dan Port

| Service | URL / Port | Keterangan |
| --- | --- | --- |
| Frontend | `http://localhost:5173` | React app |
| Backend | `http://localhost:8000` | FastAPI |
| Swagger | `http://localhost:8000/api/v1/docs` | API docs |
| PostgreSQL | `localhost:5434` | DB host port |
| Redis | `localhost:6379` | Cache |
| Adminer | `http://localhost:8081` | PostgreSQL web UI |
| MLflow | `http://localhost:5000` | Experiment/model tracking |
| Jupyter | `http://localhost:8888` | ML notebook |
| Airflow | `http://localhost:8080` | Orchestration UI |
| Prometheus | `http://localhost:9090` | Metrics |
| Grafana | `http://localhost:3000` | Dashboard |

## Login Adminer

```text
System: PostgreSQL
Server: postgres
Username: postgres
Password: postgres123
Database: telco_recommender
```

Adminer berjalan sebagai container `telco-adminer-dev` dan terhubung ke network Docker yang sama dengan PostgreSQL.

## PostgreSQL

Container:

```text
telco-postgres-dev
```

Database:

```text
telco_recommender
```

Port host:

```text
5434
```

Masuk via terminal:

```bash
docker exec -it telco-postgres-dev psql -U postgres -d telco_recommender
```

Contoh query:

```sql
SELECT product_id, product_name, kategori_rekomendasi, ikut_rekomendasi
FROM products
ORDER BY product_id;
```

```sql
SELECT category, status, created_at
FROM complaints
ORDER BY created_at DESC
LIMIT 10;
```

## Init SQL

File init utama:

```text
infrastructure/postgres/init/01_init.sql
infrastructure/postgres/init/02_create_users_table.sql
infrastructure/postgres/init/03_add_rf_v2_features.sql
infrastructure/postgres/init/04_sync_transactions_purchases.sql
infrastructure/postgres/init/05_create_user_preferences.sql
infrastructure/postgres/init/06_add_product_metadata.sql
infrastructure/postgres/init/07_seed_indonesian_recommendation_products.sql
infrastructure/postgres/init/08_create_complaints.sql
```

Catatan: file init PostgreSQL hanya otomatis dijalankan saat volume database pertama kali dibuat. Untuk database yang sudah ada, perubahan runtime juga ditangani oleh endpoint/backend bila diperlukan, atau perlu dijalankan manual jika ingin sinkron penuh.

## Data Penting Yang Jangan Dihapus Sembarangan

Volume Docker penting:

- `telco-recommender-dev_postgres_data`
- `telco-recommender-dev_redis_data`
- `telco-recommender-dev_mlflow_data`
- `telco-recommender-dev_grafana_data`
- `telco-recommender-dev_airflow_logs`
- `telco-recommender-dev_frontend_node_modules`

Perintah yang aman untuk stop:

```bash
docker compose -f compose.dev.yaml down
```

Perintah yang berisiko menghapus data:

```bash
docker compose -f compose.dev.yaml down -v
docker volume prune
```

## MLflow

MLflow digunakan sebagai layanan pendukung untuk eksperimen/model tracking.

```text
http://localhost:5000
```

Backend development memiliki environment:

```text
MLFLOW_TRACKING_URI=http://mlflow:5000
```

## Airflow

Airflow tersedia untuk pipeline ETL/retraining. Untuk saat ini, monitoring dan trigger pipeline lebih aman dilakukan langsung melalui Airflow UI.

```text
http://localhost:8080
```

Credential default mengikuti environment:

```text
username: airflow/admin sesuai .env
password: airflow/admin sesuai .env
```

## Monitoring

Prometheus:

```text
http://localhost:9090
```

Grafana:

```text
http://localhost:3000
```

Default Grafana development:

```text
username: admin
password: admin
```

## Health Check

Backend:

```bash
curl http://localhost:8000/health
```

PostgreSQL:

```bash
docker exec telco-postgres-dev pg_isready -U postgres
```

Redis:

```bash
docker exec telco-redis-dev redis-cli ping
```

## Catatan Produksi

`compose.prod.yaml` disiapkan sebagai konfigurasi production-oriented. Untuk deployment sungguhan, pastikan:

- Secret tidak memakai default development.
- Volume dan backup PostgreSQL disiapkan.
- Domain, HTTPS, dan reverse proxy dikonfigurasi.
- Resource limit dan monitoring disesuaikan.
- Airflow/MLflow/Grafana tidak dibuka publik tanpa proteksi.
