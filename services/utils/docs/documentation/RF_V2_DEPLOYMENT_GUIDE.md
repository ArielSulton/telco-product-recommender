# RF v2 Deployment & Testing Guide

**Complete deployment and testing procedures for RandomForest v2 recommendation system.**

---

## 📋 **Pre-Deployment Checklist**

### Database Migrations
- [x] `01_init.sql` - Core tables (users, products, transactions, events)
- [x] `02_create_users_table.sql` - Authentication table (app_users)
- [x] `03_add_rf_v2_features.sql` - **NEW** RF v2 behavioral features
- [x] `04_sync_transactions_purchases.sql` - **NEW** Table synchronization

### Backend Code
- [x] `backend/app/ml/rf_model.py` - RFRecommender class (126 lines)
- [x] `backend/app/ml/rf_recommender.py` - RF service with model loading
- [x] `backend/app/api/v1/endpoints/purchases.py` - Feature inference & updates
- [x] `backend/app/api/v1/endpoints/recommendations_v2.py` - RF v2 API endpoint

### Airflow DAGs
- [x] `infrastructure/airflow/dags/rf_v2_retraining.py` - **NEW** Weekly retraining
- [x] Drift detection (PSI threshold: 0.15)
- [x] MLflow integration (experiment: rf_v2_retraining)

### Model Artifacts
- [x] `backend/app/ml/models/rf_v2/rf_recommender.pkl` - Exported model (39MB)
- [x] `backend/app/ml/models/rf_v2/metadata.json` - Model metadata
- [x] `backend/app/ml/models/rf_v2/usage_example.py` - Code example

### Frontend Integration
- [x] `frontend/src/services/recommendationService.js` - getRecommendationsV2()
- [x] `frontend/src/context/RecommendationContext.jsx` - v2 with v1 fallback

---

## 🚀 **Deployment Steps**

### Step 1: Fresh Database Deployment

```bash
# Start PostgreSQL container
docker compose -f compose.dev.yaml up -d postgres

# Verify migrations ran in order
docker compose -f compose.dev.yaml logs postgres | grep "✅"

# Expected output:
# ✅ Database schema initialized successfully
# ✅ RF v2 database migration completed successfully
# ✅ Purchases <-> Transactions sync configuration complete
```

**Verify Schema:**
```sql
-- Connect to database
docker exec -it asah-capstone-postgres psql -U postgres -d telco_recommender

-- Check app_users has behavioral features
\d app_users

-- Expected columns (12 new):
-- plan_type, device_brand, avg_data_usage_gb, pct_video_usage,
-- avg_call_duration, sms_freq, monthly_spend, topup_freq,
-- travel_score, complaint_count, last_purchase_date, total_purchases

-- Check purchases table exists
\d purchases

-- Check sync trigger exists
SELECT tgname, tgenabled FROM pg_trigger WHERE tgrelid = 'purchases'::regclass;

-- Expected: trigger_sync_purchase_to_transaction | O (enabled)
```

---

### Step 2: Backend Service Deployment

```bash
# Start backend with model loading
docker compose -f compose.dev.yaml up -d backend

# Watch logs for model loading
docker compose -f compose.dev.yaml logs -f backend

# Expected output:
# INFO: Loading RF v2 model from models/rf_v2/rf_recommender.pkl
# INFO: RF v2 model loaded successfully - Version: 2.0.0
# INFO: Model metadata: 21 features, 10 classes, accuracy: 0.9753
```

**Verify API Health:**
```bash
curl http://localhost:8000/health

# Expected:
# {"status":"healthy","models":{"rf_v2":"loaded"}}
```

---

### Step 3: Test Purchase → Feature Update Flow

**Create Test User:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "081234567890",
    "password": "test123",
    "name": "Test User RF v2"
  }'

# Expected:
# {"id":"...","phone":"081234567890","name":"Test User RF v2","balance":100000}
```

**Login to Get Token:**
```bash
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"081234567890","password":"test123"}' \
  | jq -r '.access_token')

