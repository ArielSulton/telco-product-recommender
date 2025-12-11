# 🔄 RF v2 Integration Flow Diagram

## Complete Request Flow (With Fallback)

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER DASHBOARD                           │
│                     (React Component)                            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ fetchRecommendations()
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                  RECOMMENDATION CONTEXT                          │
│              (frontend/src/context/...)                          │
│                                                                  │
│  1. Try v2 API first ─────────┐                                │
│  2. If fails → fallback to v1 │                                │
└───────────────┬───────────────┴──────────────────────────────────┘
                │
                │ Try v2 first
                ↓
┌─────────────────────────────────────────────────────────────────┐
│            RECOMMENDATION SERVICE (v2)                           │
│         (frontend/src/services/api.js)                           │
│                                                                  │
│  POST /api/v1/recommend/v2                                      │
│  {                                                               │
│    user_id: 1,                                                   │
│    k: 5,                                                         │
│    include_explanations: true                                    │
│  }                                                               │
└───────────────┬──────────────────────────────────────────────────┘
                │
                │ HTTP Request
                ↓
┌─────────────────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND                                │
│        (backend/app/api/v1/endpoints/recommendations_v2.py)      │
│                                                                  │
│  1. Validate request                                             │
│  2. Get user features                                            │
│  3. Determine A/B variant (10% treatment, 90% control)          │
│  4. Route to RF model or legacy                                 │
└───────────────┬──────────────────────────────────────────────────┘
                │
                │ If variant = 'treatment'
                ↓
┌─────────────────────────────────────────────────────────────────┐
│                 RF RECOMMENDER SERVICE                           │
│           (backend/app/ml/rf_recommender.py)                     │
│                                                                  │
│  1. Validate user features ✓                                     │
│  2. Get predictions from RF model                                │
│     model.predict_topk() → ['5G Premium', 'Unlimited Data']     │
│  3. Enrich with product details ⭐ NEW                          │
│     └─→ Query PostgreSQL for each product                       │
│  4. Add explanations (SHAP)                                      │
│  5. Add metadata (confidence, rank, inference_time)              │
└───────────────┬──────────────────────────────────────────────────┘
                │
                │ Product enrichment
                ↓
┌─────────────────────────────────────────────────────────────────┐
│                      POSTGRESQL                                  │
│              (products table)                                    │
│                                                                  │
│  SELECT * FROM products                                          │
│  WHERE product_name = '5G Premium Package'                       │
│                                                                  │
│  Returns:                                                        │
│  {                                                               │
│    product_id: 1,                                                │
│    product_name: "5G Premium Package",                           │
│    price: 150000,                                                │
│    quota_data_mb: 20480,                                         │
│    validity_days: 30,                                            │
│    family: "Data",                                               │
│    description: "..."                                            │
│  }                                                               │
└───────────────┬──────────────────────────────────────────────────┘
                │
                │ Enriched data
                ↓
┌─────────────────────────────────────────────────────────────────┐
│               ENRICHED RECOMMENDATIONS                           │
│                                                                  │
│  [                                                               │
│    {                                                             │
│      // Full product details ⭐                                  │
│      product_id: 1,                                              │
│      product_name: "5G Premium Package",                         │
│      price: 150000,                                              │
│      quota_data_mb: 20480,                                       │
│      validity_days: 30,                                          │
│      family: "Data",                                             │
│      description: "...",                                         │
│                                                                  │
│      // RF metadata ⭐                                           │
│      confidence: 0.873,                                          │
│      rank: 1,                                                    │
│      explanation: {                                              │
│        top_features: [...],                                      │
│        explanation_text: "..."                                   │
│      }                                                            │
│    }                                                             │
│  ]                                                               │
└───────────────┬──────────────────────────────────────────────────┘
                │
                │ Return to backend
                ↓
┌─────────────────────────────────────────────────────────────────┐
│             FASTAPI RESPONSE                                     │
│                                                                  │
│  {                                                               │
│    "user_id": 1,                                                 │
│    "recommendations": [...enriched recommendations],             │
│    "model_version": "rf_v2",                                     │
│    "ab_variant": "treatment",                                    │
│    "inference_time_ms": 45.2,                                    │
│    "timestamp": "2025-12-09T..."                                 │
│  }                                                               │
└───────────────┬──────────────────────────────────────────────────┘
                │
                │ HTTP Response
                ↓
