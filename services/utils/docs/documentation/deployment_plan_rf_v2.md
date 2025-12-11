# 🚀 RF Recommender v2.0 - Production Deployment Plan

## Executive Summary

**Project**: Replace legacy 3-stage hybrid recommender with Random Forest classifier
**Timeline**: 2-3 weeks (phased rollout)
**Risk Level**: Medium (A/B testing mitigates risk)
**Expected Impact**: 560% improvement in recommendation accuracy

**Performance Comparison**:
| Metric | Legacy (v1) | RF (v2) | Improvement |
|--------|-------------|---------|-------------|
| Accuracy | 14.76% | 97.53% | +560% |
| Hit Rate@3 | N/A | 87.24% | New metric |
| Inference Time | 200-500ms | <50ms | 4-10x faster |
| Cold Start | ❌ Problem | ✅ No problem | Critical fix |

---

## Phase 1: Model Export & Backend Integration (Week 1)

### Day 1-2: Model Export

**Objective**: Export trained model from notebook to production format

**Tasks**:
```bash
# 1. Run export script
cd ml/scripts
python export_rf_model.py

# Expected output:
# - backend/app/ml/models/rf_v2/rf_recommender.pkl
# - backend/app/ml/models/rf_v2/metadata.json
# - backend/app/ml/models/rf_v2/usage_example.py
# - MLflow registration (optional)
```

**Acceptance Criteria**:
- ✅ Model file < 50MB
- ✅ Inference test passes
- ✅ MLflow registration successful (if available)
- ✅ Metadata includes version, features, performance

### Day 3-4: Backend Integration

**Objective**: Integrate RF recommender into backend API

**Files Created**:
- `backend/app/ml/rf_recommender.py` - Service layer
- `backend/app/api/v1/endpoints/recommendations_v2.py` - API endpoints

**Testing**:
```bash
# 1. Start backend
cd backend
uvicorn app.main:app --reload

# 2. Test RF recommender endpoint
curl -X POST http://localhost:8000/api/v1/recommend/v2 \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "k": 5,
    "include_explanations": true
  }'

# Expected response:
# {
#   "user_id": 123,
#   "recommendations": [
#     {
#       "product": "5G Premium Package",
#       "confidence": 0.873,
#       "rank": 1,
#       "explanation": "..."
#     }
#   ],
#   "model_version": "rf_v2",
#   "ab_variant": "treatment",
#   "inference_time_ms": 45.2
# }
```

**Acceptance Criteria**:
- ✅ API responds in <100ms
- ✅ Returns top-K recommendations
- ✅ Confidence scores sum to ~1.0
- ✅ Explanations are human-readable
- ✅ Error handling works (invalid user, missing features)

### Day 5: Unit & Integration Tests

**Objective**: Ensure code quality and correctness

**Test Files**:
```python
# backend/tests/test_rf_recommender.py
import pytest
from app.ml.rf_recommender import RFRecommenderService

@pytest.fixture
def rf_recommender():
    return RFRecommenderService()

@pytest.mark.asyncio
async def test_rf_recommendations():
    """Test RF model inference."""
    recommender = rf_recommender()

    user_features = {
        'plan_type': 'Postpaid',
        'device_brand': 'Samsung',
        'avg_data_usage_gb': 12.5,
        'pct_video_usage': 0.65,
        'avg_call_duration': 15.2,
        'sms_freq': 25,
        'monthly_spend': 150000,
        'topup_freq': 4,
        'travel_score': 0.3,
        'complaint_count': 1
    }

    recommendations = await recommender.get_recommendations(
        user_id=123,
        user_features=user_features,
        k=5
    )

    # Assertions
    assert len(recommendations) <= 5
    assert all(0 <= r['confidence'] <= 1 for r in recommendations)
    assert recommendations[0]['rank'] == 1
    assert recommendations[0]['confidence'] >= recommendations[-1]['confidence']

@pytest.mark.asyncio
async def test_rf_inference_time():
    """Test inference performance."""
    import time
    recommender = rf_recommender()

    start = time.time()
    recommendations = await recommender.get_recommendations(...)
    elapsed = time.time() - start

    assert elapsed < 0.1  # < 100ms
```

