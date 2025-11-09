# Deployment Guide - Telco Product Recommender

## Overview

This guide covers deploying the Telco Product Recommender system to production environments. The system uses Docker containers orchestrated with Docker Compose for consistency across environments.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Production Deployment](#production-deployment)
4. [Health Checks](#health-checks)
5. [Scaling](#scaling)
6. [Rollback Procedures](#rollback-procedures)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum Production Server:**
- CPU: 8 cores
- RAM: 16 GB
- Storage: 100 GB SSD
- OS: Ubuntu 20.04 LTS or later

**Recommended Production Server:**
- CPU: 16 cores
- RAM: 32 GB
- Storage: 250 GB SSD
- OS: Ubuntu 22.04 LTS

### Software Requirements

```bash
# Docker
Docker Engine: 24.0+
Docker Compose: 2.20+

# System packages
curl, wget, git, openssl
```

### Installation

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

---

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/telco-recommender.git
cd telco-recommender
```

### 2. Configure Environment Variables

Create production `.env` file:

```bash
cp .env.example .env
nano .env
```

**Required Production Variables:**

```bash
# Environment
ENVIRONMENT=production
VERSION=1.0.0

# Database
DATABASE_USER=telco_prod_user
DATABASE_PASSWORD=<strong-random-password>
DATABASE_NAME=telco_recommender
DATABASE_HOST=postgres
DATABASE_PORT=5432

# Redis
REDIS_PASSWORD=<strong-random-password>
REDIS_HOST=redis
REDIS_PORT=6379

# Security
SECRET_KEY=<generate-with-openssl-rand-hex-32>
ALLOWED_ORIGINS=https://app.telco-recommender.com,https://admin.telco-recommender.com

# API Configuration
API_WORKERS=4
API_RELOAD=false
LOG_LEVEL=INFO
LOG_FORMAT=json

# Monitoring
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<strong-random-password>
GRAFANA_SECRET_KEY=<generate-random>

# Airflow
AIRFLOW_FERNET_KEY=<generate-with-python-cryptography>
AIRFLOW_SECRET_KEY=<generate-random>
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=<strong-random-password>
AIRFLOW_ADMIN_EMAIL=admin@telco-recommender.com

# Domains
BACKEND_DOMAIN=api.telco-recommender.com
FRONTEND_DOMAIN=app.telco-recommender.com
MONITORING_DOMAIN=monitoring.telco-recommender.com
```

### 3. Generate Secrets

```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate AIRFLOW_FERNET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate random passwords
openssl rand -base64 32
```

### 4. Set File Permissions

```bash
chmod 600 .env
chmod 755 infrastructure/postgres/init/*.sql
```

---

## Production Deployment

### Initial Deployment

**1. Build Images**

```bash
# Build all services
docker-compose -f compose.prod.yaml build

# Verify images
docker images | grep telco
```

**2. Initialize Database**

```bash
# Start database first
docker-compose -f compose.prod.yaml up -d postgres

# Wait for database to be ready
docker-compose -f compose.prod.yaml exec postgres pg_isready -U ${DATABASE_USER}

# Run migrations (if applicable)
docker-compose -f compose.prod.yaml exec backend alembic upgrade head
```

**3. Start All Services**

```bash
# Start all services
docker-compose -f compose.prod.yaml up -d

# Check service status
docker-compose -f compose.prod.yaml ps

# View logs
docker-compose -f compose.prod.yaml logs -f backend
```

**4. Verify Deployment**

```bash
# Health checks
curl http://localhost:8000/health
curl http://localhost:8000/health/ready

# Check all services
docker-compose -f compose.prod.yaml ps
```

### Update Deployment

**Zero-Downtime Update Strategy:**

```bash
# 1. Pull latest code
git pull origin main

# 2. Build new images with version tag
export VERSION=1.0.1
docker-compose -f compose.prod.yaml build

# 3. Update services one at a time
docker-compose -f compose.prod.yaml up -d --no-deps --scale backend=2 backend

# 4. Wait for health checks to pass
sleep 30

# 5. Remove old containers
docker-compose -f compose.prod.yaml up -d --no-deps --scale backend=2 backend

# 6. Update other services
docker-compose -f compose.prod.yaml up -d --no-deps frontend
docker-compose -f compose.prod.yaml up -d --no-deps mlflow
```

---

## Health Checks

### Automated Health Checks

All services include Docker health checks:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Manual Health Verification

```bash
# Backend API
curl -f http://localhost:8000/health/ready || echo "Backend unhealthy"

# Database
docker-compose -f compose.prod.yaml exec postgres pg_isready -U ${DATABASE_USER}

# Redis
docker-compose -f compose.prod.yaml exec redis redis-cli ping

# All services
docker-compose -f compose.prod.yaml ps
```

### Monitoring Endpoints

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
- **MLflow**: http://localhost:5000
- **Airflow**: http://localhost:8080

---

## Scaling

### Horizontal Scaling

**Scale Backend API:**

```bash
# Scale to 4 replicas
docker-compose -f compose.prod.yaml up -d --scale backend=4

# Verify replicas
docker-compose -f compose.prod.yaml ps backend
```

**Load Balancer Configuration (Nginx/Traefik):**

```nginx
upstream backend {
    least_conn;
    server backend-1:8000 max_fails=3 fail_timeout=30s;
    server backend-2:8000 max_fails=3 fail_timeout=30s;
    server backend-3:8000 max_fails=3 fail_timeout=30s;
    server backend-4:8000 max_fails=3 fail_timeout=30s;
}
```

### Vertical Scaling

**Adjust Resource Limits:**

Edit `compose.prod.yaml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
```

**Apply Changes:**

```bash
docker-compose -f compose.prod.yaml up -d --force-recreate backend
```

### Database Scaling

**PostgreSQL Tuning:**

```bash
# Edit PostgreSQL configuration
docker-compose -f compose.prod.yaml exec postgres vi /var/lib/postgresql/data/postgresql.conf

# Key parameters:
# shared_buffers = 4GB
# effective_cache_size = 12GB
# maintenance_work_mem = 1GB
# max_connections = 200

# Restart database
docker-compose -f compose.prod.yaml restart postgres
```

**Read Replicas:**

```yaml
# Add read replica to compose.prod.yaml
postgres-replica:
  image: postgres:14-alpine
  environment:
    POSTGRES_PRIMARY_HOST: postgres
    POSTGRES_PRIMARY_PORT: 5432
  command: >
    -c wal_level=replica
    -c hot_standby=on
    -c max_wal_senders=10
```

---

## Rollback Procedures

### Quick Rollback

```bash
# 1. Stop current version
docker-compose -f compose.prod.yaml down

# 2. Checkout previous version
git checkout <previous-tag>

# 3. Deploy previous version
docker-compose -f compose.prod.yaml up -d

# 4. Verify health
curl http://localhost:8000/health/ready
```

### Database Rollback

```bash
# Rollback migrations
docker-compose -f compose.prod.yaml exec backend alembic downgrade -1

# Restore from backup
docker-compose -f compose.prod.yaml exec postgres psql -U ${DATABASE_USER} -d ${DATABASE_NAME} < backup.sql
```

### Blue-Green Deployment

```bash
# 1. Deploy new version to "green" environment
docker-compose -f compose.prod-green.yaml up -d

# 2. Test green environment
curl http://green-backend:8000/health/ready

# 3. Switch traffic to green (update load balancer)
# 4. Keep blue running for quick rollback
# 5. Shutdown blue after verification period

docker-compose -f compose.prod-blue.yaml down
```

---

## Troubleshooting

### Common Issues

**1. Service Won't Start**

```bash
# Check logs
docker-compose -f compose.prod.yaml logs <service-name>

# Check resource usage
docker stats

# Check disk space
df -h
```

**2. Database Connection Failed**

```bash
# Verify database is running
docker-compose -f compose.prod.yaml ps postgres

# Test connection
docker-compose -f compose.prod.yaml exec backend python -c "from app.db.session import check_db_health; import asyncio; print(asyncio.run(check_db_health()))"

# Check network connectivity
docker-compose -f compose.prod.yaml exec backend ping postgres
```

**3. Redis Connection Failed**

```bash
# Verify Redis is running
docker-compose -f compose.prod.yaml ps redis

# Test connection
docker-compose -f compose.prod.yaml exec backend python -c "from app.api.deps import RedisClient; import asyncio; r = asyncio.run(RedisClient.get_instance()); print(asyncio.run(r.ping()))"
```

**4. High Memory Usage**

```bash
# Check container memory
docker stats --no-stream

# Increase resource limits
# Edit compose.prod.yaml and increase memory limits

# Restart service
docker-compose -f compose.prod.yaml restart <service>
```

**5. Slow Response Times**

```bash
# Check system resources
htop

# Check database connections
docker-compose -f compose.prod.yaml exec postgres psql -U ${DATABASE_USER} -d ${DATABASE_NAME} -c "SELECT count(*) FROM pg_stat_activity;"

# Check Redis memory
docker-compose -f compose.prod.yaml exec redis redis-cli INFO memory

# Check API workers
docker-compose -f compose.prod.yaml logs backend | grep "worker"
```

### Debug Mode

**Enable Debug Logging:**

```bash
# Temporarily enable debug logging
docker-compose -f compose.prod.yaml exec backend \
  python -c "from app.core.config import settings; settings.LOG_LEVEL='DEBUG'"

# Or restart with debug environment
docker-compose -f compose.prod.yaml up -d backend -e LOG_LEVEL=DEBUG
```

### Recovery Procedures

**Database Recovery:**

```bash
# Stop services
docker-compose -f compose.prod.yaml down

# Restore database backup
docker-compose -f compose.prod.yaml up -d postgres
docker-compose -f compose.prod.yaml exec -T postgres psql -U ${DATABASE_USER} -d ${DATABASE_NAME} < /path/to/backup.sql

# Restart all services
docker-compose -f compose.prod.yaml up -d
```

**Full System Recovery:**

```bash
# Stop all services
docker-compose -f compose.prod.yaml down

# Remove volumes (WARNING: Data loss)
docker-compose -f compose.prod.yaml down -v

# Redeploy from scratch
docker-compose -f compose.prod.yaml up -d

# Restore from backups
# ... restore database, Redis, MLflow artifacts
```

---

## Maintenance

### Backup Strategy

**Automated Backups:**

```bash
# Database backup
docker-compose -f compose.prod.yaml exec postgres pg_dump -U ${DATABASE_USER} ${DATABASE_NAME} | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Volume backup
docker run --rm -v telco-recommender-prod_postgres_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/postgres_data_$(date +%Y%m%d).tar.gz /data
```

**Backup Schedule:**
- Full backup: Daily at 2 AM
- Incremental backup: Every 6 hours
- Retention: 30 days

### Update Strategy

**Regular Updates:**
- Security patches: Weekly
- Feature releases: Monthly
- Major versions: Quarterly

### Monitoring

**Key Metrics:**
- API response time < 200ms (p95)
- Error rate < 0.1%
- CPU usage < 70%
- Memory usage < 80%
- Disk usage < 75%

---

## Support

For deployment support:
- **DevOps Team**: devops@telco-recommender.com
- **Documentation**: https://docs.telco-recommender.com
- **Status Page**: https://status.telco-recommender.com
