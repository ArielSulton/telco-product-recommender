# Production Quick Start Guide

## Prerequisites

```bash
# Verify Docker installation
docker --version  # Should be 24.0+
docker-compose --version  # Should be 2.20+
```

## 1. Environment Setup (5 minutes)

```bash
# Clone and navigate to project
cd "/path/to/ASAH Capstone"

# Copy environment template
cp .env.example .env

# Generate secrets
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
echo "REDIS_PASSWORD=$(openssl rand -base64 32)" >> .env
echo "AIRFLOW_FERNET_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" >> .env

# Edit .env with your configuration
nano .env
```

**Required Configuration:**
```bash
# Update these values in .env:
DATABASE_PASSWORD=<strong-password>
REDIS_PASSWORD=<generated-above>
SECRET_KEY=<generated-above>
ALLOWED_ORIGINS=https://your-frontend-domain.com
BACKEND_DOMAIN=api.your-domain.com
FRONTEND_DOMAIN=your-domain.com
```

## 2. Build & Deploy (10 minutes)

```bash
# Build production images
docker-compose -f compose.prod.yaml build

# Start all services
docker-compose -f compose.prod.yaml up -d

# Verify services are running
docker-compose -f compose.prod.yaml ps

# Check health
curl http://localhost:8000/health/ready
```

## 3. Validation (5 minutes)

```bash
# Install Python dependencies for testing
pip install httpx asyncio

# Run E2E tests
python scripts/test_e2e_production.py --base-url http://localhost:8000

# Run security audit
python scripts/security_audit.py --target http://localhost:8000
```

## 4. Monitoring Setup (5 minutes)

```bash
# Access Grafana
open http://localhost:3000
# Login: admin / <GRAFANA_ADMIN_PASSWORD from .env>

# Access Prometheus
open http://localhost:9090

# Check metrics endpoint
curl http://localhost:8000/metrics
```

## Quick Commands

### View Logs
```bash
# All services
docker-compose -f compose.prod.yaml logs -f

# Specific service
docker-compose -f compose.prod.yaml logs -f backend

# Last 100 lines
docker-compose -f compose.prod.yaml logs --tail=100 backend
```

### Restart Services
```bash
# Restart backend
docker-compose -f compose.prod.yaml restart backend

# Restart all
docker-compose -f compose.prod.yaml restart
```

### Scale Services
```bash
# Scale backend to 4 replicas
docker-compose -f compose.prod.yaml up -d --scale backend=4
```

### Stop/Start
```bash
# Stop all services
docker-compose -f compose.prod.yaml down

# Start all services
docker-compose -f compose.prod.yaml up -d
```

## Troubleshooting

### Service Won't Start
```bash
# Check logs
docker-compose -f compose.prod.yaml logs <service-name>

# Check configuration
docker-compose -f compose.prod.yaml config

# Recreate service
docker-compose -f compose.prod.yaml up -d --force-recreate <service-name>
```

### Database Connection Issues
```bash
# Check database status
docker-compose -f compose.prod.yaml ps postgres

# Test connection
docker-compose -f compose.prod.yaml exec backend \
  python -c "from app.db.session import check_db_health; import asyncio; print(asyncio.run(check_db_health()))"
```

### High Memory Usage
```bash
# Check resource usage
docker stats --no-stream

# Increase limits in compose.prod.yaml and restart
docker-compose -f compose.prod.yaml up -d --force-recreate
```

## Health Check Endpoints

- **Basic Health**: http://localhost:8000/health
- **Readiness**: http://localhost:8000/health/ready
- **Liveness**: http://localhost:8000/health/live
- **Metrics**: http://localhost:8000/metrics

## Default Ports

- Backend API: 8000
- Frontend: 5173
- PostgreSQL: 5432
- Redis: 6379
- MLflow: 5000
- Prometheus: 9090
- Grafana: 3000
- Airflow: 8080

## Documentation

- **API Documentation**: `docs/API_DOCUMENTATION.md`
- **Deployment Guide**: `docs/DEPLOYMENT_GUIDE.md`
- **Monitoring Runbook**: `docs/MONITORING_RUNBOOK.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING_GUIDE.md`
- **Sprint 5 Summary**: `SPRINT5_COMPLETION.md`

## Support

For issues or questions:
- Check troubleshooting guide
- Review documentation
- Contact: devops@telco-recommender.com