**Run Tests**:
```bash
cd backend
pytest tests/test_rf_recommender.py -v --cov=app/ml
```

**Acceptance Criteria**:
- ✅ All tests pass
- ✅ Code coverage ≥80%
- ✅ No critical security issues (bandit scan)
- ✅ No performance regressions

---

## Phase 2: A/B Testing Setup (Week 2, Days 1-3)

### Day 1: A/B Test Configuration

**Objective**: Setup traffic splitting and variant assignment

**Configuration**:
```python
# backend/app/core/config.py
class Settings:
    # A/B Test Configuration
    AB_TEST_ENABLED: bool = True
    RF_TRAFFIC_SPLIT: float = 0.10  # 10% to RF model
    AB_TEST_VARIANT_ASSIGNMENT: str = "consistent_hash"  # or "random"
```

**Traffic Split Strategy**:
```yaml
Phase 1 (3 days):
  rf_traffic: 10%
  legacy_traffic: 90%
  monitoring: intensive
  rollback_threshold: error_rate > 1% OR latency_p95 > 200ms

Phase 2 (5 days):
  rf_traffic: 50%
  legacy_traffic: 50%
  monitoring: standard
  rollback_threshold: error_rate > 0.5% OR latency_p95 > 150ms

Phase 3 (7 days):
  rf_traffic: 100%
  legacy_traffic: 0%
  monitoring: standard
  rollback_threshold: error_rate > 0.5%
```

### Day 2: Monitoring & Alerting

**Objective**: Setup metrics collection and alerts

**Prometheus Metrics**:
```python
# backend/app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Recommendation metrics
recommendations_total = Counter(
    'recommendations_total',
    'Total recommendations served',
    ['model_version', 'variant']
)

recommendation_latency = Histogram(
    'recommendation_latency_seconds',
    'Recommendation inference time',
    ['model_version', 'variant']
)

recommendation_confidence = Histogram(
    'recommendation_confidence',
    'Top-1 recommendation confidence',
    ['model_version', 'variant']
)
```

**Grafana Dashboard**:
- Panel 1: Recommendations/min by variant
- Panel 2: Latency p50/p95/p99 by variant
- Panel 3: Error rate by variant
- Panel 4: Confidence distribution
- Panel 5: CTR comparison
- Panel 6: Conversion rate comparison

**Alerts** (PagerDuty/Slack):
```yaml
- name: RF_High_Error_Rate
  condition: error_rate{variant="treatment"} > 1%
  severity: critical
  action: rollback_to_control

- name: RF_High_Latency
  condition: latency_p95{variant="treatment"} > 200ms
  severity: warning
  action: investigate

- name: RF_Low_Confidence
  condition: avg(confidence{variant="treatment"}) < 0.3
  severity: warning
  action: review_model
```

### Day 3: Testing A/B Flow

**Test Scenarios**:

1. **Variant Assignment Consistency**:
```bash
# Same user should get same variant
curl -H "X-User-ID: 123" http://localhost:8000/api/v1/recommend/v2
# Check: ab_variant should be consistent across calls
```

2. **Force Variant**:
```bash
# Force control
curl -H "X-AB-Variant: control" http://localhost:8000/api/v1/recommend/v2

# Force treatment
curl -H "X-AB-Variant: treatment" http://localhost:8000/api/v1/recommend/v2
```

3. **Traffic Split**:
```bash
# Test 100 users, expect ~10 in treatment
for i in {1..100}; do
  curl -H "X-User-ID: $i" http://localhost:8000/api/v1/recommend/v2 | jq .ab_variant
done | sort | uniq -c
```

