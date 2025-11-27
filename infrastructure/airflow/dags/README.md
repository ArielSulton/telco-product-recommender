# Airflow DAGs - Telco Product Recommender

Event-driven data pipeline orchestration for real-time feature engineering.

## Overview

This directory contains Airflow DAGs for the Telco Product Recommender system. The pipeline follows an event-driven architecture where data ingestion triggers feature computation automatically.

## DAG Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     DATA FLOW PIPELINE                        │
└──────────────────────────────────────────────────────────────┘

Data Simulator
    ↓
Batch Ingestion (every 4 hours)
    ↓
    ┌─────────────────────────────┐
    │ data_ingestion_monitor DAG  │
    │ (Schedule: 0 */4 * * *)     │
    └─────────────────────────────┘
                ↓
    Check for new data in last 4h
                ↓
         ┌──────┴──────┐
         ↓             ↓
    New Data      No New Data
         ↓             ↓
    Log Stats     Skip
         ↓
    Update Metrics
         ↓
    ┌─────────────────────────────┐
    │ Trigger: feature_engineering│
    └─────────────────────────────┘
                ↓
    ┌─────────────────────────────┐
    │  feature_engineering DAG    │
    │  (Triggered by monitor)     │
    └─────────────────────────────┘
                ↓
        ┌───────┴───────┐
        ↓               ↓
    Compute RFM    Compute ARPU
        └───────┬───────┘
                ↓
        Compute RFM Scores
                ↓
        Cache to Redis (10K users)
                ↓
        Prepare Notification
                ↓
        Notify FastAPI Webhook
                ↓
        Feature Store Updated ✓
```

## DAGs

### 1. data_ingestion_monitor

**Purpose**: Monitor new data ingestion and trigger feature computation

**Schedule**: `0 */4 * * *` (Every 4 hours)

**Workflow**:
1. **check_new_data** - Check if new transactions exist in last 4 hours
2. **log_detection** - Log detection details (if new data found)
3. **skip_trigger** - Skip processing (if no new data)
4. **get_ingestion_stats** - Get batch statistics
5. **update_monitoring_metrics** - Update monitoring table
6. **trigger_feature_computation** - Trigger feature_engineering DAG

**Key Features**:
- Event-driven branching logic
- Ingestion batch tracking
- Monitoring metrics collection
- Automatic feature pipeline triggering

**Configuration**:
```python
schedule_interval='0 */4 * * *'  # Every 4 hours
catchup=False                     # Don't backfill
retries=3
retry_delay=timedelta(minutes=5)
```

### 2. feature_engineering

**Purpose**: Compute real-time features (RFM, ARPU, usage) and cache to Redis

**Schedule**: None (triggered by data_ingestion_monitor)

**Workflow**:
1. **compute_rfm** - Calculate Recency, Frequency, Monetary features
2. **compute_arpu** - Calculate ARPU buckets (low, medium, high, premium)
3. **compute_rfm_scores** - Calculate RFM quintile scores
4. **cache_to_redis** - Cache top 10K users to Redis (1h TTL)
5. **prepare_notification** - Prepare webhook payload
6. **notify_fastapi** - Send completion webhook to FastAPI

**Key Features**:
- Parallel feature computation (RFM + ARPU)
- Quintile-based RFM scoring
- Redis caching for hot features
- FastAPI webhook notification
- Comprehensive metrics tracking

**Configuration**:
```python
schedule_interval=None  # Triggered, not scheduled
catchup=False
retries=2
retry_delay=timedelta(minutes=3)
```

## Feature Computation Details

### RFM Features

**Recency**: Days since last purchase
```sql
EXTRACT(DAY FROM (NOW() - MAX(transaction_date)))
```

**Frequency**: Total number of purchases
```sql
COUNT(transaction_id)
```

**Monetary**: Total revenue from user
```sql
SUM(amount)
```

### ARPU Buckets

| Bucket | Range (IDR) |
|--------|-------------|
| low | < 50,000 |
| medium | 50,000 - 100,000 |
| high | 100,000 - 200,000 |
| premium | > 200,000 |

### RFM Scores

Quintile-based scoring (1-5):
- **R Score**: Lower recency = higher score (5 = recent purchase)
- **F Score**: Higher frequency = higher score (5 = frequent buyer)
- **M Score**: Higher monetary = higher score (5 = high value)

Example RFM scores:
- `555` - Best customers (recent, frequent, high value)
- `111` - Dormant customers (old, infrequent, low value)
- `511` - Recent but low-value customers

## Database Tables

### ingestion_batches

Tracks data ingestion progress:

```sql
CREATE TABLE ingestion_batches (
    batch_id UUID PRIMARY KEY,
    batch_start_time TIMESTAMP,
    batch_end_time TIMESTAMP,
    records_processed INTEGER,
    records_failed INTEGER,
    status VARCHAR(20),
    error_message TEXT,
    source_file VARCHAR(255)
);
```

### user_features

Stores computed features:

```sql
CREATE TABLE user_features (
    user_id UUID PRIMARY KEY,
    recency INTEGER,
    frequency INTEGER,
    monetary DECIMAL(10,2),
    arpu_bucket VARCHAR(20),
    rfm_score VARCHAR(3),
    churn_score DECIMAL(5,4),
    segment_id INTEGER,
    updated_at TIMESTAMP
);
```

### ingestion_monitoring

Tracks monitoring checks:

```sql
CREATE TABLE ingestion_monitoring (
    check_time TIMESTAMP PRIMARY KEY,
    new_records INTEGER,
    batches_processed INTEGER,
    feature_trigger_status VARCHAR(20)
);
```

## Airflow Connections

### Required Connections

#### telco_postgres
PostgreSQL connection for database access

**Type**: Postgres
**Host**: postgres
**Port**: 5432
**Database**: telco_recommender
**Login**: postgres
**Password**: postgres

#### fastapi_backend
HTTP connection for webhook notifications

**Type**: HTTP
**Host**: http://backend
**Port**: 8000
**Schema**: http

### Setup Connections

Via Airflow UI:
```
Admin → Connections → Add
```

Via CLI:
```bash
# PostgreSQL
airflow connections add telco_postgres \
    --conn-type postgres \
    --conn-host postgres \
    --conn-port 5432 \
    --conn-login postgres \
    --conn-password postgres \
    --conn-schema telco_recommender

