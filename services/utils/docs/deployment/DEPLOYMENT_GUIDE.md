# Complete Deployment Guide - PAKETIFY

**Project**: Telco Recommendation System
**Environment**: Development (localhost) & Production (Dokploy VPS)
**Status**: ✅ Ready to Deploy

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Deployment](#development-deployment)
3. [Production Deployment](#production-deployment)
4. [Post-Deployment Validation](#post-deployment-validation)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

**Development:**
- Docker Desktop 24.0+
- Docker Compose v2.20+
- Node.js 18+ (for local frontend dev)
- Git

**Production:**
- Dokploy VPS (with Docker pre-installed)
- Domain name with DNS access
- SSL certificate (Dokploy's Traefik handles this automatically)

### Required Environment Variables

Create `.env` file in project root:

```bash
# Database
DATABASE_USER=postgres
DATABASE_PASSWORD=<strong-password>
DATABASE_NAME=telco_recommender

# Redis
REDIS_PASSWORD=<strong-password>

# Backend API
SECRET_KEY=<generated-secret-key>
ALLOWED_ORIGINS=http://localhost:5173

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000

# Airflow
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=<strong-password>
AIRFLOW_ADMIN_EMAIL=admin@example.com
AIRFLOW_FERNET_KEY=<generated-fernet-key>
AIRFLOW_SECRET_KEY=<generated-secret>

# Monitoring
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<strong-password>
```

**Generate Secrets:**
```bash
# Secret key (32 bytes)
python3 -c "import secrets; print(secrets.token_hex(32))"

# Fernet key for Airflow
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Development Deployment

### Step 1: Clone and Setup

```bash
# Clone repository
cd "~/Documents/Stargazing Project/VScode Project/dicoding/ASAH Capstone"

# Create .env file
cp .env.example .env
# Edit .env with your values

# Verify Docker is running
docker --version
docker compose version
```

### Step 2: Start Infrastructure Services

```bash
# Start core services
docker compose -f compose.dev.yaml up -d postgres redis mlflow

# Wait for health checks (30 seconds)
docker compose -f compose.dev.yaml ps

# Expected output:
# telco-postgres-dev   healthy
# telco-redis-dev      healthy
# telco-mlflow-dev     healthy
```

### Step 3: Initialize Airflow

```bash
# Start Airflow initialization
docker compose -f compose.dev.yaml up -d airflow-init

# Wait for completion (~2 minutes)
docker logs telco-airflow-init-dev --follow

# Start Airflow services
docker compose -f compose.dev.yaml up -d airflow-webserver airflow-scheduler

# Verify Airflow
docker logs telco-airflow-webserver-dev --tail 50
```

### Step 4: Train Demo ML Model

```bash
# Run training script
python3 scripts/train_demo_model.py

# Expected output:
# ✅ Model promoted to Production stage (version 1)
# Top 5 popular products: ['PROD_DATA_001', 'PROD_DEVICE_001', ...]

# Verify in MLflow UI
open http://localhost:5000
# Check: Experiment "telco-recommender-demo"
# Model: "baseline-recommender" → Stage: "Production"
```

### Step 5: Start Application Services

```bash
# Start backend API
docker compose -f compose.dev.yaml up -d backend

# Start data simulator
docker compose -f compose.dev.yaml up -d data-simulator

# Start frontend (local dev server)
cd frontend
npm install
npm run dev

# Frontend will be available at http://localhost:5173
```

### Step 6: Start Monitoring (Optional)

```bash
# Start Prometheus and Grafana
docker compose -f compose.dev.yaml up -d prometheus grafana

# Access monitoring:
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

### Development URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:5173 | N/A |
| Backend API | http://localhost:8000 | N/A |
| API Docs | http://localhost:8000/api/v1/docs | N/A |
| MLflow | http://localhost:5000 | N/A |
| Airflow | http://localhost:8080 | admin/admin |
| Grafana | http://localhost:3000 | admin/admin |
| Prometheus | http://localhost:9090 | N/A |

---

## Production Deployment

### Step 1: Prepare Production Environment

```bash
# Create .env.production
cat > .env.production <<EOF
# Production Configuration
DATABASE_USER=postgres
DATABASE_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
DATABASE_NAME=telco_recommender

REDIS_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ALLOWED_ORIGINS=https://your-domain.com

# Domains (replace with your actual domains)
BACKEND_DOMAIN=api.your-domain.com
FRONTEND_DOMAIN=your-domain.com
MONITORING_DOMAIN=monitoring.your-domain.com

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000

# Airflow
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
AIRFLOW_ADMIN_EMAIL=admin@your-domain.com
AIRFLOW_FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
AIRFLOW_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
GRAFANA_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Build metadata
VERSION=1.0.0
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VCS_REF=$(git rev-parse --short HEAD)
EOF
```

### Step 2: DNS Configuration

Point your domains to your VPS IP:

```
# A Records
api.your-domain.com       → <VPS-IP>
your-domain.com           → <VPS-IP>
monitoring.your-domain.com → <VPS-IP>
```

### Step 3: Deploy with Dokploy

**Via Dokploy UI:**

1. Create new application in Dokploy
2. Connect to Git repository
3. Set environment variables from `.env.production`
4. Select `compose.prod.yaml` as deployment file
5. Enable Traefik integration (for SSL/TLS)
6. Deploy

**Via Git Push (if configured):**

```bash
# Push to production branch
git checkout main
git push production main

# Dokploy auto-deploys on push
```

### Step 4: Initialize Production Database

```bash
# SSH into VPS
ssh user@your-vps-ip

# Navigate to project directory
cd /path/to/project

# Run migrations (if using Alembic)
docker exec telco-backend-prod alembic upgrade head

# Populate initial data
docker exec telco-backend-prod python scripts/seed_data.py
```

### Step 5: Train Production ML Models

```bash
# SSH into VPS
ssh user@your-vps-ip

# Run training script
docker exec telco-backend-prod python scripts/train_demo_model.py

# Or trigger via Airflow
docker exec telco-airflow-scheduler-prod airflow dags trigger model_retraining
```

### Step 6: SSL/TLS Verification

Dokploy's Traefik automatically handles SSL with Let's Encrypt.

Verify HTTPS:
```bash
curl -I https://api.your-domain.com/health
curl -I https://your-domain.com
curl -I https://monitoring.your-domain.com
```

All should return `200 OK` with valid SSL certificate.

---

## Post-Deployment Validation

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health
# Expected: {"status": "healthy"}

# Database connection
curl http://localhost:8000/health/ready
# Expected: {"status": "ready", "database": "connected", ...}

# MLflow
curl http://localhost:5000/health
# Expected: {"status": "ok"}
```

### Functional Testing

**1. Test Recommendation API:**
```bash
curl -X POST http://localhost:8000/api/v1/recommend \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "limit": 5
  }'
```

**2. Test Event Tracking:**
```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "product_id": "PROD_001",
    "event_type": "view"
  }'
```

**3. Test Frontend:**
- Open http://localhost:5173 (dev) or https://your-domain.com (prod)
- Navigate through pages: Home → Products → Login → Dashboard
- Verify recommendations load
- Check event tracking in network tab

### Performance Validation

**Backend API:**
```bash
# Load test with Apache Bench
ab -n 1000 -c 10 http://localhost:8000/health

# Expected: <200ms response time
```

**MLflow Query:**
```bash
curl http://localhost:5000/api/2.0/mlflow/registered-models/list
```

**Airflow DAG:**
- Open http://localhost:8080
- Verify `model_retraining` DAG is active
- Trigger manually and check logs

---

## Troubleshooting

### Issue 1: Backend Won't Start

**Symptoms:**
```
Error: Could not connect to database
```

**Solution:**
```bash
# Check PostgreSQL is healthy
docker compose -f compose.dev.yaml ps postgres

# Restart PostgreSQL if needed
docker compose -f compose.dev.yaml restart postgres

# Check logs
docker logs telco-postgres-dev --tail 50
```

### Issue 2: ML Models Not Loading

**Symptoms:**
```
Recommendation service not initialized
```

**Solution:**
```bash
# Verify MLflow has models
curl http://localhost:5000/api/2.0/mlflow/registered-models/list

# If empty, train model
python3 scripts/train_demo_model.py

# Restart backend
docker compose -f compose.dev.yaml restart backend
```

### Issue 3: Airflow DAG Import Errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'mlflow'
```

**Solution:**
```bash
# Recreate Airflow containers (installs dependencies)
docker compose -f compose.dev.yaml down airflow-webserver airflow-scheduler
docker compose -f compose.dev.yaml up -d airflow-init airflow-webserver airflow-scheduler

# Check logs
docker logs telco-airflow-scheduler-dev --follow
```

### Issue 4: Frontend Can't Connect to Backend

**Symptoms:**
```
Network Error: Failed to fetch
```

**Solution:**
```bash
# Check CORS settings in backend
# .env should have:
ALLOWED_ORIGINS=http://localhost:5173

# Restart backend
docker compose -f compose.dev.yaml restart backend

# Verify backend is accessible
curl http://localhost:8000/health
```

### Issue 5: Production SSL Not Working

**Symptoms:**
```
Certificate error or HTTP instead of HTTPS
```

**Solution:**
```bash
# Check Traefik labels in compose.prod.yaml
# Verify DNS points to correct IP
# Check Dokploy Traefik configuration
# Let's Encrypt may take 1-2 minutes to provision cert
```

---

## Maintenance Commands

### Backup Database

```bash
# Development
docker exec telco-postgres-dev pg_dump -U postgres telco_recommender > backup.sql

# Production
docker exec telco-postgres-prod pg_dump -U postgres telco_recommender > backup_$(date +%Y%m%d).sql
```

### View Logs

```bash
# Backend logs
docker logs telco-backend-dev --tail 100 --follow

# Airflow logs
docker logs telco-airflow-scheduler-dev --tail 100 --follow

# All services
docker compose -f compose.dev.yaml logs --tail 50 --follow
```

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild services
docker compose -f compose.dev.yaml up -d --build backend frontend

# Or for production
docker compose -f compose.prod.yaml up -d --build backend frontend
```

### Clean Up

```bash
# Stop all services
docker compose -f compose.dev.yaml down

# Remove volumes (WARNING: deletes data)
docker compose -f compose.dev.yaml down -v

# Clean Docker resources
docker system prune -a
```

---

## Quick Reference

### Start Everything (Dev)

```bash
# One command to start all services
docker compose -f compose.dev.yaml up -d

# Then open:
# Frontend: http://localhost:5173
# Backend: http://localhost:8000
# MLflow: http://localhost:5000
# Airflow: http://localhost:8080
```

### Stop Everything

```bash
docker compose -f compose.dev.yaml down
```

### Check Status

```bash
docker compose -f compose.dev.yaml ps
```

### Restart Single Service

```bash
docker compose -f compose.dev.yaml restart backend
```

---

## Success Criteria

### Development Ready ✅
- [ ] All Docker containers healthy
- [ ] Backend API responding
- [ ] ML model loaded in MLflow
- [ ] Frontend loads at localhost:5173
- [ ] Recommendations API working
- [ ] Event tracking functional

### Production Ready ✅
- [ ] DNS configured correctly
- [ ] SSL/TLS certificates valid
- [ ] All services healthy
- [ ] Monitoring dashboards accessible
- [ ] ML models trained and registered
- [ ] Airflow DAG scheduled and working
- [ ] Load balancing configured
- [ ] Backups automated

---

## Support

**Documentation:**
- `/docs/deployment/` - Deployment guides
- `/docs/architecture/` - System architecture
- `/README.md` - Project overview

**Logs Location:**
- Development: `docker logs <container-name>`
- Production: `/var/lib/docker/volumes/` (managed by Dokploy)

**Common Issues:**
- See Troubleshooting section above
- Check `/docs/deployment/AIRFLOW_TRAINING_GUIDE.md` for Airflow-specific issues

---

**Last Updated**: 2025-01-16
**Version**: 1.0.0
**Maintainer**: Team A25-CS007
