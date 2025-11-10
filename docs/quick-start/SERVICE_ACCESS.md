# Service Access Guide - Telco Product Recommender

Panduan lengkap untuk mengakses semua layanan sistem rekomendasi.

---

## 📋 Service URLs

### ✅ Frontend
**URL**: http://localhost:5173

**Status**: Accessible
**Login Credentials**:
- Demo User: `08123456789` / `user123`
- Admin User: `admin` / `admin123`
- Test User: `08111111111` / `demo`

---

### ✅ Backend API

**⚠️ PENTING**: Dokumentasi API bukan di `/docs`, tapi di `/api/v1/docs`

**URLs**:
- **API Docs (Swagger)**: http://localhost:8000/api/v1/docs
- **API Docs (ReDoc)**: http://localhost:8000/api/v1/redoc
- **OpenAPI Schema**: http://localhost:8000/api/v1/openapi.json
- **Health Check**: http://localhost:8000/health
- **Metrics (Prometheus)**: http://localhost:8000/metrics

**Why `/api/v1/`?**
Backend menggunakan API versioning best practice. Semua endpoint berada di bawah `/api/v1/`:
- `/api/v1/recommendations` - Recommendation endpoints
- `/api/v1/events` - Event tracking
- `/api/v1/webhooks` - Webhook handlers
- `/api/v1/docs` - API documentation

---

### ✅ MLflow

**URL**: http://localhost:5000

**Status**: Accessible
**Purpose**: ML experiment tracking, model registry, model versioning

**Features**:
- View ML experiments and runs
- Compare model performance metrics
- Access model artifacts
- Track hyperparameters
- View training plots and logs

---

### ✅ Apache Airflow

**URL**: http://localhost:8080

**Status**: Accessible
**Credentials**: `admin` / `admin`

**⚠️ DAGs Status**: Currently PAUSED

#### Available DAGs:
1. **data_ingestion_monitor** - Monitoring data ingestion dari simulator
2. **feature_engineering** - Feature engineering pipeline untuk ML
3. **model_retraining** - Automated model retraining pipeline

#### Enable DAGs:
```bash
# Via Airflow UI
1. Login ke http://localhost:8080
2. Klik toggle di sebelah kiri nama DAG untuk UNPAUSE
3. DAG akan otomatis run sesuai schedule

# Via CLI
docker compose -f compose.dev.yaml exec airflow-webserver \
  airflow dags unpause data_ingestion_monitor

docker compose -f compose.dev.yaml exec airflow-webserver \
  airflow dags unpause feature_engineering

docker compose -f compose.dev.yaml exec airflow-webserver \
  airflow dags unpause model_retraining
```

#### Trigger Manual Run:
```bash
# Via UI: Klik tombol "Play" di sebelah kanan nama DAG

# Via CLI
docker compose -f compose.dev.yaml exec airflow-webserver \
  airflow dags trigger data_ingestion_monitor
```

---

### 🤔 Airflow vs APScheduler - Architecture Rationale

**Q: Mengapa pakai APScheduler untuk data simulator jika sudah ada Airflow?**

**A: Different tools for different jobs!**

#### APScheduler (Data Simulator)
✅ **Use Case**: Simple periodic tasks
✅ **Benefit**: Lightweight, in-process, low overhead
✅ **Perfect for**: Real-time data generation every 5 minutes

**Why?**
- Data simulator perlu insert data REAL-TIME setiap 5 menit
- Tidak perlu dependency management atau retries kompleks
- Minimal resource usage
- Fast startup, immediate execution

#### Apache Airflow (ML Workflows)
✅ **Use Case**: Complex workflow orchestration
✅ **Benefit**: DAG dependencies, retries, monitoring, scheduling
✅ **Perfect for**: ML training, batch ETL, complex pipelines

**Why?**
- Feature engineering has dependencies (need raw data first)
- Model training needs retry logic if fails
- Need workflow visualization and monitoring
- Batch processing with complex dependencies

#### Architecture Decision:
```
┌─────────────────────┐
│ APScheduler         │ → Simple, periodic, real-time data insertion
│ (Data Simulator)    │   Every 5 minutes, no dependencies
└─────────────────────┘

┌─────────────────────┐
│ Apache Airflow      │ → Complex orchestration with dependencies
│ (ML Workflows)      │   Daily/hourly batch jobs, retry logic
├─────────────────────┤
│ ┌─────────────────┐ │
│ │ Data Ingestion  │ │ ← Monitor simulator data
│ └────────┬────────┘ │
│          ↓          │
│ ┌─────────────────┐ │
│ │ Feature Eng     │ │ ← Transform raw data
│ └────────┬────────┘ │
│          ↓          │
│ ┌─────────────────┐ │
│ │ Model Training  │ │ ← Train/retrain models
│ └─────────────────┘ │
└─────────────────────┘
```

**Best Practice**: Use the simplest tool that solves the problem!

---

### ✅ Grafana Dashboards

**URL**: http://localhost:3000

**Status**: Accessible (dashboards now available)
**Credentials**: `admin` / `admin`

**Available Dashboards**:
1. **Recommender System** - Overall system metrics
2. **API Performance** - Backend API latency, throughput, errors
3. **ML Models** - Model performance and predictions

**Access Dashboards**:
1. Login: http://localhost:3000
2. Navigate: Dashboards → Browse
3. Select: "Telco Recommender Dashboards" folder

**Fix Applied**: Dashboard provisioning path corrected, restart Grafana to apply.

---

### ✅ Prometheus

**URL**: http://localhost:9090

**Status**: Accessible
**Purpose**: Metrics collection and alerting