# FastAPI
airflow connections add fastapi_backend \
    --conn-type http \
    --conn-host backend \
    --conn-port 8000
```

## Redis Caching

### Cache Structure

```
user_features:{user_id} -> Hash
    - recency: INTEGER
    - frequency: INTEGER
    - monetary: FLOAT
    - arpu_bucket: STRING
    - rfm_score: STRING
    - churn_score: FLOAT
    - segment_id: INTEGER
    - cached_at: ISO8601

feature_cache:last_update -> ISO8601
feature_cache:user_count -> INTEGER
```

### Cache Strategy

- **Top 10K users**: Cache most active users (by frequency)
- **TTL**: 1 hour (3600 seconds)
- **Updates**: Every feature engineering run
- **Eviction**: Automatic expiration

## Monitoring & Debugging

### View DAG Status

```bash
# List DAGs
airflow dags list

# Get DAG state
airflow dags state data_ingestion_monitor $(date +%Y-%m-%d)

# List task instances
airflow tasks list data_ingestion_monitor
```

### Manual Triggering

```bash
# Trigger data ingestion monitor
airflow dags trigger data_ingestion_monitor

# Trigger feature engineering (with config)
airflow dags trigger feature_engineering --conf '{"triggered_by": "manual"}'
```

### View Logs

```bash
# Task logs
airflow tasks logs data_ingestion_monitor check_new_data $(date +%Y-%m-%d)

# Webserver logs
docker logs telco-airflow-webserver-dev

# Scheduler logs
docker logs telco-airflow-scheduler-dev
```

### Check Metrics

```sql
-- Check recent ingestion batches
SELECT * FROM ingestion_batches
ORDER BY batch_start_time DESC
LIMIT 10;

-- Check monitoring records
SELECT * FROM ingestion_monitoring
ORDER BY check_time DESC
LIMIT 10;

-- Check feature update times
SELECT COUNT(*), MAX(updated_at) as latest_update
FROM user_features;
```

## Development

### Testing DAGs

```bash
# Test DAG structure
airflow dags test data_ingestion_monitor $(date +%Y-%m-%d)

# Test specific task
airflow tasks test data_ingestion_monitor check_new_data $(date +%Y-%m-%d)
```

### Adding New Tasks

1. Create Python callable function
2. Add PythonOperator to DAG
3. Define task dependencies
4. Test locally
5. Deploy to Airflow

### Best Practices

- **Idempotency**: Tasks should be rerunnable without side effects
- **Error Handling**: Use try/except and proper logging
- **XCom**: Use for small data sharing between tasks
- **Dependencies**: Use >> operator for clear task flow
- **Retry Logic**: Configure retries for transient failures
- **Monitoring**: Log key metrics and progress

## Troubleshooting

### Common Issues

**Issue**: DAG not appearing in UI
- **Solution**: Check for syntax errors: `python data_ingestion.py`
- **Solution**: Restart scheduler: `docker restart telco-airflow-scheduler-dev`

**Issue**: Database connection failed
- **Solution**: Verify telco_postgres connection in Airflow UI
- **Solution**: Check PostgreSQL is running: `docker ps | grep postgres`

**Issue**: Redis connection failed
- **Solution**: Check REDIS_HOST environment variable
- **Solution**: Verify Redis is accessible: `redis-cli ping`

**Issue**: Webhook notification failed
- **Solution**: Check fastapi_backend connection
- **Solution**: Verify FastAPI is running: `curl http://backend:8000/health`

**Issue**: Feature computation timeout
- **Solution**: Increase task timeout in DAG default_args
- **Solution**: Optimize database queries (add indexes)

## Performance Optimization

### Query Optimization

- Add indexes on frequently queried columns
- Use EXPLAIN ANALYZE to identify bottlenecks
- Batch operations for better performance

### Parallel Execution

- Configure Airflow parallelism settings
- Use LocalExecutor for better performance
- Consider CeleryExecutor for distributed execution

### Resource Management

```python
# Limit concurrent tasks
default_args = {
    'max_active_runs': 1,  # One DAG run at a time
    'concurrency': 4,      # Max parallel tasks
}
```

## Production Deployment

### Checklist

- [ ] Configure production database connection
- [ ] Set up monitoring and alerting
- [ ] Configure email notifications for failures
- [ ] Set appropriate retry policies
- [ ] Enable DAG-level SLAs
- [ ] Configure log retention
- [ ] Set up backup for Airflow metadata
- [ ] Configure resource limits

### Monitoring Recommendations

- **Metrics**: DAG success rate, task duration, feature freshness
- **Alerts**: Failed DAGs, stuck tasks, database errors
- **Dashboards**: Grafana dashboard for pipeline health

## Support

For issues and questions:
- Check Airflow logs for error details
- Review DAG code for logic issues
- Test database queries independently
- Contact: telco-ml-team@example.com
