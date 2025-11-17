# Airflow ML Training Guide

**File**: `infrastructure/airflow/dags/model_retraining.py`
**Status**: ✅ Fixed - Ready to test

---

## What Was Fixed

### 1. Missing Imports ✅
- Added `mlflow` and `mlflow.sklearn` imports
- Added ML model class imports (KMeansSegmenter, LightFMRecommender, XGBoostRanker)
- Configured Python path to import from backend code

### 2. Docker Configuration ✅
- Added backend code mount: `./backend:/opt/airflow/backend`
- Installed required dependencies via `_PIP_ADDITIONAL_REQUIREMENTS`:
  - `mlflow==2.9.2`
  - `scikit-learn`
  - `lightfm`
  - `xgboost`
  - `joblib`
- Added `MLFLOW_TRACKING_URI=http://mlflow:5000`
- Added dependency on MLflow service

### 3. Both Dev & Production ✅
- Updated `compose.dev.yaml` (3 services)
- Updated `compose.prod.yaml` (3 services)

---

## How It Works

### DAG Workflow

**Schedule**: Weekly (Sunday 2 AM)
**Trigger**: Data drift PSI ≥ 0.2

```
┌─────────────────┐
│ Check Data Drift│
│   (PSI calc)    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
 Drift?    No Drift
    │         │
    ▼         ▼
┌───────┐  ┌──────┐
│Prepare│  │ Skip │
│ Data  │  └──────┘
└───┬───┘
    │
    ▼
┌───────────────────────┐
│ Train Models (||)     │
│ - K-Means            │
│ - LightFM            │
│ - XGBoost            │
└──────────┬────────────┘
           │
           ▼
    ┌──────────┐
    │ Validate │
    └────┬─────┘
         │
    ┌────┴─────┐
    │          │
  Pass?      Fail
    │          │
    ▼          ▼
┌────────┐  ┌──────────┐
│Promote │  │ Rollback │
│to Prod │  └──────────┘
└────────┘
```

### Metrics Logged to MLflow

**K-Means Segmentation**:
- `silhouette_score` - Cluster quality (higher = better)
- `calinski_harabasz_score` - Cluster separation
- `inertia` - Within-cluster sum of squares
- `n_clusters` - Number of clusters (5)
- `training_samples` - Dataset size

**LightFM Collaborative Filtering**:
- `no_components` - Embedding dimensions (50)
- `loss` - Loss function (warp)
- `training_interactions` - Number of user-item interactions

**XGBoost Ranker**:
- `objective` - Ranking objective (rank:pairwise)
- `learning_rate` - 0.1
- `max_depth` - 6

**Data Drift**:
- `avg_psi` - Average Population Stability Index
- `max_psi` - Maximum PSI across features

---

## Testing Airflow DAG

### Prerequisites

```bash
# 1. Start required services
docker compose -f compose.dev.yaml up -d postgres redis mlflow

# 2. Wait for services to be healthy
docker compose -f compose.dev.yaml ps

# 3. Start Airflow
docker compose -f compose.dev.yaml up -d airflow-init airflow-webserver airflow-scheduler
```

### Verify Installation

```bash
# Check Airflow webserver logs
docker logs telco-airflow-webserver-dev --tail 50

# Expected:
# ✅ Dependencies installed (mlflow, scikit-learn, lightfm, xgboost)
# ✅ Backend code mounted at /opt/airflow/backend
# ✅ DAG loaded without import errors
```

### Access Airflow UI

```bash
# Open browser
open http://localhost:8080

# Login credentials (from .env)
Username: admin
Password: admin
```

### Test DAG Manually

**Option 1: Via UI**
1. Open Airflow UI: http://localhost:8080
2. Find DAG: `model_retraining`
3. Click "Trigger DAG" (play button)
4. Monitor task progress

**Option 2: Via CLI**
```bash
# Trigger DAG manually
docker exec -it telco-airflow-scheduler-dev \
  airflow dags trigger model_retraining

# Check DAG status
docker exec -it telco-airflow-scheduler-dev \
  airflow dags list-runs -d model_retraining

# View task logs
docker exec -it telco-airflow-scheduler-dev \
  airflow tasks logs model_retraining check_data_drift <run_date>
```

### Expected Behavior

**First Run** (No production model):
```
1. ✅ check_data_drift → calculates PSI
2. ⏭️ skip_retraining (insufficient new data or no drift)
   OR
   🔄 prepare_training_data → loads from PostgreSQL
3. 🔄 train_segmentation → K-Means training
4. 🔄 train_collaborative → LightFM training
5. 🔄 train_ranker → XGBoost training
6. ✅ validate_models → auto-promotes (no production baseline)
7. ✅ promote_models → sets stage to "Production"
8. ✅ notify_fastapi → webhook notification
```

