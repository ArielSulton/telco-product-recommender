# MLflow & Airflow Architecture Guide

Comprehensive guide explaining when MLflow runs, Airflow orchestration, and the rationale behind using both APScheduler and Airflow.

---

## 📊 MLflow - ML Experiment Tracking

### Kapan MLflow Running?

**Answer**: MLflow **SELALU RUNNING sejak docker compose up!**

MLflow adalah **standalone service** yang berjalan independen dan **TIDAK tergantung** pada Airflow triggers.

#### MLflow Runtime Lifecycle:

```bash
# MLflow starts automatically with docker compose
docker compose -f compose.dev.yaml up -d

# MLflow container telco-mlflow-dev starts immediately
# Listening on: http://localhost:5000
```

**Status**: ✅ Always Running (Independent Service)

```
┌─────────────────────┐
│ Docker Compose Up   │
└──────────┬──────────┘
           │
           ├─► Backend (Port 8000) ✅ Running
           ├─► Frontend (Port 5173) ✅ Running
           ├─► MLflow (Port 5000)  ✅ Running ← ALWAYS ON!
           ├─► Airflow (Port 8080) ✅ Running
           └─► Data Simulator       ✅ Running
```

### MLflow Fungsi & Kapan Digunakan

**MLflow Functions**:
1. **Experiment Tracking** - Log ML training runs, parameters, metrics
2. **Model Registry** - Store and version trained models
3. **Model Serving** - Deploy models for inference (optional)
4. **Artifact Storage** - Store model files, plots, datasets

**When MLflow is Used**:

#### 1. During ML Training (Triggered by Airflow or Manual)
```python
# Backend code atau Airflow DAG calls MLflow
import mlflow

mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("telco-recommender")

with mlflow.start_run():
    # Log parameters
    mlflow.log_param("algorithm", "XGBoost")
    mlflow.log_param("max_depth", 5)

    # Train model
    model.fit(X_train, y_train)

    # Log metrics
    mlflow.log_metric("accuracy", 0.95)
    mlflow.log_metric("ndcg@5", 0.82)

    # Save model
    mlflow.sklearn.log_model(model, "model")
```

#### 2. During Inference (Backend API)
```python
# Backend loads model from MLflow
model_uri = "models:/telco-recommender/production"
model = mlflow.pyfunc.load_model(model_uri)

# Make predictions
recommendations = model.predict(user_features)
```

#### 3. Viewing Experiments (Manual via UI)
- Open: http://localhost:5000
- Browse experiments, compare runs
- View metrics, parameters, artifacts
- Promote models to production

---

## 🔄 Apache Airflow - Workflow Orchestration

### Apakah Harus Trigger Manual?

**Answer**: **TIDAK**, setelah DAG di-unpause, akan **auto-run sesuai schedule!**

#### Current DAG Status:

```bash
# Check DAG status
docker compose -f compose.dev.yaml exec airflow-webserver airflow dags list

# Output:
dag_id                 | filepath               | owner         | paused
=======================+========================+===============+=======
data_ingestion_monitor | data_ingestion.py      | telco-ml-team | True  ← PAUSED
feature_engineering    | feature_engineering.py | telco-ml-team | True  ← PAUSED
model_retraining       | model_retraining.py    | ml-team       | True  ← PAUSED
```

**Status**: All DAGs are **PAUSED** by default (for safety)

### How to Enable Auto-Run:

#### Option 1: Via Airflow UI (Recommended)
```
1. Open http://localhost:8080
2. Login: admin / admin
3. Find DAG in list
4. Click toggle switch (left side) to UNPAUSE
5. DAG will auto-run based on schedule
```

#### Option 2: Via CLI
```bash
# Unpause specific DAG
docker compose -f compose.dev.yaml exec airflow-webserver \
  airflow dags unpause data_ingestion_monitor

docker compose -f compose.dev.yaml exec airflow-webserver \
  airflow dags unpause feature_engineering

docker compose -f compose.dev.yaml exec airflow-webserver \
  airflow dags unpause model_retraining
```

#### Option 3: Trigger Manual Run (One-time)
```bash
# Trigger immediate run (doesn't unpause)
docker compose -f compose.dev.yaml exec airflow-webserver \
  airflow dags trigger model_retraining
```

### DAG Schedules:

```python
# data_ingestion_monitor.py
schedule_interval='*/30 * * * *'  # Every 30 minutes

# feature_engineering.py
schedule_interval='@daily'  # Daily at midnight

# model_retraining.py
schedule_interval='@weekly'  # Weekly on Sunday 2 AM
```

