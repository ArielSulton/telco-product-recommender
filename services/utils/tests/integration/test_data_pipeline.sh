#!/bin/bash
# ==============================================
# Data Pipeline Integration Test Script
# ==============================================
# Tests the complete data streaming and feature engineering pipeline
# Sprint 1/2 - Infrastructure & Streaming Foundation

set -e

echo "======================================"
echo "Data Pipeline Integration Test"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# Test function
test_step() {
    local test_name=$1
    local test_command=$2

    echo -e "${YELLOW}Testing:${NC} $test_name"

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}: $test_name"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}: $test_name"
        ((TESTS_FAILED++))
        return 1
    fi
}

echo "Step 1: Verify Docker Services"
echo "------------------------------"

test_step "PostgreSQL is running" \
    "docker compose -f compose.dev.yaml ps postgres | grep -q 'Up'"

test_step "Redis is running" \
    "docker compose -f compose.dev.yaml ps redis | grep -q 'Up'"

test_step "Data Simulator is running" \
    "docker compose -f compose.dev.yaml ps data-simulator | grep -q 'Up'"

test_step "Airflow Webserver is running" \
    "docker compose -f compose.dev.yaml ps airflow-webserver | grep -q 'Up'"

test_step "Airflow Scheduler is running" \
    "docker compose -f compose.dev.yaml ps airflow-scheduler | grep -q 'Up'"

echo ""
echo "Step 2: Verify Database Schema"
echo "------------------------------"

test_step "users table exists" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c '\\dt users' | grep -q 'users'"

test_step "products table exists" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c '\\dt products' | grep -q 'products'"

test_step "transactions table exists" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c '\\dt transactions' | grep -q 'transactions'"

test_step "events table exists" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c '\\dt events' | grep -q 'events'"

test_step "user_features table exists" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c '\\dt user_features' | grep -q 'user_features'"

test_step "ingestion_batches table exists" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c '\\dt ingestion_batches' | grep -q 'ingestion_batches'"

echo ""
echo "Step 3: Test Data Simulator"
echo "------------------------------"

# Trigger manual ingestion
echo "Triggering manual data ingestion..."
docker compose -f compose.dev.yaml exec -T data-simulator python simulator.py || true

sleep 3

test_step "Data ingestion created batch records" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c 'SELECT COUNT(*) FROM ingestion_batches' | grep -q '[1-9]'"

test_step "Users were created" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c 'SELECT COUNT(*) FROM users' | grep -q '[1-9]'"

test_step "Transactions were created" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c 'SELECT COUNT(*) FROM transactions' | grep -q '[1-9]'"

echo ""
echo "Step 4: Test Airflow DAGs"
echo "------------------------------"

# Check if DAGs are available
test_step "data_ingestion_monitor DAG exists" \
    "docker compose -f compose.dev.yaml exec -T airflow-webserver airflow dags list | grep -q 'data_ingestion_monitor'"

test_step "feature_engineering DAG exists" \
    "docker compose -f compose.dev.yaml exec -T airflow-webserver airflow dags list | grep -q 'feature_engineering'"

# Trigger DAGs manually
echo ""
echo "Triggering Airflow DAGs manually..."
docker compose -f compose.dev.yaml exec -T airflow-webserver airflow dags trigger data_ingestion_monitor || true

sleep 10

echo ""
echo "Step 5: Test Feature Engineering"
echo "------------------------------"

# Manually trigger feature computation
echo "Running feature computation SQL..."
docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender << 'EOF' || true
-- Compute RFM features
WITH user_rfm AS (
    SELECT
        u.user_id,
        COALESCE(EXTRACT(DAY FROM (NOW() - MAX(t.transaction_date)))::INTEGER, 365) AS recency,
        COALESCE(COUNT(t.transaction_id), 0)::INTEGER AS frequency,
        COALESCE(SUM(t.amount), 0)::DECIMAL(10,2) AS monetary,
        MAX(t.transaction_date) AS last_purchase_date
    FROM users u
    LEFT JOIN transactions t ON u.user_id = t.user_id AND t.status = 'completed'
    GROUP BY u.user_id
)
INSERT INTO user_features (user_id, recency, frequency, monetary, last_purchase_date, updated_at)
SELECT user_id, recency, frequency, monetary, last_purchase_date, NOW()
FROM user_rfm
ON CONFLICT (user_id)
DO UPDATE SET
    recency = EXCLUDED.recency,
    frequency = EXCLUDED.frequency,
    monetary = EXCLUDED.monetary,
    last_purchase_date = EXCLUDED.last_purchase_date,
    updated_at = NOW();
