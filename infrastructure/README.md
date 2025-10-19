# Infrastructure - Telco Product Recommender

DevOps configuration and infrastructure as code for the recommendation system.

## Overview

Complete infrastructure setup including:
- Docker containerization
- Database setup (PostgreSQL)
- Caching layer (Redis)
- Monitoring stack (Prometheus + Grafana)
- ETL orchestration (Apache Airflow)

## Technology Stack

- **Containerization**: Docker + Docker Compose
- **Database**: PostgreSQL 14
- **Cache**: Redis 7
- **Deployment Platform**: Dokploy (with built-in Traefik reverse proxy)
- **Monitoring**: Prometheus + Grafana
- **ETL**: Apache Airflow
- **Secrets Management**: Docker secrets / .env

## Project Structure

```
infrastructure/
├── postgres/
│   ├── init/                # Initial schema SQL
│   └── migrations/          # Schema evolution scripts
├── redis/
│   └── redis.conf           # Redis configuration
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       ├── provisioning/
│       │   ├── dashboards/
│       │   └── datasources/
│       └── dashboards/
└── airflow/
    ├── dags/                # ETL workflows
    └── plugins/             # Custom operators
```

## Quick Start

### Development Environment

```bash
# Start all services
docker-compose -f compose.dev.yaml up -d

# View logs
docker-compose -f compose.dev.yaml logs -f

# Stop all services
docker-compose -f compose.dev.yaml down
```

Services will be available at:
- **Backend API**: http://localhost:8000
- **Frontend**: http://localhost:5173
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **MLflow**: http://localhost:5000
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
- **Airflow**: http://localhost:8080

### Production Environment (Dokploy)