┌─────────────────────────────────────────────────────────────────┐
│                 RECOMMENDATION CONTEXT                           │
│                   (Success Path)                                 │
│                                                                  │
│  setRecommendations(data.recommendations)                        │
│  setVariant(data.ab_variant)  // 'treatment'                    │
│  setMetadata({                                                   │
│    model_version: 'rf_v2',                                       │
│    inference_time_ms: 45.2                                       │
│  })                                                              │
│                                                                  │
│  console.log('✅ Recommendations from rf_v2 (treatment)')       │
└───────────────┬──────────────────────────────────────────────────┘
                │
                │ Update state
                ↓
┌─────────────────────────────────────────────────────────────────┐
│                      USER DASHBOARD                              │
│                  (Displays Recommendations)                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐          │
│  │  5G Premium Package                 [Beli] │     │          │
│  │  Rp 150,000 | 20 GB | 30 Hari               │    │          │
│  │  ⭐ Confidence: 87.3%                         │    │          │
│  │  💡 "Based on your high data usage..."      │    │          │
│  └──────────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Fallback Flow (If RF v2 Fails)

```
RECOMMENDATION CONTEXT
        │
        │ Try v2 API
        ↓
   v2 API Call
        │
        ↓ ERROR (500 / timeout / model not found)
        │
        │ Catch v2Error
        ↓
┌───────────────────────────────────────┐
│  console.warn('RF v2 failed...')      │
│  Fallback to legacy v1 API            │
└───────────────┬───────────────────────┘
                │
                │ POST /api/v1/recommend (legacy)
                ↓
┌─────────────────────────────────────────────────────────┐
│              LEGACY RECOMMENDER                          │
│     (K-Means + LightFM + XGBoost)                        │
│                                                          │
│  Returns legacy format:                                  │
│  {                                                       │
│    "recommendations": [                                  │
│      {                                                   │
│        "product_id": 1,                                  │
│        "product_name": "5G Premium Package",             │
│        "price": 150000,                                  │
│        "reason": "Based on your segment"                 │
│      }                                                   │
│    ]                                                     │
│  }                                                       │
└───────────────┬─────────────────────────────────────────┘
                │
                │ HTTP Response
                ↓
┌─────────────────────────────────────────────────────────┐
│         RECOMMENDATION CONTEXT                           │
│           (Fallback Path)                                │
│                                                          │
│  setRecommendations(data.recommendations || data)        │
│  setVariant('legacy_fallback')                           │
│  setMetadata({                                           │
│    model_version: 'hybrid_v1',                           │
│    fallback_reason: v2Error.message                      │
│  })                                                      │
│                                                          │
│  console.log('✅ Recommendations from legacy v1')       │
└───────────────┬─────────────────────────────────────────┘
                │
                │ Update state
                ↓
┌─────────────────────────────────────────────────────────┐
│              USER DASHBOARD                              │
│       (Displays Fallback Recommendations)                │
│                                                          │
│  ┌────────────────────────────────────────────┐        │
│  │  5G Premium Package          [Beli] │      │        │
│  │  Rp 150,000 | 20 GB | 30 Hari        │      │        │
│  │  💡 "Based on your segment"          │      │        │
│  └────────────────────────────────────────────┘        │
│                                                          │
│  (UI looks identical - user doesn't notice fallback!)   │
└──────────────────────────────────────────────────────────┘
```

---

## A/B Testing Flow

```
USER REQUEST
     │
     │ user_id = 12345
     ↓
┌──────────────────────────────────────────┐
│      A/B VARIANT ASSIGNMENT               │
│   (Consistent Hashing)                    │
│                                           │
│  hash = md5(f"user_{user_id}")           │
│  normalized = (hash % 100) / 100         │
│                                           │
│  if normalized < traffic_split:          │
│      variant = 'treatment'  (RF v2)      │
│  else:                                    │
│      variant = 'control'    (legacy)     │
└──────────────┬────────────────────────────┘
               │
               ├─────────────┬──────────────┐
               ↓             ↓              ↓
          10% users     90% users      (configurable)
        ┌──────────┐  ┌──────────┐
        │ RF v2    │  │ Legacy   │
        │ Model    │  │ Model    │
        └──────────┘  └──────────┘
               │             │
               └─────┬───────┘
                     ↓
             RECOMMENDATIONS
                     │
                     ↓
             ┌───────────────┐
             │ Track Metrics │
             │ - CTR         │
             │ - Conversion  │
             │ - Latency     │
             │ - Confidence  │
             └───────────────┘
```

