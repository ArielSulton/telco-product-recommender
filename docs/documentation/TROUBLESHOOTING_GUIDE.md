# Troubleshooting Guide - Telco Product Recommender

## Overview

Comprehensive troubleshooting guide for common issues in the Telco Product Recommender system.

---

## Table of Contents

1. [Quick Diagnosis](#quick-diagnosis)
2. [Application Issues](#application-issues)
3. [Database Issues](#database-issues)
4. [Redis Issues](#redis-issues)
5. [Performance Issues](#performance-issues)
6. [Security Issues](#security-issues)
7. [Deployment Issues](#deployment-issues)

---

## Quick Diagnosis

### Health Check Commands

```bash
# Check all services status
docker-compose -f compose.prod.yaml ps

# Check API health
curl http://localhost:8000/health/ready

# Check logs for errors
docker-compose -f compose.prod.yaml logs --tail=50 backend | grep -i error

# Check resource usage
docker stats --no-stream

# Check network connectivity
docker-compose -f compose.prod.yaml exec backend ping postgres
docker-compose -f compose.prod.yaml exec backend ping redis
```

### Common Error Patterns

| Error Pattern | Likely Cause | Section |
|--------------|-------------|---------|
| "Connection refused" | Service not running | [Application Issues](#application-issues) |
| "Database locked" | Connection pool exhausted | [Database Issues](#database-issues) |
| "Redis timeout" | Redis overloaded/down | [Redis Issues](#redis-issues) |
| "Out of memory" | Memory leak/insufficient resources | [Performance Issues](#performance-issues) |
| "401 Unauthorized" | Authentication issue | [Security Issues](#security-issues) |

---

## Application Issues

### Issue: Backend Service Won't Start

**Symptoms:**
- Container exits immediately
- "Exited (1)" status in docker ps
- Error in startup logs

**Diagnosis:**
```bash
# Check container logs
docker-compose -f compose.prod.yaml logs backend

# Check environment variables
docker-compose -f compose.prod.yaml exec backend env | grep -E "DATABASE|REDIS|SECRET"

# Verify configuration
docker-compose -f compose.prod.yaml config
```

**Common Causes:**

**1. Missing Environment Variables**
```bash
# Check .env file
cat .env | grep SECRET_KEY

# Solution: Add missing variables
cp .env.example .env
nano .env  # Fill in values
```

**2. Database Connection Failed**
```bash
# Test database connection
docker-compose -f compose.prod.yaml exec backend \
  python -c "from app.db.session import check_db_health; import asyncio; print(asyncio.run(check_db_health()))"

# Solution: Ensure database is running
docker-compose -f compose.prod.yaml up -d postgres
docker-compose -f compose.prod.yaml restart backend
```

**3. Port Already in Use**
```bash
# Check what's using the port
sudo lsof -i :8000

# Solution: Stop conflicting process or change port
sudo kill -9 <PID>
# Or change API_PORT in .env
```

### Issue: High Memory Usage / OOM Errors

**Symptoms:**
- Container killed by OOM
- "Cannot allocate memory" errors
- Slow performance and crashes

**Diagnosis:**
```bash
# Check memory usage
docker stats --no-stream backend

# Check application memory
docker-compose -f compose.prod.yaml exec backend \
  python -c "import psutil; print(f'Memory: {psutil.virtual_memory().percent}%')"

# Check for memory leaks
docker-compose -f compose.prod.yaml logs backend | grep -i "memory"
```

**Solutions:**

**1. Increase Container Memory Limit**
```yaml
# In compose.prod.yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 4G  # Increase from 2G
```

**2. Optimize Application**
```python
# Check for memory leaks in code
# Use memory profiling tools
# Implement proper garbage collection
```

**3. Scale Horizontally**
```bash
# Add more replicas instead of increasing memory
docker-compose -f compose.prod.yaml up -d --scale backend=4
```

### Issue: Slow Request Processing

**Symptoms:**
- High response times (> 1s)
- Timeouts on API calls
- User complaints about slow app

**Diagnosis:**
```bash
# Check response times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/health

# Check application logs
docker-compose -f compose.prod.yaml logs backend | grep "duration"

# Check system load
docker-compose -f compose.prod.yaml exec backend top
```

**Solutions:**

**1. Database Query Optimization**
```bash
# Find slow queries
docker-compose -f compose.prod.yaml exec postgres \
  psql -U $DATABASE_USER -d $DATABASE_NAME \
  -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Add indexes, optimize queries
```

**2. Enable/Verify Caching**
```bash
# Check cache hit rate
docker-compose -f compose.prod.yaml exec redis redis-cli INFO stats

# Increase cache TTL
# Edit REDIS_CACHE_TTL in .env
```

**3. Increase Workers**
```bash
# Edit .env
API_WORKERS=8  # Increase from 4

# Restart backend
docker-compose -f compose.prod.yaml restart backend
```

---

## Database Issues

### Issue: Connection Pool Exhausted

**Symptoms:**
- "Could not get database connection" errors
- "Connection pool timeout" errors
- High number of active connections

**Diagnosis:**
```bash
# Check active connections
docker-compose -f compose.prod.yaml exec postgres \
  psql -U $DATABASE_USER -d $DATABASE_NAME \
  -c "SELECT count(*) as connections, state FROM pg_stat_activity GROUP BY state;"

# Check pool configuration
grep DATABASE_POOL .env
```

**Solutions:**

**1. Increase Pool Size**
```bash
# Edit .env
DATABASE_POOL_SIZE=20       # Increase from 5
DATABASE_MAX_OVERFLOW=30    # Increase from 10

# Restart backend
docker-compose -f compose.prod.yaml restart backend
```

**2. Fix Connection Leaks**
```python
# Ensure proper connection cleanup in code
# Use context managers for database sessions
async with get_db() as db:
    # Database operations
    pass
```

**3. Kill Idle Connections**
```bash
# Terminate idle connections
docker-compose -f compose.prod.yaml exec postgres \
  psql -U $DATABASE_USER -d $DATABASE_NAME \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND state_change < NOW() - INTERVAL '30 minutes';"
```

### Issue: Slow Database Queries

**Symptoms:**
- High query execution times
- Database CPU at 100%
- Slow API responses

**Diagnosis:**
```bash
# Enable query logging
docker-compose -f compose.prod.yaml exec postgres \
  psql -U $DATABASE_USER -d $DATABASE_NAME \
  -c "ALTER SYSTEM SET log_min_duration_statement = 1000;"

# Restart PostgreSQL
docker-compose -f compose.prod.yaml restart postgres

# Check slow queries
docker-compose -f compose.prod.yaml logs postgres | grep "duration"
```

**Solutions:**

**1. Add Missing Indexes**
```sql
-- Analyze table usage
SELECT schemaname, tablename, seq_scan, idx_scan
FROM pg_stat_user_tables
WHERE seq_scan > idx_scan
ORDER BY seq_scan DESC;

-- Create indexes on frequently queried columns
CREATE INDEX idx_users_user_id ON users(user_id);
CREATE INDEX idx_events_timestamp ON events(timestamp);
```

**2. Vacuum and Analyze**
```bash
# Vacuum database
docker-compose -f compose.prod.yaml exec postgres \
  vacuumdb -U $DATABASE_USER -d $DATABASE_NAME --analyze --verbose

# Auto-vacuum settings
ALTER TABLE users SET (autovacuum_vacuum_scale_factor = 0.1);
```

**3. Optimize Queries**
```sql
-- Use EXPLAIN ANALYZE to understand query plans
EXPLAIN ANALYZE SELECT * FROM users WHERE user_id = 'user123';

-- Rewrite queries to use indexes
-- Limit result sets with LIMIT
-- Use JOIN instead of subqueries where appropriate
```

### Issue: Database Connection Refused

**Symptoms:**
- "Connection refused" errors
- "Database unavailable" errors
- Cannot connect to PostgreSQL

**Diagnosis:**
```bash
# Check if PostgreSQL is running
docker-compose -f compose.prod.yaml ps postgres

# Check PostgreSQL logs
docker-compose -f compose.prod.yaml logs postgres

# Test connection
docker-compose -f compose.prod.yaml exec backend \
  pg_isready -h postgres -p 5432 -U $DATABASE_USER
```

**Solutions:**

**1. Start PostgreSQL**
```bash
docker-compose -f compose.prod.yaml up -d postgres

# Wait for health check
docker-compose -f compose.prod.yaml exec postgres pg_isready
```

**2. Check Network Connectivity**
```bash
# Verify containers are on same network
docker network ls
docker network inspect telco-network

# Recreate network if needed
docker-compose -f compose.prod.yaml down
docker-compose -f compose.prod.yaml up -d
```

**3. Verify Credentials**
```bash
# Check environment variables
docker-compose -f compose.prod.yaml exec backend env | grep DATABASE

# Test manual connection
docker-compose -f compose.prod.yaml exec postgres \
  psql -h localhost -U $DATABASE_USER -d $DATABASE_NAME
```

---

## Redis Issues

### Issue: Redis Connection Timeout

**Symptoms:**
- "Redis timeout" errors
- Cache operations failing
- Slow cache reads

**Diagnosis:**
```bash
# Check Redis status
docker-compose -f compose.prod.yaml ps redis

# Test connection
docker-compose -f compose.prod.yaml exec backend \
  python -c "from app.api.deps import RedisClient; import asyncio; r = asyncio.run(RedisClient.get_instance()); print(asyncio.run(r.ping()))"

# Check Redis performance
docker-compose -f compose.prod.yaml exec redis redis-cli INFO stats
```

**Solutions:**

**1. Increase Redis Memory**
```yaml
# In compose.prod.yaml
services:
  redis:
    command: >
      redis-server
      --maxmemory 1gb  # Increase from 512mb
```

**2. Optimize Redis Configuration**
```bash
# Check memory usage
docker-compose -f compose.prod.yaml exec redis redis-cli INFO memory

# Clear unused keys
docker-compose -f compose.prod.yaml exec redis redis-cli --scan --pattern "old:*" | xargs redis-cli DEL
```

**3. Adjust Timeout Settings**
```bash
# Increase timeout in application
# Edit Redis connection settings
REDIS_TIMEOUT=10  # Increase timeout
```

### Issue: Redis Out of Memory

**Symptoms:**
- "OOM command not allowed" errors
- Cache writes failing
- Eviction of keys

**Diagnosis:**
```bash
# Check memory usage
docker-compose -f compose.prod.yaml exec redis redis-cli INFO memory | grep used_memory

# Check key count
docker-compose -f compose.prod.yaml exec redis redis-cli DBSIZE

# Check eviction policy
docker-compose -f compose.prod.yaml exec redis redis-cli CONFIG GET maxmemory-policy
```

**Solutions:**

**1. Increase maxmemory**
```yaml
# In compose.prod.yaml
services:
  redis:
    command: --maxmemory 2gb --maxmemory-policy allkeys-lru
```

**2. Reduce TTL**
```bash
# Edit .env
REDIS_CACHE_TTL=1800  # Reduce from 3600

# Flush old keys
docker-compose -f compose.prod.yaml exec redis redis-cli FLUSHDB
```

**3. Implement Key Expiration**
```python
# Set TTL on all cached keys
await redis.setex(key, ttl, value)
```

---

## Performance Issues

### Issue: High CPU Usage

**Symptoms:**
- CPU at 100%
- Slow response times
- System unresponsive

**Diagnosis:**
```bash
# Check CPU usage
docker stats --no-stream

# Check process CPU usage
docker-compose -f compose.prod.yaml exec backend top -bn1 | head -20

# Check for CPU-intensive operations
docker-compose -f compose.prod.yaml logs backend | grep -i "slow"
```

**Solutions:**

**1. Identify CPU-Intensive Code**
```python
# Use profiling tools
import cProfile
cProfile.run('your_function()')

# Optimize algorithms
# Cache expensive computations
```

**2. Increase CPU Limit**
```yaml
# In compose.prod.yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '4'  # Increase from 2
```

**3. Scale Horizontally**
```bash
# Add more replicas
docker-compose -f compose.prod.yaml up -d --scale backend=6
```

### Issue: Network Latency

**Symptoms:**
- High response times
- Timeouts
- Intermittent failures

**Diagnosis:**
```bash
# Test network latency
docker-compose -f compose.prod.yaml exec backend ping -c 10 postgres

# Check network statistics
docker network inspect telco-network

# Test external connectivity
docker-compose -f compose.prod.yaml exec backend curl -w "@curl-format.txt" https://example.com
```

**Solutions:**

**1. Optimize Network Configuration**
```yaml
# Use host network for better performance
network_mode: host
```

**2. Reduce External Calls**
```python
# Cache external API responses
# Use connection pooling
# Implement circuit breakers
```

---

## Security Issues

### Issue: Authentication Failures

**Symptoms:**
- 401 Unauthorized errors
- Token validation failures
- Login failures

**Diagnosis:**
```bash
# Check JWT configuration
docker-compose -f compose.prod.yaml exec backend env | grep SECRET_KEY

# Test token generation
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}'
```

**Solutions:**

**1. Verify SECRET_KEY**
```bash
# Generate new secret key
openssl rand -hex 32

# Update .env
SECRET_KEY=<new-secret-key>

# Restart backend
docker-compose -f compose.prod.yaml restart backend
```

**2. Check Token Expiration**
```bash
# Increase token lifetime
ACCESS_TOKEN_EXPIRE_MINUTES=60  # Increase from 30
```

### Issue: CORS Errors

**Symptoms:**
- "CORS policy blocked" errors in browser
- Preflight request failures
- Cross-origin issues

**Diagnosis:**
```bash
# Check CORS configuration
docker-compose -f compose.prod.yaml exec backend env | grep ALLOWED_ORIGINS

# Test CORS headers
curl -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: X-Requested-With" \
  -X OPTIONS http://localhost:8000/api/v1/recommendations
```

**Solutions:**

**1. Update Allowed Origins**
```bash
# Edit .env
ALLOWED_ORIGINS=https://app.telco-recommender.com,https://admin.telco-recommender.com

# Restart backend
docker-compose -f compose.prod.yaml restart backend
```

**2. Verify CORS Middleware**
```python
# Check main.py CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Deployment Issues

### Issue: Container Build Failures

**Symptoms:**
- "ERROR: failed to build" messages
- Dependency installation failures
- Docker build hanging

**Diagnosis:**
```bash
# Check build output
docker-compose -f compose.prod.yaml build --no-cache backend

# Check Dockerfile syntax
docker-compose -f compose.prod.yaml config
```

**Solutions:**

**1. Clear Docker Cache**
```bash
docker system prune -af
docker volume prune -f
docker-compose -f compose.prod.yaml build --no-cache
```

**2. Fix Dependency Issues**
```bash
# Update requirements.txt
pip install --upgrade pip
pip install -r requirements.txt

# Rebuild
docker-compose -f compose.prod.yaml build backend
```

### Issue: Health Check Failures

**Symptoms:**
- Container marked as unhealthy
- Automatic restarts
- Service unavailable

**Diagnosis:**
```bash
# Check health status
docker-compose -f compose.prod.yaml ps

# Check health check logs
docker inspect <container-id> --format='{{json .State.Health}}' | jq

# Test health endpoint manually
curl http://localhost:8000/health/ready
```

**Solutions:**

**1. Adjust Health Check Parameters**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
  interval: 60s      # Increase interval
  timeout: 30s       # Increase timeout
  retries: 5         # Increase retries
  start_period: 60s  # Increase start period
```

**2. Fix Application Issues**
```bash
# Check what's failing
docker-compose -f compose.prod.yaml logs backend

# Fix underlying issue (database, Redis, etc.)
```

---

## Getting Help

If issues persist after following this guide:

1. **Check logs**: `docker-compose logs --tail=100 <service>`
2. **Run diagnostics**: `./scripts/test_e2e_production.py`
3. **Review documentation**: `docs/` directory
4. **Contact support**: devops@telco-recommender.com
5. **Open issue**: https://github.com/your-org/telco-recommender/issues
