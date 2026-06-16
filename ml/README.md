# ML - Paketify Random Forest Recommendation Pipeline

Folder ini berisi dataset, preprocessing, feature engineering, training, evaluasi, dan artifact model Random Forest v2 yang dipakai backend.

## Status Saat Ini

Model utama project saat ini adalah **Random Forest classifier**. Model dilatih menggunakan dataset Telco Customer Churn Kaggle sebanyak 7.043 data pelanggan, lalu diperkaya dengan fitur perilaku, label rekomendasi berbasis aturan bisnis, transaksi sintetis, dan event sintetis untuk kebutuhan aplikasi.

Pipeline hybrid lama berbasis K-Means, LightFM, dan XGBoost masih ada sebagai referensi lama, tetapi bukan jalur utama aplikasi web saat ini.

## Output Model

Model memprediksi kelas rekomendasi:

- `Paket Pemula`
- `Paket Kuota Besar`
- `Paket Telepon`
- `Paket Keluarga/Kombo`
- `Paket Retensi`
- `Paket Data Premium`

Backend kemudian memetakan kelas tersebut ke produk aktif di database.

## Evaluasi Terbaru

```text
Accuracy: 86.8%
Top-3 Accuracy: 99.57%
```

File evaluasi berada di:

```text
ml/models/kaggle_rf/evaluation_plots/
```

Contoh output:

- `confusion_matrix_rf.png`
- `feature_importance_rf.png`
- `classification_metrics_rf.png`
- `classification_report.csv`
- `evaluation_summary.json`

## Struktur Folder

```text
ml/
|-- data/
|   |-- raw/                  Dataset mentah
|   |-- processed/            Dataset hasil cleaning
|   `-- features/             Dataset fitur dan target
|-- models/
|   `-- kaggle_rf/            Artifact Random Forest aktif
|-- notebook/
|   `-- kaggle_rf_retraining.ipynb
|-- scripts/
|   |-- preprocess_telco_kaggle.py
|   |-- build_telco_recommendation_targets.py
|   |-- generate_telco_synthetic_behavior.py
|   `-- generate_rf_evaluation_plots.py
|-- requirements.txt
`-- Dockerfile
```

## Dataset dan File Penting

Raw:

```text
ml/data/raw/Telco_customer_churn.xlsx
```

Processed/features:

```text
ml/data/processed/telco_customer_churn_clean.csv
ml/data/features/telco_user_profile_features.csv
ml/data/features/telco_training_dataset_with_targets.csv
ml/data/features/telco_synthetic_transactions.csv
ml/data/features/telco_synthetic_events.csv
```

Artifact model aktif:

```text
ml/models/kaggle_rf/kaggle_rf_recommender.pkl
ml/models/kaggle_rf/metadata.json
```

## Fitur Input Model

Model menggunakan fitur perilaku dan hasil rekayasa fitur seperti:

- `plan_type`
- `device_brand`
- `avg_data_usage_gb`
- `pct_video_usage`
- `avg_call_duration`
- `sms_freq`
- `monthly_spend`
- `topup_freq`
- `travel_score`
- `complaint_count`
- fitur turunan seperti loyalty, ARPU, dan intensitas penggunaan

## Alur Retraining Lokal

Jalankan dari root atau folder `ml` sesuai kebutuhan.

### 1. Install dependency

```bash
cd ml
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Preprocessing dataset

```bash
python scripts/preprocess_telco_kaggle.py
```

### 3. Bangun target rekomendasi

```bash
python scripts/build_telco_recommendation_targets.py
```

### 4. Generate data sintetis

```bash
python scripts/generate_telco_synthetic_behavior.py
```

### 5. Retraining model

Gunakan notebook:

```text
ml/notebook/kaggle_rf_retraining.ipynb
```

### 6. Generate plot evaluasi

```bash
python scripts/generate_rf_evaluation_plots.py
```

## Jupyter Via Docker

Dari root project:

```bash
docker compose -f compose.dev.yaml up -d ml
```

Buka:

```text
http://localhost:8888
```

## MLflow

MLflow UI:

```text
http://localhost:5000
```

Untuk development saat ini, artifact RF aktif juga disimpan langsung di folder `ml/models/kaggle_rf/` supaya backend bisa membacanya lewat volume Docker.

## Catatan Untuk Jurnal

Deskripsi yang sesuai dengan kondisi project:

- Sistem rekomendasi produk telekomunikasi berbasis web.
- Frontend menggunakan React.js.
- Backend menggunakan FastAPI.
- Database menggunakan PostgreSQL.
- Model rekomendasi menggunakan Random Forest.
- Dataset utama Telco Customer Churn sebanyak 7.043 pelanggan.
- Dataset diperkaya dengan fitur perilaku dan label rekomendasi berbasis aturan bisnis.
- Aplikasi menyediakan dashboard pengguna dan dashboard admin.