echo "Token: $TOKEN"
```

**Make Purchase (Streaming Pack):**
```bash
curl -X POST http://localhost:8000/api/v1/purchases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "PKG_STREAM_10GB",
    "payment_method": "pulsa"
  }'

# Expected logs in backend:
# 📊 Inferred features for 'Streaming Partner Pack 10GB': data=10.0GB, video=80%
# ✅ Updated user features with behavioral inference
# ✅ Invalidated cache for user ... after purchase
```

**Verify Feature Update:**
```sql
-- In PostgreSQL
SELECT
    phone,
    plan_type,
    device_brand,
    avg_data_usage_gb,
    pct_video_usage,
    monthly_spend,
    topup_freq,
    last_purchase_date,
    total_purchases
FROM app_users
WHERE phone = '081234567890';

-- Expected values:
-- avg_data_usage_gb: 10.0 (inferred from 10GB quota)
-- pct_video_usage: 0.8 (streaming pack = 80% video)
-- monthly_spend: 150000 (price of streaming pack)
-- topup_freq: 1 (first purchase)
-- total_purchases: 1
```

---

### Step 4: Test RF v2 Recommendations

**Get Recommendations (Before Purchase):**
```bash
curl -X POST http://localhost:8000/api/v1/recommend/v2 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"<user_id>","k":5}'

# Expected: General offers for new user
```

**Get Recommendations (After Purchase):**
```bash
curl -X POST http://localhost:8000/api/v1/recommend/v2 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"<user_id>","k":5}'

# Expected: Streaming-related recommendations!
# - "Data Booster 15GB" (upgrade for heavy data user)
# - "Streaming Partner Pack Plus" (upsell)
# - "YouTube Premium Bundle" (video-centric)
```

**Verify Explanation Quality:**
```json
{
  "recommendations": [
    {
      "product_name": "Data Booster 15GB",
      "confidence": 0.6421,
      "explanation": "We recommend this based on your data usage of 10.0 GB and video streaming of 80%"
    }
  ]
}
```

---

### Step 5: Test Table Synchronization

**Verify Sync Trigger:**
```sql
-- Check purchases table
SELECT COUNT(*) FROM purchases WHERE user_id = '<user_id>';
-- Expected: 1

-- Check transactions table (should have synced record)
SELECT COUNT(*) FROM transactions WHERE user_id = '<user_id>';
-- Expected: 1

-- Check discrepancy report
SELECT * FROM v_purchase_discrepancy_report;
-- Expected: 0 discrepancies
```

---

### Step 6: Deploy Airflow DAG

```bash
# Start Airflow
docker compose -f compose.dev.yaml up -d airflow-webserver airflow-scheduler

# Access Airflow UI
open http://localhost:8080
# Login: admin / admin

# Verify DAG appears in UI
# DAGs -> rf_v2_retraining
# Status: Should be visible and paused

# Enable DAG
# Toggle ON in Airflow UI
```

**Manual Trigger Test:**
```bash
# Trigger DAG manually
curl -X POST http://localhost:8080/api/v1/dags/rf_v2_retraining/dagRuns \
  -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"conf":{}}'

# Watch logs
docker compose -f compose.dev.yaml logs -f airflow-scheduler

# Expected stages:
# 1. check_feature_drift → SKIP (not enough data yet)
# 2. skip_retraining → SUCCESS
```

---

### Step 7: Test MLflow Integration

```bash
# Access MLflow UI
open http://localhost:5000

# Verify experiment exists
# Experiments -> rf_v2_retraining