**Acceptance Criteria**:
- ✅ Variant assignment is consistent per user
- ✅ Traffic split matches configuration (±5%)
- ✅ Both variants return valid recommendations
- ✅ Metrics are collected correctly
- ✅ Alerts fire on test errors

---

## Phase 3: Production Rollout (Week 2, Days 4-7)

### Day 4: Initial Rollout (10%)

**Actions**:
```bash
# 1. Update traffic split to 10%
curl -X POST http://localhost:8000/api/v1/recommend/v2/rollout?traffic_split=0.10 \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 2. Monitor metrics
# - Check Grafana dashboard every hour
# - Review error logs
# - Compare CTR between variants
```

**Success Criteria**:
- ✅ Error rate < 1%
- ✅ Latency p95 < 150ms
- ✅ No customer complaints
- ✅ RF recommendations make business sense

**If Issues Detected**:
```bash
# Immediate rollback
curl -X POST http://localhost:8000/api/v1/recommend/v2/rollout?traffic_split=0.0 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Day 5-7: Monitor & Analyze

**Daily Tasks**:
1. Review Grafana dashboard
2. Check A/B test metrics:
```bash
curl http://localhost:8000/api/v1/recommend/v2/ab-metrics \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```
3. Analyze user feedback
4. Compare business metrics:
   - CTR (Click-Through Rate)
   - Conversion rate
   - ARPU (Average Revenue Per User)

**Expected Results** (after 3 days):
```yaml
Control (Legacy):
  recommendations_served: ~9000
  avg_confidence: 0.15
  ctr: 2.5%
  conversion_rate: 1.2%
  avg_latency_ms: 350

Treatment (RF):
  recommendations_served: ~1000
  avg_confidence: 0.87
  ctr: 8.5% (+240% vs control)
  conversion_rate: 4.1% (+242% vs control)
  avg_latency_ms: 45 (-87% vs control)
```

---

## Phase 4: Scale-Up (Week 3)

### Days 1-3: 50% Traffic

**Actions**:
```bash
# Increase to 50%
curl -X POST http://localhost:8000/api/v1/recommend/v2/rollout?traffic_split=0.50 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Monitoring Focus**:
- Database load (queries/sec)
- Redis cache hit rate
- Backend CPU/memory
- Network latency

**Expected Impact**:
- 5x increase in RF requests
- Database queries: +20%
- Redis gets: +50%
- Backend CPU: +10%

### Days 4-7: 100% Migration

**Actions**:
```bash
# Full migration
curl -X POST http://localhost:8000/api/v1/recommend/v2/rollout?traffic_split=1.0 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Final Validation**:
- ✅ All users get RF recommendations
- ✅ Legacy model can still be accessed (backup)
- ✅ Performance stable under full load
- ✅ Business metrics improved vs legacy

**Deprecation Plan**:
- Week 4: Monitor 100% RF traffic
- Week 5: Archive legacy model code
- Week 6: Remove legacy endpoints (mark deprecated)

---

## Rollback Plan

### Trigger Conditions

Rollback immediately if:
- ❌ Error rate > 5% for 5 minutes
- ❌ Latency p95 > 500ms for 10 minutes
- ❌ Redis/DB unavailable
- ❌ Critical bug discovered

Rollback gradually if:
- ⚠️ CTR decreases > 20% vs control
- ⚠️ Conversion rate decreases > 10%
- ⚠️ User complaints spike
- ⚠️ Model confidence suspiciously low

### Rollback Procedure

**Immediate (< 1 minute)**:
```bash
# 1. Set traffic to 0%
curl -X POST http://localhost:8000/api/v1/recommend/v2/rollout?traffic_split=0.0

# 2. Verify traffic shifted
curl http://localhost:8000/api/v1/recommend/v2/ab-metrics

# 3. Clear Redis cache (if corrupted)
redis-cli FLUSHDB

# 4. Restart backend (if needed)
docker compose restart backend
```

