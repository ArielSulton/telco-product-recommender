# Telco Data Streaming Simulator

Sprint 1: Infrastructure & Streaming Foundation

## Overview

The Data Streaming Simulator simulates real-world data ingestion from CSV files into PostgreSQL. It streams customer behavior data in configurable batches to mimic production data pipelines.

## Architecture

```
CSV Data (ac-01_telco_customer_behavior_mock_data.csv)
    ↓ (batch processing with APScheduler)
[TelcoDataSimulator]
    ↓ (realistic timestamp adjustment)
[PostgreSQL] (transactions, users tables)
    ↓ (batch tracking)
[ingestion_batches table]
```

## Features

- **Batch Processing**: Configurable batch sizes (default: 1000 records)
- **Scheduled Ingestion**: Periodic data ingestion (default: every 4 hours)
- **Realistic Timestamps**: Adjusts timestamps to simulate real-time data flow
- **Progress Tracking**: Records batch status in `ingestion_batches` table
- **Error Handling**: Comprehensive error logging with partial batch support
- **Replay Mode**: Optional continuous replay when all data is processed
- **Privacy**: SHA-256 hashing of customer IDs (MSISDN)

## Configuration

### Environment Variables

```bash
# Database connection
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/telco_recommender

# Data source
DATA_SOURCE_PATH=/app/ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv

# Ingestion settings
BATCH_SIZE=1000                     # Records per batch
INGESTION_INTERVAL_HOURS=4          # Hours between ingestion runs
START_IMMEDIATELY=true              # Run ingestion on startup
REPLAY_MODE=false                   # Replay data when complete

# Scheduling
USE_CRON=false                      # Use cron expression instead of interval
CRON_EXPRESSION="0 */4 * * *"       # Cron schedule (every 4 hours)

# Redis (for feature cache integration)
REDIS_HOST=redis
REDIS_PORT=6379
```

### Configuration File

See `config.yaml` for additional configuration options.

## Usage

### Run with Docker Compose

```bash
# Start all services (includes data-simulator)
docker compose -f compose.dev.yaml up -d

# View simulator logs
docker compose -f compose.dev.yaml logs -f data-simulator

# Stop simulator
docker compose -f compose.dev.yaml stop data-simulator
```

### Run Standalone

```bash
# Install dependencies
pip install -r requirements.txt

# Run single batch
python simulator.py

# Run scheduler
python scheduler.py
```

## Data Mapping

### CSV to Database

| CSV Column | Database Table | Column | Transformation |
|------------|----------------|--------|----------------|
| customer_id | users | msisdn_hash | SHA-256 hash |
| plan_type | users | - | Used for user creation |
| monthly_spend | transactions | amount | Direct mapping |
| target_offer | transactions | product_id | Mapped via offer_mapping |

### Offer to Product Mapping

| Target Offer | Product ID | Product Name |
|--------------|------------|--------------|
| General Offer | PKG003 | Combo Hemat 5GB |
| Device Upgrade Offer | PKG004 | Combo Super 15GB |
| Data Booster | PKG002 | Internet Freedom 25GB |
| Top-up Promo | PKG001 | Internet Freedom 10GB |

## Monitoring

### Batch Status

Check ingestion progress in PostgreSQL:

```sql
-- Recent batches
SELECT batch_id, batch_start_time, batch_end_time,
       records_processed, records_failed, status
FROM ingestion_batches
ORDER BY batch_start_time DESC
LIMIT 10;

-- Total ingestion stats
SELECT
    COUNT(*) as total_batches,
    SUM(records_processed) as total_records,
    SUM(records_failed) as total_failures
FROM ingestion_batches;
```

### Health Checks

The simulator includes a health check that verifies:
- Database connectivity
- CSV file accessibility
- Scheduler status

## Event-Driven Integration

The simulator integrates with Airflow DAGs:

1. **Data Ingestion**: Simulator streams batches to PostgreSQL
2. **Monitoring**: `data_ingestion_monitor` DAG checks for new data every 4 hours
3. **Feature Computation**: Triggers `feature_engineering` DAG when new data detected
4. **Caching**: Features cached to Redis for fast retrieval

## Error Handling

### Retry Logic

- **Database connection failures**: Automatic reconnection with connection pool
- **Individual record failures**: Logged but don't stop batch processing
- **Batch failures**: Recorded in `ingestion_batches` with error message

### Partial Batches

If some records fail, the batch status is set to `partial` with counts of both successful and failed records.

## Performance

### Batch Size Recommendations

| Environment | Batch Size | Frequency | Rationale |
|-------------|------------|-----------|-----------|
| Development | 1000 | 4 hours | Balance between speed and realism |
| Testing | 5000 | 1 hour | Faster data population |
| Demo | 500 | 2 hours | Frequent updates for demos |

### Resource Usage

- **Memory**: ~100MB for Python process
- **Database**: Minimal impact with batching
- **Network**: Low bandwidth (batch processing)

## Troubleshooting

### Simulator Not Starting

```bash
# Check logs
docker compose logs data-simulator

# Common issues:
# 1. Database not ready - wait for postgres health check
# 2. CSV file not found - verify volume mount
# 3. Port conflicts - check DATABASE_URL
```

### No Data Ingestion

```bash
# Check simulator progress
docker compose exec data-simulator python -c "
from simulator import TelcoDataSimulator
import os
sim = TelcoDataSimulator(
    os.getenv('DATA_SOURCE_PATH'),
    os.getenv('DATABASE_URL')
)
print(sim.get_progress())
"

# Check database
docker compose exec postgres psql -U postgres -d telco_recommender -c "
SELECT COUNT(*) FROM transactions;
"
```

### Reset Ingestion

```bash
# Delete existing data
docker compose exec postgres psql -U postgres -d telco_recommender -c "
TRUNCATE transactions CASCADE;
TRUNCATE ingestion_batches CASCADE;
"

# Restart simulator
docker compose restart data-simulator
```

## Development

### Testing

```python
# Test single batch
from simulator import TelcoDataSimulator

simulator = TelcoDataSimulator(
    csv_path='path/to/csv',
    db_url='postgresql://user:pass@host:port/db'
)

result = simulator.ingest_batch(batch_size=100)
print(result)

# Check progress
progress = simulator.get_progress()
print(progress)
```

### Extending

To add custom transformations:

1. Modify `_map_offer_to_product()` for product mapping
2. Add preprocessing in `ingest_batch()` method
3. Update schema validation in `_load_data()`

## Security

- **Customer IDs**: Hashed using SHA-256 before storage
- **Database Credentials**: Passed via environment variables
- **Read-Only CSV**: Mounted as read-only volume in Docker

## License

Part of the Telco Product Recommender system - Sprint 1 Implementation.