**Dokploy** handles deployment with built-in Traefik reverse proxy for automatic:
- SSL/TLS certificate generation (Let's Encrypt)
- Reverse proxy routing
- Load balancing
- HTTP to HTTPS redirect

```bash
# Via Dokploy UI:
1. Create new project
2. Connect GitHub repository
3. Set environment variables
4. Deploy using compose.prod.yaml

# Or via Dokploy CLI:
dokploy deploy --compose compose.prod.yaml --env production
```

**Domain Configuration**:
- Frontend: `yourdomain.com` (configured via Traefik labels)
- Backend API: `api.yourdomain.com`
- Grafana: `monitoring.yourdomain.com`

No manual Nginx configuration needed - Traefik handles all routing automatically.

## Database Setup

### Initial Schema

Located in `postgres/init/01_init.sql`:
- `users` - Customer master data
- `products` - Telco package catalog
- `transactions` - Purchase history
- `events` - Web interaction tracking
- `user_features` - Pre-computed ML features

### Migrations

Using Alembic for schema evolution:
```bash
# Create migration
alembic revision -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

Stored in `postgres/migrations/`:
- `V1__create_users.sql`
- `V2__create_products.sql`
- `V3__create_events.sql`
- `V4__create_features.sql`

## Redis Configuration

### Cache Strategy

**Hot Data (TTL: 1 hour)**:
- User features (RFM, ARPU, usage)
- User segments
- Popular products per segment

**Session Data (TTL: 24 hours)**:
- A/B test variant assignments
- User session tracking

### Redis Keys Convention
```
user:features:{user_id}           # User feature vector
user:segment:{user_id}            # Segment assignment
segment:popular:{segment_id}      # Popular products
session:variant:{session_id}      # A/B variant
```

## Monitoring Stack

### Prometheus

Metrics collected:
- **Backend**: Request latency, error rate, throughput
- **Database**: Connection pool, query duration
- **Redis**: Hit/miss rate, memory usage
- **ML Models**: Inference latency, cache hits

Configuration: `monitoring/prometheus/prometheus.yml`

### Grafana Dashboards

Pre-configured dashboards:
1. **System Overview**: CPU, memory, disk, network
2. **API Metrics**: Latency (p50/p95/p99), error rate, RPS
3. **Recommendation Quality**: CTR, conversion, NDCG
4. **A/B Test Results**: Variant performance comparison
5. **Database Health**: Query performance, connections

Access: http://localhost:3000 (admin/admin)

## Airflow ETL

### DAGs

**Daily ETL** (`etl_pipeline.py`):
- Extract transaction data from source systems
- Transform and clean data
- Load to PostgreSQL
- Recalculate user features
- Update Redis cache

**Weekly Retraining** (`model_retraining.py`):
- Fetch latest data
- Trigger model training scripts
- Evaluate new models
- Deploy to MLflow registry (if improved)
- Update inference service

### Schedule
- ETL: Daily at 02:00 UTC
- Retraining: Sunday at 03:00 UTC

## Security

### Network Isolation
- Frontend: Public network (via Traefik)
- Backend: Private network + exposed via Traefik
- Database: Private network only
- Redis: Private network only

### Secrets Management

Development:
```bash
cp ../.env.example .env
# Edit with development credentials
```

Production (via Dokploy):
- Environment variables set in Dokploy UI
- Automatic secret encryption
- Credential rotation via Dokploy interface
- RBAC through Dokploy user management

### SSL/TLS

Dokploy + Traefik automatically provides:
- Let's Encrypt SSL certificates (auto-renewal)
- TLS 1.2+ enforcement
- Strong cipher suites (configured by Traefik)
- HTTP to HTTPS redirect
- HSTS headers

No manual certificate management needed.

## Backup Strategy

### Database Backups
- **Frequency**: Every 6 hours
- **Retention**: 7 days (hourly), 4 weeks (daily), 12 months (weekly)
- **Method**: pg_dump with compression
- **Storage**: S3-compatible object storage

### Redis Persistence
- RDB snapshots: Every 1 hour
- AOF: Append-only file enabled
- Backup to persistent volume

## Scaling

### Horizontal Scaling

**Backend**:
```yaml
deploy:
  replicas: 3  # Increase based on load
```

**Database**:
- Read replicas for analytics queries
- Connection pooling (pgbouncer)

**Redis**:
- Redis Cluster for high availability
- Sentinel for automatic failover

### Vertical Scaling

Resource limits in `compose.prod.yaml`:
```yaml
resources:
  limits:
    cpus: '2'
    memory: 4G
  reservations:
    cpus: '1'
    memory: 2G
```

## Health Checks

All services implement health checks:
- **Backend**: `GET /health`
- **PostgreSQL**: `pg_isready`
- **Redis**: `redis-cli ping`
- **Airflow**: Scheduler heartbeat

## Disaster Recovery

### RTO/RPO Targets
- **Recovery Time Objective**: <15 minutes
- **Recovery Point Objective**: <1 hour

### Procedures
1. Restore database from latest backup
2. Rebuild Redis cache from PostgreSQL
3. Redeploy services from container registry
4. Verify health checks
5. Resume traffic routing

## Performance Tuning

### PostgreSQL
- Shared buffers: 25% of RAM
- Effective cache: 75% of RAM
- Max connections: 200
- Work mem: 256MB
- Maintenance work mem: 1GB

### Redis
- Max memory: 4GB
- Eviction policy: allkeys-lru
- Max memory samples: 5

## Observability

### Logging
- Centralized logging (future: ELK stack)
- Structured JSON logs
- Log levels: DEBUG, INFO, WARN, ERROR
- Retention: 30 days

### Tracing
- Distributed tracing (future: Jaeger)
- Request ID propagation
- Service dependency mapping

### Alerting
- Prometheus Alertmanager
- Slack/Email notifications
- Alert rules:
  - Latency p95 >300ms
  - Error rate >2%
  - Database connections >80%
  - Disk usage >85%

## Cost Optimization

### Resource Efficiency
- Autoscaling based on CPU/memory
- Spot instances for batch jobs
- Reserved instances for baseline
- Regular resource right-sizing

### Monitoring
- Monthly cost reports
- Resource utilization dashboards
- Idle resource detection

## Status

🚧 **Under Development** - Sprint 1-5 implementation in progress

Current setup:
- ✅ Docker Compose files (dev/prod)
- 🚧 Database schema (pending finalization)
- 🚧 Monitoring dashboards (pending configuration)
- 🚧 Airflow DAGs (pending data availability)

See `../IMPLEMENTATION_FLOW.md` for detailed implementation roadmap.

## Contributing

When adding infrastructure:
1. Document all configuration changes
2. Update relevant README sections
3. Test in development environment
4. Validate resource limits
5. Update monitoring/alerting