EOF

sleep 2

test_step "User features were computed" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c 'SELECT COUNT(*) FROM user_features WHERE frequency > 0' | grep -q '[1-9]'"

test_step "RFM features are populated" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c 'SELECT COUNT(*) FROM user_features WHERE recency IS NOT NULL AND frequency > 0 AND monetary > 0' | grep -q '[1-9]'"

echo ""
echo "Step 6: Test Redis Cache"
echo "------------------------------"

test_step "Redis is accessible" \
    "docker compose -f compose.dev.yaml exec -T redis redis-cli ping | grep -q 'PONG'"

# Try to cache a sample feature
docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -t -c "SELECT user_id FROM user_features WHERE frequency > 0 LIMIT 1" | head -1 | xargs | read USER_ID || USER_ID=""

if [ -n "$USER_ID" ]; then
    echo "Caching sample user features to Redis..."
    docker compose -f compose.dev.yaml exec -T redis redis-cli HSET "user_features:$USER_ID" recency 10 frequency 5 monetary 100000 > /dev/null 2>&1 || true
    docker compose -f compose.dev.yaml exec -T redis redis-cli EXPIRE "user_features:$USER_ID" 3600 > /dev/null 2>&1 || true

    test_step "Redis can store user features" \
        "docker compose -f compose.dev.yaml exec -T redis redis-cli EXISTS 'user_features:$USER_ID' | grep -q '1'"
fi

echo ""
echo "Step 7: Data Quality Checks"
echo "------------------------------"

test_step "All ingestion batches have valid status" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c \"SELECT COUNT(*) FROM ingestion_batches WHERE status NOT IN ('running', 'completed', 'failed', 'partial')\" | grep -q '^ *0'"

test_step "No negative RFM values" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c 'SELECT COUNT(*) FROM user_features WHERE recency < 0 OR frequency < 0 OR monetary < 0' | grep -q '^ *0'"

test_step "All users have msisdn_hash" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c 'SELECT COUNT(*) FROM users WHERE msisdn_hash IS NULL' | grep -q '^ *0'"

test_step "All transactions have valid user_id" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c 'SELECT COUNT(*) FROM transactions t WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.user_id = t.user_id)' | grep -q '^ *0'"

echo ""
echo "Step 8: System Health Checks"
echo "------------------------------"

test_step "PostgreSQL has no zombie connections" \
    "docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -c 'SELECT COUNT(*) FROM pg_stat_activity WHERE state = '\''idle'\'' AND state_change < NOW() - INTERVAL '\''1 hour'\''' | grep -q '^ *0'"

test_step "Airflow scheduler is processing tasks" \
    "docker compose -f compose.dev.yaml logs --tail=50 airflow-scheduler | grep -q 'Processing file'"

test_step "No critical errors in data simulator logs" \
    "! docker compose -f compose.dev.yaml logs --tail=100 data-simulator | grep -E 'CRITICAL|FATAL'"

echo ""
echo "======================================"
echo "Test Summary"
echo "======================================"
echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Tests Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Data Pipeline Status:"
    echo "------------------------------"

    # Get statistics
    echo "Ingestion Batches:"
    docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c \
        "SELECT COUNT(*) as batches, SUM(records_processed) as total_records, SUM(records_failed) as failed_records FROM ingestion_batches;" || true

    echo ""
    echo "User Features:"
    docker compose -f compose.dev.yaml exec -T postgres psql -U postgres -d telco_recommender -c \
        "SELECT COUNT(*) as users_with_features, MAX(updated_at) as latest_update FROM user_features WHERE frequency > 0;" || true

    echo ""
    echo "Redis Cache:"
    CACHE_KEYS=$(docker compose -f compose.dev.yaml exec -T redis redis-cli KEYS "user_features:*" | wc -l)
    echo "Cached users: $CACHE_KEYS"

    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the errors above.${NC}"
    exit 1
fi