**Useful Queries**:
```promql
# API request rate
rate(http_requests_total[5m])

# API latency P95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Model prediction latency
histogram_quantile(0.95, rate(ml_model_prediction_duration_seconds_bucket[5m]))
```

---

## 🗄️ PostgreSQL Access

### Development Environment

**Connection Details**:
- Host: `localhost`
- Port: `5434` (external) / `5432` (internal Docker)
- Username: `postgres`
- Password: `postgres123`
- Databases:
  - `telco_recommender` (main application)
  - `airflow` (Airflow metadata)

#### Access Methods:

##### 1. psql CLI (from host)
```bash
psql -h localhost -p 5434 -U postgres -d telco_recommender
# Password: postgres123
```

##### 2. Docker exec (inside container)
```bash
docker exec -it telco-postgres-dev psql -U postgres -d telco_recommender
```

##### 3. pgAdmin / DBeaver (GUI)
```
Host: localhost
Port: 5434
Database: telco_recommender
Username: postgres
Password: postgres123
```

##### 4. Python/Application
```python
# Connection string from .env
DATABASE_URL=postgresql+asyncpg://postgres:postgres123@localhost:5434/telco_recommender
```

#### Common Queries:
```sql
-- List all tables
\dt

-- Show users table structure
\d users

-- Count records
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM events;

-- Recent recommendations
SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 10;
```

---

### Production Environment (Dokploy)

**Connection Details**:
- Host: `postgres` (Docker internal service name)
- Port: `5432` (internal only)
- Username: From `DATABASE_USER` in `.env.prod`
- Password: From `DATABASE_PASSWORD` in `.env.prod`

**Important**:
- Applications connect via **internal Docker network** (host: `postgres`)
- External access should use **SSH tunnel** for security:

```bash
# SSH tunnel for secure external access
ssh -L 5432:postgres:5432 user@your-server.com

# Then connect via localhost:5432
psql -h localhost -p 5432 -U your_db_user -d telco_recommender
```

**Best Practice**:
- ✅ Internal apps connect to `postgres:5432` (fast, secure)
- ⚠️ External tools use SSH tunnel (secure)
- ❌ Never expose PostgreSQL port directly to internet

---

## 🔧 Service Management

### Check All Services
```bash
docker compose -f compose.dev.yaml ps
```

### View Logs
```bash
# All services
docker compose -f compose.dev.yaml logs -f

# Specific service
docker compose -f compose.dev.yaml logs -f backend
docker compose -f compose.dev.yaml logs -f frontend
docker compose -f compose.dev.yaml logs -f data-simulator
```

### Restart Service
```bash
docker compose -f compose.dev.yaml restart backend
docker compose -f compose.dev.yaml restart grafana
```

### Stop All Services
```bash
docker compose -f compose.dev.yaml down
```

### Start All Services
```bash
docker compose -f compose.dev.yaml up -d
```

---

## 📊 Health Checks

### Quick Status Check
```bash
# Backend health
curl http://localhost:8000/health

# Frontend
curl -I http://localhost:5173

# MLflow
curl -I http://localhost:5000

# Prometheus
curl -I http://localhost:9090/-/healthy

# PostgreSQL
docker compose -f compose.dev.yaml exec postgres pg_isready -U postgres
```

---

## 🐛 Troubleshooting

### Backend API Not Accessible
```bash
# Check if running
docker compose -f compose.dev.yaml ps backend

# Check logs for errors
docker compose -f compose.dev.yaml logs backend --tail=50

# Verify correct URL (use /api/v1/docs not /docs)
curl http://localhost:8000/api/v1/docs
```

### Grafana Dashboards Not Showing
```bash
# Restart Grafana to reload provisioning
docker compose -f compose.dev.yaml restart grafana

# Check dashboard files exist
ls -la infrastructure/monitoring/grafana/dashboards/

# Verify provisioning config
cat infrastructure/monitoring/grafana/provisioning/dashboards/dashboard-provider.yml
```

### Airflow DAGs Not Running
```bash
# Check DAG status
docker compose -f compose.dev.yaml exec airflow-webserver airflow dags list

# Unpause DAG
docker compose -f compose.dev.yaml exec airflow-webserver \
  airflow dags unpause <dag_id>

# Check logs
docker compose -f compose.dev.yaml logs airflow-scheduler --tail=50
```

### PostgreSQL Connection Failed
```bash
# Test connection
psql -h localhost -p 5434 -U postgres -d telco_recommender

# Check if PostgreSQL is healthy
docker compose -f compose.dev.yaml ps postgres

# View PostgreSQL logs
docker compose -f compose.dev.yaml logs postgres --tail=50
```

---

## 📝 Summary

| Service | URL | Status | Notes |
|---------|-----|--------|-------|
| Frontend | http://localhost:5173 | ✅ | Login: 08123456789/user123 |
| Backend API Docs | http://localhost:8000/api/v1/docs | ✅ | Use /api/v1/ prefix |
| MLflow | http://localhost:5000 | ✅ | Experiment tracking |
| Airflow | http://localhost:8080 | ✅ | admin/admin, DAGs paused |
| Grafana | http://localhost:3000 | ✅ | admin/admin, dashboards fixed |
| Prometheus | http://localhost:9090 | ✅ | Metrics collection |
| PostgreSQL | localhost:5434 | ✅ | postgres/postgres123 |
| Redis | localhost:6379 | ✅ | No password |

**⚠️ Key Points**:
- Backend docs at `/api/v1/docs` NOT `/docs`
- Airflow DAGs are paused by default - unpause to enable
- APScheduler for simple periodic tasks, Airflow for complex workflows
- PostgreSQL port 5434 for host access, 5432 internal
