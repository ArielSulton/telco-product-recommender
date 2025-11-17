# Monitoring Runbook - Telco Product Recommender

## Overview

This runbook provides operational procedures for monitoring, alerting, and maintaining the Telco Product Recommender system in production.

---

## Table of Contents

1. [Monitoring Stack](#monitoring-stack)
2. [Key Metrics](#key-metrics)
3. [Alert Definitions](#alert-definitions)
4. [Dashboard Guide](#dashboard-guide)
5. [Incident Response](#incident-response)
6. [Common Scenarios](#common-scenarios)

---

## Monitoring Stack

### Components

**Prometheus** (Metrics Collection)
- **URL**: http://monitoring.telco-recommender.com:9090
- **Port**: 9090
- **Retention**: 30 days
- **Scrape Interval**: 15 seconds

**Grafana** (Visualization)
- **URL**: http://monitoring.telco-recommender.com:3000
- **Port**: 3000
- **Default Credentials**: admin/admin (change immediately)
- **Dashboards**: API Performance, ML Models, System Health

**Application Metrics** (FastAPI + Prometheus Client)
- **Endpoint**: http://api.telco-recommender.com/metrics
- **Format**: Prometheus exposition format

---

## Key Metrics

### API Performance Metrics

#### Response Time
```promql
# P50 response time
histogram_quantile(0.50, http_request_duration_seconds_bucket)

# P95 response time
histogram_quantile(0.95, http_request_duration_seconds_bucket)

# P99 response time
histogram_quantile(0.99, http_request_duration_seconds_bucket)
```

**Thresholds:**
- P50: < 100ms (target), < 200ms (acceptable)
- P95: < 200ms (target), < 500ms (acceptable)
- P99: < 500ms (target), < 1000ms (acceptable)

#### Request Rate
```promql
# Requests per second
rate(http_requests_total[5m])

# Request rate by endpoint
rate(http_requests_total[5m]) by (endpoint)

# Request rate by status code
rate(http_requests_total[5m]) by (status)
```

**Thresholds:**
- Normal: 10-100 req/s
- High: 100-500 req/s
- Alert: > 500 req/s (potential attack or spike)

#### Error Rate
```promql
# Error rate (5xx errors)
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# Error rate percentage
100 * rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

**Thresholds:**
- Normal: < 0.1%
- Warning: 0.1% - 1%
- Critical: > 1%

### System Resource Metrics

#### CPU Usage
```promql
# CPU usage percentage
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Container CPU usage
rate(container_cpu_usage_seconds_total[5m])
```

**Thresholds:**
- Normal: < 70%
- Warning: 70% - 85%
- Critical: > 85%

#### Memory Usage
```promql
# Memory usage percentage
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# Container memory usage
container_memory_usage_bytes / container_spec_memory_limit_bytes * 100
```

**Thresholds:**
- Normal: < 80%
- Warning: 80% - 90%
- Critical: > 90%

#### Disk Usage
```promql
# Disk usage percentage
(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100
```

**Thresholds:**
- Normal: < 75%
- Warning: 75% - 85%
- Critical: > 85%

### Database Metrics

#### Connection Pool
```promql
# Active connections
pg_stat_activity_count

# Connection pool saturation
pg_stat_activity_count / pg_settings_max_connections * 100
```

**Thresholds:**
- Normal: < 70%
- Warning: 70% - 85%
- Critical: > 85%

#### Query Performance
```promql
# Slow queries (> 1s)
pg_stat_statements_mean_exec_time_seconds > 1

# Query rate
rate(pg_stat_statements_calls_total[5m])
```

**Thresholds:**
- Slow Query: > 1 second
- Very Slow Query: > 5 seconds

### Redis Metrics

#### Memory Usage
```promql
# Redis memory usage
redis_memory_used_bytes / redis_memory_max_bytes * 100

# Cache hit rate
redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total) * 100
```

**Thresholds:**
- Memory: < 90%
- Hit Rate: > 80%

### ML Model Metrics

#### Recommendation Quality
```promql
# Average recommendation score
avg(recommendation_score)

# Recommendation latency
histogram_quantile(0.95, recommendation_duration_seconds_bucket)
```

**Thresholds:**
- Score: > 0.7
- Latency: < 500ms (P95)

---

## Alert Definitions

### Critical Alerts (Immediate Response Required)

#### High Error Rate
```yaml
alert: HighErrorRate
expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01
for: 5m
severity: critical
description: "Error rate is {{ $value | humanizePercentage }}"
action: |
  1. Check application logs for errors
  2. Check database connectivity
  3. Verify Redis connection
  4. Check system resources
```

#### Service Down
```yaml
alert: ServiceDown
expr: up{job="backend"} == 0
for: 1m
severity: critical
description: "Backend service is down"
action: |
  1. Check container status: docker-compose ps
  2. Check container logs: docker-compose logs backend
  3. Restart service if needed: docker-compose restart backend
  4. Verify health endpoint: curl http://localhost:8000/health
```

#### High Memory Usage
```yaml
alert: HighMemoryUsage
expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.90
for: 5m
severity: critical
description: "Memory usage is {{ $value | humanizePercentage }}"
action: |
  1. Identify memory-consuming processes
  2. Check for memory leaks in application logs
  3. Consider scaling vertically or horizontally
  4. Restart service as last resort
```

### Warning Alerts (Attention Required)

#### Slow Response Time
```yaml
alert: SlowResponseTime
expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 0.5
for: 10m
severity: warning
description: "P95 response time is {{ $value }}s"
action: |
  1. Check database query performance
  2. Review Redis cache hit rate
  3. Monitor CPU and memory usage
  4. Review recent code changes
```

#### Low Cache Hit Rate
```yaml
alert: LowCacheHitRate
expr: redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total) < 0.8
for: 15m
severity: warning
description: "Cache hit rate is {{ $value | humanizePercentage }}"
action: |
  1. Review caching strategy
  2. Check Redis memory usage
  3. Adjust cache TTL if needed
  4. Consider increasing Redis memory
```

---

## Dashboard Guide

### API Performance Dashboard

**Access**: Grafana → Dashboards → API Performance

**Panels:**
1. **Request Rate**: Total requests per second over time
2. **Response Time**: P50, P95, P99 latencies
3. **Error Rate**: 4xx and 5xx errors percentage
4. **Top Endpoints**: Most frequently accessed endpoints
5. **Status Code Distribution**: Breakdown by HTTP status

**Usage:**
- Monitor request patterns and identify traffic spikes
- Identify slow endpoints requiring optimization
- Track error trends and correlate with deployments

### ML Models Dashboard

**Access**: Grafana → Dashboards → ML Models

**Panels:**
1. **Recommendation Latency**: Time to generate recommendations
2. **Model Scores**: Average recommendation confidence
3. **Cache Performance**: Hit/miss rates for model predictions
4. **Model Version**: Currently deployed model versions
5. **Prediction Volume**: Number of recommendations generated

**Usage:**
- Monitor model performance after updates
- Identify degradation in recommendation quality
- Track model serving latency

### System Health Dashboard

**Access**: Grafana → Dashboards → Recommender System

**Panels:**
1. **Service Status**: All services up/down status
2. **Resource Usage**: CPU, memory, disk across services
3. **Database Connections**: Connection pool utilization
4. **Redis Status**: Memory usage and operations
5. **Container Health**: Docker container status

**Usage:**
- Quick overview of system health
- Identify resource bottlenecks
- Monitor service dependencies

---

## Incident Response

### Severity Levels

**P0 - Critical (Response: Immediate)**
- Service completely down
- Data loss or corruption
- Security breach

**P1 - High (Response: < 30 minutes)**
- Degraded service performance
- High error rates (> 1%)
- Multiple service failures

**P2 - Medium (Response: < 2 hours)**
- Single service degradation
- Performance issues
- Non-critical component failure

**P3 - Low (Response: Next business day)**
- Minor bugs
- Documentation issues
- Non-urgent improvements

### Response Workflow

**1. Acknowledge**
```bash
# Check alert details in Grafana
# Acknowledge alert to prevent duplicate notifications
```

**2. Assess**
```bash
# Check service status
docker-compose -f compose.prod.yaml ps

# Check recent logs
docker-compose -f compose.prod.yaml logs --tail=100 backend

# Check metrics
curl http://localhost:9090/api/v1/query?query=up
```

**3. Mitigate**
```bash
# Quick mitigation strategies
docker-compose -f compose.prod.yaml restart <service>
docker-compose -f compose.prod.yaml scale backend=4
```

**4. Investigate**
```bash
# Detailed investigation
docker-compose -f compose.prod.yaml exec backend python -c "..."
docker-compose -f compose.prod.yaml logs --since 1h backend | grep ERROR
```

**5. Resolve**
```bash
# Apply permanent fix
git pull origin main
docker-compose -f compose.prod.yaml build backend
docker-compose -f compose.prod.yaml up -d backend
```

**6. Document**
- Update incident log
- Create post-mortem if P0/P1
- Update runbook with learnings

---

## Common Scenarios

### Scenario 1: High Response Time

**Symptoms:**
- P95 latency > 500ms
- User complaints about slow app
- Grafana alert triggered

**Investigation:**
```bash
# 1. Check database query performance
docker-compose -f compose.prod.yaml exec postgres \
  psql -U $DATABASE_USER -d $DATABASE_NAME \
  -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# 2. Check Redis performance
docker-compose -f compose.prod.yaml exec redis redis-cli INFO stats

# 3. Check application logs
docker-compose -f compose.prod.yaml logs backend | grep "duration"
```

**Resolution:**
```bash
# Optimize slow queries
# Increase cache TTL
# Scale horizontally
docker-compose -f compose.prod.yaml up -d --scale backend=4
```

### Scenario 2: Database Connection Pool Exhausted

**Symptoms:**
- "Could not connect to database" errors
- High number of database connections
- Timeouts on database queries

**Investigation:**
```bash
# Check active connections
docker-compose -f compose.prod.yaml exec postgres \
  psql -U $DATABASE_USER -d $DATABASE_NAME \
  -c "SELECT count(*) FROM pg_stat_activity;"

# Check connection pool config
grep POOL_SIZE .env
```

**Resolution:**
```bash
# Increase pool size in .env
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=20

# Restart backend
docker-compose -f compose.prod.yaml restart backend
```

### Scenario 3: Redis Out of Memory

**Symptoms:**
- Cache misses increasing
- "OOM command not allowed" errors
- Redis performance degradation

**Investigation:**
```bash
# Check Redis memory
docker-compose -f compose.prod.yaml exec redis redis-cli INFO memory

# Check key count
docker-compose -f compose.prod.yaml exec redis redis-cli DBSIZE
```

**Resolution:**
```bash
# Option 1: Increase maxmemory
# Edit compose.prod.yaml and restart Redis

# Option 2: Reduce TTL
# Adjust REDIS_CACHE_TTL in .env

# Option 3: Flush old keys
docker-compose -f compose.prod.yaml exec redis redis-cli FLUSHDB
```

### Scenario 4: Model Serving Latency

**Symptoms:**
- Recommendation API slow (> 1s)
- ML model inference taking too long
- Users experiencing delays

**Investigation:**
```bash
# Check model loading time
docker-compose -f compose.prod.yaml logs backend | grep "model"

# Check recommendation latency
curl -w "@curl-format.txt" http://localhost:8000/api/v1/recommendations/user123
```

**Resolution:**
```bash
# Warm up models on startup
# Implement model caching
# Consider model quantization or distillation
# Scale ML serving separately
```

---

## Maintenance Windows

### Scheduled Maintenance

**Frequency**: Monthly (first Sunday, 2-4 AM UTC)

**Activities:**
1. Database vacuum and analyze
2. Redis memory cleanup
3. Log rotation and archival
4. Security updates
5. Backup verification

**Procedure:**
```bash
# 1. Enable maintenance mode
curl -X POST http://localhost:8000/admin/maintenance/enable

# 2. Perform maintenance tasks
docker-compose -f compose.prod.yaml exec postgres vacuumdb -U $DATABASE_USER -d $DATABASE_NAME --analyze
docker-compose -f compose.prod.yaml exec redis redis-cli BGREWRITEAOF

# 3. Verify services
./scripts/test_e2e_production.py --base-url http://localhost:8000

# 4. Disable maintenance mode
curl -X POST http://localhost:8000/admin/maintenance/disable
```

---

## Contact Information

**On-Call Engineer**: +1-XXX-XXX-XXXX
**DevOps Team**: devops@telco-recommender.com
**PagerDuty**: https://telco-recommender.pagerduty.com
**Status Page**: https://status.telco-recommender.com

**Escalation Path:**
1. On-Call Engineer (Immediate)
2. DevOps Lead (< 15 min)
3. Engineering Manager (< 30 min)
4. CTO (P0 only)
