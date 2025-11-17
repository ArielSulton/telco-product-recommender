# Demo ML Training - Quick Start

Simple ML training script for bootcamp demonstration.

## Overview

This script trains a baseline recommendation model and registers it to MLflow for the bootcamp demo. It's designed to be simple and fast - perfect for demonstrating the end-to-end ML workflow without complex data pipelines.

## What It Does

1. ✅ Loads customer data from CSV (10,000 customers)
2. ✅ Creates 5,000 synthetic transactions (simulates user-product interactions)
3. ✅ Trains TopPopular baseline recommender
4. ✅ Registers model to MLflow with "Production" stage
5. ✅ Tests recommendations

## Prerequisites

```bash
# 1. Start Docker services (PostgreSQL, Redis, MLflow)
docker compose -f compose.dev.yaml up -d postgres redis mlflow

# 2. Verify MLflow is running
curl http://localhost:5000/health
```

## Running the Training

**Option 1: Direct Python**
```bash
# From project root
python scripts/train_demo_model.py
```

**Option 2: From Docker (recommended for consistency)**
```bash
# Execute in backend container
docker exec -it telco-backend-dev python /app/scripts/train_demo_model.py
```

## Expected Output

```
============================================================
Starting Demo ML Training
============================================================
INFO - Loading customer data from ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv
INFO - Loaded 10000 customers
INFO - Creating 5000 synthetic transactions
INFO - Created 5000 transactions
INFO - Unique products: 4
INFO - Unique users: 4892
INFO - Training TopPopular baseline model
INFO - TopPopular fitted. Global items: 4
INFO - Segments: 0
INFO - Model statistics: {'n_products': 4, 'mean_popularity': 1250.0, ...}
INFO - Registering model to MLflow experiment: telco-recommender-demo
INFO - Registering model: baseline-recommender
INFO - Promoting version 1 to Production stage
INFO - ✅ Model promoted to Production stage (version 1)
============================================================
✅ Demo ML Training Complete
Run ID: abc123...
Model: baseline-recommender (Production stage)
============================================================

Testing recommendation:
Top 5 popular products: ['PROD_DATA_001', 'PROD_DEVICE_001', 'PROD_TOPUP_001', 'PROD_GEN_001']
```

## Verify in MLflow UI

1. Open MLflow UI: http://localhost:5000
2. Check experiment: "telco-recommender-demo"
3. Verify model: "baseline-recommender" (Production stage)

## Product Mapping

The script maps customer target offers to product IDs:

| Target Offer | Product ID |
|--------------|------------|
| General Offer | PROD_GEN_001 |
| Top-up Promo | PROD_TOPUP_001 |
| Device Upgrade Offer | PROD_DEVICE_001 |
| Data Booster | PROD_DATA_001 |

## Verifying Backend Integration

After training, verify the backend can load the model:

```bash
# Restart backend to reload models
docker compose -f compose.dev.yaml restart backend

# Check logs for model loading
docker logs telco-backend-dev --tail 50

# Expected log:
# ✅ ML models loaded successfully
#   - Baseline: ✓ (baseline-recommender v1)
```

## Testing Recommendations

```bash
# Test recommendation endpoint
curl -X POST http://localhost:8000/api/v1/recommend \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{
    "user_id": "C00001",
    "limit": 5
  }'
```

Expected response:
```json
{
  "recommendations": [
    {
      "product_id": "PROD_DATA_001",
      "score": 0.95,
      "reason": "Popular product"
    },
    ...
  ]
}
```

## Troubleshooting

**Error: MLflow connection refused**
- Solution: Ensure MLflow is running: `docker compose -f compose.dev.yaml up -d mlflow`
- Verify: `curl http://localhost:5000/health`

**Error: CSV file not found**
- Solution: Ensure you're running from project root
- Check path: `ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv`

**Error: Module not found**
- Solution: Install dependencies: `pip install -r backend/requirements.txt`
- Or use Docker: `docker exec -it telco-backend-dev python /app/scripts/train_demo_model.py`

## For Bootcamp Demo

This is a **simplified training script** designed for demonstration purposes:

✅ **Included**:
- Basic model training
- MLflow integration
- Simple product recommendations
- Fast execution (<30 seconds)

❌ **Not Included** (Production features):
- Complex feature engineering
- Multiple model training (K-Means, LightFM, XGBoost)
- Hyperparameter tuning
- Cross-validation
- Advanced evaluation metrics

For production ML training, see: `infrastructure/airflow/dags/model_retraining.py`