# After manual training:
# - Run should appear with metrics
# - Model should be registered in "Models" tab
# - Model name: rf_v2_classifier
```

---

## 🧪 **End-to-End Test Scenario**

### Scenario: User Journey with Real-Time Recommendations

**User Profile:**
- Name: "Heavy Streamer"
- Behavior: Watches YouTube/Netflix heavily

**Test Flow:**

1. **Register User**
   ```bash
   POST /api/v1/auth/register
   # Creates user with default features (avg_data_usage_gb=5.0, pct_video_usage=0.4)
   ```

2. **Purchase 1: Streaming Partner Pack 10GB (Rp 150,000)**
   ```bash
   POST /api/v1/purchases
   # Backend infers:
   # - avg_data_usage_gb = 10.0
   # - pct_video_usage = 0.8 (streaming = high video)
   # - monthly_spend = 150000
   # - topup_freq = 1
   ```

3. **Get Recommendations (After Purchase 1)**
   ```bash
   POST /api/v1/recommend/v2
   # Expected recommendations:
   # 1. Data Booster 15GB (upgrade for heavy data)
   # 2. Streaming Partner Pack Plus (upsell)
   # 3. YouTube Premium Bundle (video-centric)
   ```

4. **Purchase 2: Data Booster 15GB (Rp 180,000)**
   ```bash
   POST /api/v1/purchases
   # Backend updates:
   # - avg_data_usage_gb = 12.5 (increased)
   # - monthly_spend = 330000 (150k + 180k)
   # - topup_freq = 2
   ```

5. **Get Recommendations (After Purchase 2)**
   ```bash
   POST /api/v1/recommend/v2
   # Expected recommendations:
   # 1. Data Booster 25GB (even higher quota)
   # 2. Unlimited Streaming Pack (premium)
   # 3. Family Plan 30GB (shared quota)
   ```

**Success Criteria:**
- ✅ Recommendations **change** after each purchase
- ✅ Recommendations **align** with user behavior (streaming → data-centric offers)
- ✅ Explanations **reference** updated features (data usage, video percentage)

---

## 📊 **Monitoring & Validation**

### Key Metrics to Track

**Backend Logs:**
```bash
# Purchase feature inference
grep "📊 Inferred features" backend.log

# Feature update success
grep "✅ Updated user features" backend.log

# Cache invalidation
grep "✅ Invalidated cache" backend.log
```

**Database Queries:**
```sql
-- Users with behavioral features
SELECT COUNT(*) FROM app_users WHERE total_purchases > 0;

-- Recent purchases (last 24h)
SELECT COUNT(*) FROM purchases WHERE purchase_date >= NOW() - INTERVAL '1 day';

-- Sync health
SELECT * FROM v_purchase_discrepancy_report;

-- Feature distribution
SELECT
    AVG(avg_data_usage_gb) as avg_data,
    AVG(pct_video_usage) as avg_video,
    AVG(monthly_spend) as avg_spend
FROM app_users WHERE total_purchases > 0;
```

**Airflow Monitoring:**
```sql
-- DAG run status
SELECT dag_id, state, execution_date
FROM dag_run
WHERE dag_id = 'rf_v2_retraining'
ORDER BY execution_date DESC
LIMIT 5;
```

**MLflow Metrics:**
- Validation Accuracy ≥ 75%
- Top-5 Accuracy ≥ 90%
- Feature Drift PSI < 0.15 (stable)

---

## 🚨 **Troubleshooting**

### Issue 1: Model Not Loading

**Symptom:**
```
ERROR: FileNotFoundError: rf_recommender.pkl not found
```

**Fix:**
```bash
# Re-export model
cd services/utils/tests/scripts
python3 export_rf_model.py

# Verify export
ls -lh /home/.../backend/app/ml/models/rf_v2/
# Should see: rf_recommender.pkl (39MB)
```

---

### Issue 2: Purchase Feature Update Fails

**Symptom:**
```
WARNING: Failed to update user features: column "avg_data_usage_gb" does not exist
```

**Fix:**
```sql
-- Run migration manually
\i infrastructure/postgres/init/03_add_rf_v2_features.sql
```

---

### Issue 3: Recommendations Not Changing

**Symptom:**
- User makes purchase
- Recommendations identical before/after

**Debug:**
```sql
-- Check if features updated
SELECT avg_data_usage_gb, pct_video_usage, monthly_spend
FROM app_users WHERE phone = '<phone>';

