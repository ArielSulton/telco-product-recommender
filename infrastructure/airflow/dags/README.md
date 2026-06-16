# Airflow DAGs

Folder ini berisi DAG Airflow untuk pipeline data dan retraining model Paketify.

## Status Saat Ini

Airflow adalah service pendukung untuk orkestrasi ETL, feature engineering, dan retraining. Aplikasi web aktif tetap berjalan melalui backend FastAPI dan model Random Forest v2 yang berada di:

```text
ml/models/kaggle_rf/kaggle_rf_recommender.pkl
```

## DAG Utama

```text
data_ingestion.py
feature_engineering.py
manual_train_baseline.py
model_retraining.py
rf_v2_retraining.py
```

## Peran DAG

- `data_ingestion.py`
  Memantau ingestion data dari simulator.

- `feature_engineering.py`
  Menghitung ulang fitur seperti RFM, ARPU, usage, dan fitur perilaku lain.

- `rf_v2_retraining.py`
  Jalur retraining Random Forest v2.

- `model_retraining.py`
  Jalur retraining umum/legacy.

- `manual_train_baseline.py`
  Training manual untuk baseline/eksperimen.

## Menjalankan Airflow

Dari root project:

```bash
docker compose -f compose.dev.yaml up -d airflow-init airflow-webserver airflow-scheduler
```

Buka:

```text
http://localhost:8080
```

Credential mengikuti `.env`. Default development biasanya:

```text
username: airflow
password: airflow
```

atau:

```text
username: admin
password: admin
```

## Koneksi Internal

PostgreSQL:

```text
host: postgres
port: 5432
database: telco_recommender
username: postgres
password: postgres123
```

Backend:

```text
http://backend:8000
```

MLflow:

```text
http://mlflow:5000
```

Redis:

```text
redis:6379
```

## Debug

Lihat status container:

```bash
docker compose -f compose.dev.yaml ps airflow-webserver airflow-scheduler
```

Log webserver:

```bash
docker compose -f compose.dev.yaml logs -f airflow-webserver
```

Log scheduler:

```bash
docker compose -f compose.dev.yaml logs -f airflow-scheduler
```

## Catatan

Dashboard admin aplikasi belum mengelola retraining secara langsung. Untuk monitoring pipeline dan retraining, gunakan Airflow UI dan MLflow UI.
