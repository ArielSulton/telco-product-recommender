# Data Simulator

Service ini mensimulasikan ingestion data perilaku pelanggan dari CSV ke PostgreSQL untuk kebutuhan development.

## Peran Saat Ini

Data simulator bersifat pendukung. Sistem rekomendasi aktif saat ini menggunakan Random Forest v2 dari pipeline Kaggle Telco Churn dan data sintetis yang sudah diproses di folder `ml/`.

Simulator tetap berguna untuk:

- mengisi data transaksi/event development,
- mencoba alur ingestion bertahap,
- menguji pipeline Airflow atau monitoring,
- eksperimen data streaming lokal.

## Stack

- Python
- pandas
- psycopg2
- APScheduler
- PostgreSQL
- Redis

## File Penting

```text
services/data-simulator/simulator.py
services/data-simulator/scheduler.py
services/data-simulator/config.yaml
services/data-simulator/requirements.txt
```

Sumber data default:

```text
ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv
```

## Menjalankan Dengan Docker

Dari root project:

```bash
docker compose -f compose.dev.yaml up -d data-simulator
```

Log:

```bash
docker compose -f compose.dev.yaml logs -f data-simulator
```

Stop:

```bash
docker compose -f compose.dev.yaml stop data-simulator
```

## Environment

```text
DATABASE_URL=postgresql://postgres:postgres123@postgres:5432/telco_recommender
DATA_SOURCE_PATH=/app/ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv
BATCH_SIZE=1000
INGESTION_INTERVAL_HOURS=4
START_IMMEDIATELY=true
REPLAY_MODE=false
REDIS_HOST=redis
REDIS_PORT=6379
```

## Cek Data

Via Adminer:

```text
http://localhost:8081
```

Atau via terminal:

```bash
docker exec -it telco-postgres-dev psql -U postgres -d telco_recommender
```

Contoh query:

```sql
SELECT COUNT(*) FROM transactions;
SELECT COUNT(*) FROM events;
SELECT * FROM ingestion_batches ORDER BY batch_start_time DESC LIMIT 10;
```

## Catatan Produk

Mapping produk lama seperti `PKG001` sampai `PKG008` tidak lagi menjadi katalog utama rekomendasi. Produk rekomendasi aktif saat ini memakai seed Indonesia `IDN001` sampai `IDN018` dan metadata rekomendasi di tabel `products`.