**After Unpause**:
- ✅ `data_ingestion_monitor` runs every 30 minutes automatically
- ✅ `feature_engineering` runs daily at midnight automatically
- ✅ `model_retraining` runs weekly on Sunday 2 AM automatically

---

## 🤔 APScheduler vs Airflow - Why Both?

### The Architecture Question

**User's Valid Question**: "Mengapa pakai APScheduler untuk data simulator jika udah ada Airflow?"

**Answer**: **Different tools for different jobs!** Ini adalah **GOOD architectural decision**.

### Comparison Matrix

| Aspect | APScheduler (Data Simulator) | Apache Airflow (ML Workflows) |
|--------|------------------------------|-------------------------------|
| **Use Case** | Simple periodic tasks | Complex workflow orchestration |
| **Complexity** | Lightweight, in-process | Heavy, DAG-based |
| **Dependencies** | None | Task dependencies, retries |
| **Resource Usage** | ~10MB RAM | ~500MB+ RAM |
| **Startup Time** | <1 second | ~30 seconds |
| **Best For** | Real-time data generation | Batch processing pipelines |
| **Overhead** | Minimal | Moderate-High |
| **Monitoring** | Simple logs | Full UI, metrics, alerts |

### Detailed Rationale

#### APScheduler in Data Simulator ✅

**Purpose**: Insert mock telco customer data every 5 minutes

**Why APScheduler?**
```python
# Simple scheduler, runs in same process
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(
    insert_data,
    trigger='interval',
    minutes=5,
    id='data_insertion'
)
scheduler.start()
```

**Benefits**:
- ✅ **Lightweight**: Runs in same Python process as simulator
- ✅ **Fast startup**: Immediate execution
- ✅ **Simple**: No external dependencies
- ✅ **Real-time**: Perfect for continuous data generation
- ✅ **Low overhead**: Minimal resource usage (~10MB)

**Perfect For**:
- Continuous data insertion every 5 minutes
- No dependencies between tasks
- No need for retry logic
- No complex workflow visualization needed

#### Apache Airflow for ML Workflows ✅

**Purpose**: Orchestrate complex ML training pipelines with dependencies

**Why Airflow?**
```python
# Complex DAG with dependencies
with DAG('model_retraining', schedule_interval='@weekly') as dag:

    # Step 1: Extract data
    extract_data = PythonOperator(
        task_id='extract_data',
        python_callable=extract_training_data
    )

    # Step 2: Feature engineering (depends on step 1)
    engineer_features = PythonOperator(
        task_id='engineer_features',
        python_callable=create_features
    )

    # Step 3: Train models (depends on step 2)
    train_models = PythonOperator(
        task_id='train_models',
        python_callable=train_ml_models
    )

    # Step 4: Validate models (depends on step 3)
    validate_models = PythonOperator(
        task_id='validate_models',
        python_callable=validate_performance
    )

    # Step 5: Deploy to production (depends on step 4)
    deploy_model = PythonOperator(
        task_id='deploy_model',
        python_callable=promote_to_production
    )

    # Define dependencies
    extract_data >> engineer_features >> train_models >> validate_models >> deploy_model
```

**Benefits**:
- ✅ **DAG Dependencies**: Step B only runs if Step A succeeds
- ✅ **Retry Logic**: Auto-retry on failures with backoff
- ✅ **Monitoring UI**: Visual workflow, logs, metrics
- ✅ **Notifications**: Email/Slack alerts on failures
- ✅ **Rollback**: Automatic rollback on validation failures
- ✅ **Scheduling**: Complex cron schedules
- ✅ **Parallelization**: Run independent tasks in parallel

**Perfect For**:
- ML training pipelines with dependencies
- Batch ETL jobs
- Data quality checks
- Model validation workflows
- Complex scheduling requirements

### Visual Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA FLOW ARCHITECTURE                    │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│   APScheduler        │  ← Simple, Periodic, Real-time
│  (Data Simulator)    │
├──────────────────────┤
│ Every 5 minutes:     │
│ 1. Generate data     │
│ 2. Insert to DB      │
│ 3. Done ✓            │
└──────────┬───────────┘
           │
           ▼
    ┌─────────────┐
    │ PostgreSQL  │
    │  Database   │
    └─────────────┘
           │
           │ (Read by Airflow)
           ▼