-- Check cache invalidation
-- Redis CLI:
redis-cli
> KEYS recommendations:*
> KEYS user_features:*
# Should be empty after purchase
```

**Fix:**
```bash
# Manually clear cache
redis-cli FLUSHDB

# Retry recommendation request
```

---

### Issue 4: Airflow DAG Not Appearing

**Symptom:**
- rf_v2_retraining DAG not visible in Airflow UI

**Fix:**
```bash
# Check file exists
ls infrastructure/airflow/dags/rf_v2_retraining.py

# Check Airflow logs for syntax errors
docker compose logs airflow-scheduler | grep ERROR

# Restart Airflow
docker compose restart airflow-scheduler airflow-webserver
```

---

## ✅ **Deployment Validation Checklist**

### Database
- [ ] All 4 migration scripts executed
- [ ] `app_users` has 12 behavioral feature columns
- [ ] `purchases` table created
- [ ] Sync trigger enabled
- [ ] Discrepancy report shows 0 issues

### Backend
- [ ] RF v2 model loaded successfully
- [ ] API health check passes
- [ ] Purchase endpoint returns 200
- [ ] Feature inference logs present
- [ ] Cache invalidation logs present

### Frontend
- [ ] Recommendation page loads
- [ ] API calls use v2 endpoint (10% traffic)
- [ ] Fallback to v1 works on error

### Airflow
- [ ] DAG visible in UI
- [ ] Manual trigger test passes
- [ ] Drift detection task runs
- [ ] MLflow experiment created

### Integration
- [ ] Purchase creates record in both tables
- [ ] User features update after purchase
- [ ] Recommendations change based on purchases
- [ ] Explanations reference updated features

---

## 🎯 **Success Metrics**

### Functional Metrics
- **Feature Update Rate**: 100% of purchases trigger feature updates
- **Cache Invalidation Rate**: 100% of purchases clear cache
- **Sync Success Rate**: 100% of purchases replicate to transactions table

### Performance Metrics
- **Purchase API Latency**: <200ms (p95)
- **Recommendation API Latency**: <150ms with cache, <500ms cold start
- **Feature Inference Time**: <10ms

### Business Metrics
- **RF v2 Adoption**: 10% of traffic (A/B test)
- **Recommendation Relevance**: CTR uplift ≥ 10% vs baseline
- **Model Accuracy**: ≥ 75% validation accuracy, ≥ 90% top-5 accuracy

---

## 📝 **Next Steps After Deployment**

1. **Monitor Production for 1 Week**
   - Track purchase volume
   - Monitor feature update success rate
   - Check cache hit/miss ratio
   - Validate recommendation quality

2. **Run First Scheduled Retraining**
   - Wait for Sunday 3 AM (weekly schedule)
   - Verify DAG executes successfully
   - Check MLflow for new model version
   - Validate performance metrics

3. **Analyze A/B Test Results**
   - Compare RF v2 (10%) vs Hybrid v1 (90%)
   - Metrics: CTR, conversion rate, ARPU increase
   - Decision: Scale up RF v2 traffic if successful

4. **Optimize Model**
   - Tune temperature scaling
   - Experiment with different RF hyperparameters
   - Add more product classes if needed

---

## 🔗 **References**

- **Export Script**: `services/utils/tests/scripts/export_rf_model.py`
- **Backend Service**: `backend/app/ml/rf_recommender.py`
- **API Endpoint**: `backend/app/api/v1/endpoints/recommendations_v2.py`
- **Airflow DAG**: `infrastructure/airflow/dags/rf_v2_retraining.py`
- **Migration SQLs**: `infrastructure/postgres/init/03_*.sql`, `04_*.sql`
- **Integration Analysis**: Session summary (see worklog)

---

**Deployment Date**: 2025-01-20
**Version**: RF v2.0.0
**Model Accuracy**: 97.53% (notebook), 75%+ target (production)
**Status**: ✅ Ready for Production