**Subsequent Runs** (With production model):
```
1. ✅ check_data_drift
   - If max_psi < 0.2 → skip_retraining
   - If max_psi ≥ 0.2 → proceed to training
2. 🔍 validate_models
   - Compares new vs production silhouette score
   - Requires ≥2% improvement
   - Pass → promote, Fail → rollback
```

---

## Verify in MLflow

```bash
# 1. Open MLflow UI
open http://localhost:5000

# 2. Check experiment: "model_retraining"
# 3. Verify runs with metrics

# Expected entries:
# - Run: kmeans_retraining_20251116
#   Metrics: silhouette_score, calinski_harabasz_score, inertia
# - Run: lightfm_retraining_20251116
#   Metrics: training_interactions
# - Run: xgboost_retraining_20251116
#   Metrics: (basic params)

# 4. Check Models registry
# - Model: "kmeans_segmentation"
# - Stage: "Production"
# - Version: 1
```

---

## Troubleshooting

### Error: ModuleNotFoundError: No module named 'mlflow'

**Cause**: Dependencies not installed

**Fix**:
```bash
# Recreate Airflow containers to install dependencies
docker compose -f compose.dev.yaml down airflow-webserver airflow-scheduler
docker compose -f compose.dev.yaml up -d airflow-init airflow-webserver airflow-scheduler

# Wait for startup (~2 minutes)
docker logs telco-airflow-webserver-dev --follow
```

### Error: ModuleNotFoundError: No module named 'app'

**Cause**: Backend code not mounted or Python path incorrect

**Fix**:
```bash
# Verify volume mount
docker exec -it telco-airflow-scheduler-dev ls -la /opt/airflow/backend

# Expected:
# drwxr-xr-x  app/
# Check Python path in logs
docker logs telco-airflow-scheduler-dev | grep "sys.path"
```

### Error: ImportError: cannot import name 'KMeansSegmenter'

**Cause**: Model class file not found

**Fix**:
```bash
# Check if file exists
docker exec -it telco-airflow-scheduler-dev \
  ls -la /opt/airflow/backend/app/ml/models/segmentation/

# Verify import inside container
docker exec -it telco-airflow-scheduler-dev python3 -c \
  "import sys; sys.path.insert(0, '/opt/airflow/backend'); from app.ml.models.segmentation.kmeans_segmenter import KMeansSegmenter; print('OK')"
```

### Error: Connection refused to MLflow

**Cause**: MLflow service not running

**Fix**:
```bash
# Start MLflow
docker compose -f compose.dev.yaml up -d mlflow

# Wait for healthy
docker compose -f compose.dev.yaml ps mlflow

# Test connection from Airflow
docker exec -it telco-airflow-scheduler-dev \
  curl -f http://mlflow:5000/health
```

### Error: Insufficient data for drift detection

**Cause**: No user_features data in database

**Fix**:
```bash
# Run data simulator to populate database
docker compose -f compose.dev.yaml up -d data-simulator

# Verify data
docker exec -it telco-postgres-dev psql -U postgres -d telco_recommender \
  -c "SELECT COUNT(*) FROM user_features;"
```

---

## DAG Configuration

**File**: `infrastructure/airflow/dags/model_retraining.py`

**Customization**:
```python
# Drift threshold (line 110)
if max_psi >= 0.2:  # Change threshold here

# Time windows (lines 60-70)
WHERE updated_at < NOW() - INTERVAL '7 days'  # Reference period
WHERE updated_at >= NOW() - INTERVAL '7 days'  # Current period

# Model parameters (lines 167-173)
segmenter = KMeansSegmenter(n_clusters=5)  # Change cluster count

# Validation threshold (line 309)
improvement_threshold = 0.02  # Require 2% improvement
```

---

## Production Deployment

**Same configuration works in production**:
```bash
# Deploy with production compose
docker compose -f compose.prod.yaml up -d

# Airflow will use same DAG
# MLflow tracking URI: http://mlflow:5000
# PostgreSQL connection: from environment variables
```

**Schedule**:
- Default: Weekly (Sunday 2 AM)
- Modify: Change `schedule_interval='0 2 * * 0'` in DAG

---

## Summary

✅ **Fixed Issues**:
1. Missing imports (mlflow, model classes)
2. Missing dependencies (installed via _PIP_ADDITIONAL_REQUIREMENTS)
3. Missing backend code mount

✅ **Metrics in MLflow**:
- K-Means: silhouette_score, calinski_harabasz_score, inertia
- LightFM: training_interactions, no_components
- XGBoost: objective, learning_rate, max_depth
- Drift: avg_psi, max_psi

✅ **Ready to Use**:
- Weekly automated retraining
- Data drift detection
- Model validation & promotion
- MLflow integration complete

**Next Step**: Test manually via Airflow UI or CLI