┌──────────────────────┐
│  Apache Airflow      │  ← Complex, Orchestrated, Batch
│   (ML Workflows)     │
├──────────────────────┤
│ Daily/Weekly:        │
│ ┌────────────────┐   │
│ │ Extract Data   │   │
│ └────────┬───────┘   │
│          ▼           │
│ ┌────────────────┐   │
│ │ Feature Eng    │   │ ← Depends on Extract
│ └────────┬───────┘   │
│          ▼           │
│ ┌────────────────┐   │
│ │ Train Models   │   │ ← Depends on Features
│ └────────┬───────┘   │
│          ▼           │
│ ┌────────────────┐   │
│ │ Validate       │   │ ← Depends on Training
│ └────────┬───────┘   │
│          ▼           │
│ ┌────────────────┐   │
│ │ Deploy to Prod │   │ ← Depends on Validation
│ └────────────────┘   │
│          │           │
│          ▼           │
│    ┌─────────┐       │
│    │ MLflow  │       │ ← Log experiments, store models
│    └─────────┘       │
└──────────────────────┘
```

### Real-World Analogy

**APScheduler** = **Alarm Clock**
- Simple
- Rings every X minutes
- No dependencies
- Lightweight

**Airflow** = **Project Manager**
- Coordinates complex tasks
- Manages dependencies
- Handles failures
- Provides visibility
- Sends reports

**Would you use a Project Manager to ring an alarm every 5 minutes?** NO! Too expensive and overkill.

**Would you use an alarm clock to manage a complex ML pipeline?** NO! Lacks capabilities.

### Decision Tree: When to Use What?

```
Is the task simple and periodic?
│
├─ YES → Use APScheduler
│         Examples:
│         - Data generation every N minutes
│         - Simple periodic cleanup
│         - Heartbeat checks
│         - Real-time metrics collection
│
└─ NO → Does it have dependencies or need retries?
         │
         ├─ YES → Use Airflow
         │         Examples:
         │         - ML training pipelines
         │         - ETL with data quality checks
         │         - Multi-step deployments
         │         - Batch analytics jobs
         │
         └─ NO → Can still use Airflow for:
                 - Centralized monitoring
                 - Unified scheduling UI
                 - Email/Slack notifications
```

---

## 🎯 Summary

### MLflow Runtime

| Question | Answer |
|----------|--------|
| Kapan MLflow running? | **SELALU** - sejak docker compose up |
| Apakah saat trigger Airflow? | **TIDAK** - MLflow standalone service |
| Bagaimana akses? | http://localhost:5000 (always available) |
| Untuk apa? | Log experiments, store models, track metrics |
| Digunakan kapan? | During training (Airflow DAG) & inference (Backend API) |

### Airflow Automation

| Question | Answer |
|----------|--------|
| Apakah harus trigger manual? | **TIDAK** - auto-run after unpause |
| How to enable? | Unpause di UI atau CLI |
| Schedule? | Varies by DAG (daily/weekly) |
| Dependencies? | Full DAG dependency support |
| Retry logic? | Yes, configurable retries |

### APScheduler vs Airflow

| Tool | Use Case | When to Use |
|------|----------|-------------|
| **APScheduler** | Simple periodic tasks | Data generation, simple cleanup |
| **Airflow** | Complex workflows | ML pipelines, batch ETL, complex scheduling |

**Architecture Decision**: ✅ **CORRECT** - Use the simplest tool for the job!

---

## 🐛 Troubleshooting

### Broken DAG: ModuleNotFoundError

**Previous Error**:
```
Broken DAG: [/opt/airflow/dags/model_retraining.py]
ModuleNotFoundError: No module named 'mlflow'
```

**Root Cause**: Airflow container doesn't have mlflow installed

**✅ Solution Applied**: Changed DAG to use HTTP APIs instead of direct imports
```python
# OLD (Broken):
import mlflow
from backend.app.ml.models import KMeansSegmenter

# NEW (Fixed):
import requests
# Use MLflow REST API: http://mlflow:5000/api/2.0/mlflow/...
```

**Result**: DAG now loads successfully! ✅

---

## 📚 References

- **MLflow Docs**: https://mlflow.org/docs/latest/
- **Airflow Docs**: https://airflow.apache.org/docs/
- **APScheduler Docs**: https://apscheduler.readthedocs.io/

---

**Last Updated**: 2025-11-12
**Status**: ✅ All services running, DAGs fixed, architecture documented