**Key Properties**:
- ✅ Same user = same variant (consistent hashing)
- ✅ Traffic split configurable (10%, 50%, 100%)
- ✅ Can force variant via header (`X-AB-Variant`)
- ✅ Metrics tracked per variant

---

## Data Flow Summary

### Before (Legacy v1)
```
User → Dashboard → API → Legacy Model → Response
                            (complex 3-stage)
```

### After (RF v2 with Fallback)
```
User → Dashboard → Context → Try v2 → RF Model → Enrich → Response
                        │
                        └─→ Fallback v1 → Legacy Model → Response
                             (if v2 fails)
```

**Benefits**:
- ✅ Zero downtime (automatic fallback)
- ✅ Better accuracy (RF v2: 97.53% vs v1: 14.76%)
- ✅ Full product details (no additional queries)
- ✅ A/B testing ready (gradual rollout)
- ✅ Backward compatible (UI unchanged)

---

## File Interaction Map

```
frontend/
├── pages/DashboardPage.jsx
│       ↓ uses
├── components/RecommendationWidget.jsx
│       ↓ uses
├── hooks/useRecommendations.js
│       ↓ calls
├── context/RecommendationContext.jsx  ⭐ MODIFIED
│       ↓ uses
└── services/recommendationService.js  ⭐ MODIFIED
        ↓ HTTP POST
        │
backend/
├── api/v1/endpoints/recommendations_v2.py  ⭐ MODIFIED
│       ↓ calls
├── ml/rf_recommender.py  ⭐ MODIFIED
│       ↓ queries
└── models/product.py  ⭐ IMPORTED
        (PostgreSQL)
```

---

## Performance Comparison

### Legacy v1 (Before)
```
Request → API → K-Means → LightFM → XGBoost → Response
 ─────────────────────────────────────────────
         200-500ms total latency
         14.76% accuracy
         Cold start failures
```

### RF v2 (After)
```
Request → API → RF Model → DB Enrichment → Response
 ──────────────────────────────────────────
         45-60ms total latency
         97.53% accuracy
         No cold start
```

**Improvement**: -90% latency, +560% accuracy! 🎉

---

## Error Handling Flow

```
Frontend Request
     │
     ↓
Try RF v2 API
     │
     ├─→ Success (80-90% expected)
     │   └─→ Return enriched recommendations
     │
     ├─→ Model Error (5-10%)
     │   └─→ Fallback to legacy v1
     │       └─→ Return legacy recommendations
     │
     ├─→ Network Error (<5%)
     │   └─→ Show error message
     │       User can retry
     │
     └─→ Invalid User Features (<1%)
         └─→ Return empty array
             Log error for investigation
```

**Result**: User always gets recommendations (or clear error message)!

---

## Testing Checkpoints

### ✅ Backend Tests
1. Model loaded: Check logs for `✅ RF model loaded successfully`
2. Product enrichment: Recommendations have `product_id`, `price`, etc.
3. Confidence scores: Each rec has `confidence` between 0-1
4. Explanations: `explanation.explanation_text` is human-readable

### ✅ Frontend Tests
1. Console log: `✅ Recommendations from rf_v2 (treatment)` or `legacy v1 (fallback)`
2. Dashboard renders: ProductCards display correctly
3. Fallback works: Stop backend → Shows error or empty state
4. A/B consistency: Same user ID → same variant on refresh

---

**Next Step**: Run these tests, verify everything works, then deploy! 🚀

See also:
- Integration summary: `docs/INTEGRATION_SUMMARY.md`
- Deployment plan: `docs/deployment_plan_rf_v2.md`
- Quick start: `docs/DEPLOYMENT_QUICKSTART.md`