**Post-Rollback**:
1. Investigate root cause
2. Fix issue in RF model
3. Re-test in staging
4. Plan re-deployment

---

## Post-Deployment Tasks

### Week 4: Optimization

**Performance Tuning**:
- Optimize Redis caching strategy
- Pre-compute features for frequent users
- Batch inference for bulk recommendations
- Consider model quantization (reduce size)

**Feature Enhancements**:
- Add diversity to recommendations (prevent filter bubble)
- Implement re-ranking based on real-time signals
- Add contextual features (time-of-day, location)
- Support multi-arm bandit for exploration

### Week 5-6: Documentation & Knowledge Transfer

**Documentation**:
- Update API docs with RF endpoints
- Create runbook for operations team
- Document troubleshooting procedures
- Write blog post about migration

**Training**:
- Train backend team on RF architecture
- Train data science team on model updates
- Train support team on new recommendation logic

---

## Success Metrics

### Technical Metrics
- ✅ Latency p95 < 100ms (target: 50ms)
- ✅ Error rate < 0.1%
- ✅ Cache hit rate > 80%
- ✅ Model accuracy ≥ 95%

### Business Metrics
- ✅ CTR improvement: +100% vs legacy
- ✅ Conversion rate: +50% vs legacy
- ✅ ARPU increase: +3% vs legacy
- ✅ Customer satisfaction: No negative impact

### Operational Metrics
- ✅ Deployment time: < 2 weeks
- ✅ Zero-downtime migration: ✅
- ✅ Rollback capability: Tested ✅
- ✅ Team onboarding: Complete ✅

---

## Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| RF model errors | Low | High | A/B testing, instant rollback |
| Performance degradation | Medium | Medium | Load testing, caching strategy |
| Legacy code removal | Low | High | Keep legacy warm for 2 weeks |
| Data schema changes | Low | Medium | Backward compatible changes |
| User confusion | Low | Low | No UI changes, backend only |

---

## Team & Responsibilities

| Role | Responsibility | Owner |
|------|----------------|-------|
| **ML Engineer** | Model export, performance validation | Data Science Team |
| **Backend Engineer** | API integration, testing | Backend Team |
| **DevOps** | Deployment, monitoring, rollback | DevOps Team |
| **Product Manager** | Business metrics, user feedback | Product Team |
| **QA** | Test plan execution, validation | QA Team |

---

## Timeline Summary

```
Week 1: Development & Testing
├─ Day 1-2: Model export
├─ Day 3-4: Backend integration
└─ Day 5: Unit tests

Week 2: A/B Testing
├─ Day 1: Setup A/B infrastructure
├─ Day 2: Monitoring & alerts
├─ Day 3: Testing
├─ Day 4: Initial rollout (10%)
└─ Day 5-7: Monitor & analyze

Week 3: Scale-Up
├─ Day 1-3: 50% traffic
└─ Day 4-7: 100% migration

Week 4+: Optimization & Maintenance
```

---

## Approval Checklist

Before proceeding to production:

- [ ] Model exported and validated
- [ ] Backend integration complete
- [ ] Unit tests pass (coverage ≥80%)
- [ ] Integration tests pass
- [ ] Load tests pass (1000 req/s)
- [ ] Monitoring dashboard ready
- [ ] Alerts configured
- [ ] Rollback procedure tested
- [ ] Team trained
- [ ] Documentation complete
- [ ] Stakeholder sign-off

**Sign-off Required**:
- [ ] Tech Lead: _______________
- [ ] Product Manager: _______________
- [ ] Engineering Manager: _______________

---

## Contact & Support

**Deployment Team**:
- ML Engineer: [Contact]
- Backend Lead: [Contact]
- DevOps: [Contact]

**Escalation**:
- On-call engineer: [PagerDuty rotation]
- Emergency: [Slack #incidents channel]

**Documentation**:
- API Docs: http://localhost:8000/docs
- Grafana: http://localhost:3000
- MLflow: http://localhost:5000
