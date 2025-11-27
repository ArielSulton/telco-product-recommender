# 📊 **Complete Data Flow: Mining → Recommendation**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          1. DATA MINING & PREPARATION                            │
└─────────────────────────────────────────────────────────────────────────────────┘

Raw CSV: ac-01_telco_customer_behavior_mock_data.csv
├─ user_id: 123e4567-e89b-12d3-a456-426614174000
├─ product_id: PKT001, PKT002, ...
├─ purchase_count: 5, 3, 1, ...
├─ quota_usage_mb: 8500, 2300, ...
├─ device_type: Samsung, iPhone, ...
└─ created_at: timestamps

                    ↓ Data Simulator (daily generation)

┌────────────────────────────────────────────────────────────────┐
│  PostgreSQL Database                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐      │
│  │  products    │  │  user_events │  │  transactions  │      │
│  │              │  │              │  │                │      │
│  │ PKT001-PKT50 │  │ view, click  │  │ purchase data  │      │
│  └──────────────┘  └──────────────┘  └────────────────┘      │
└────────────────────────────────────────────────────────────────┘

                    ↓ Feature Engineering

┌────────────────────────────────────────────────────────────────┐
│  Feature Matrix (per user)                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ purchase_frequency: 12 transactions/month               │  │
│  │ avg_quota_mb: 8500 MB                                   │  │
│  │ preferred_family: "Gaming", "Streaming"                 │  │
│  │ price_sensitivity: 0.3 (low = willing to pay more)     │  │
│  │ device_type: "Samsung"                                  │  │
│  │ recency_days: 7 (last purchase 7 days ago)            │  │
│  └─────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────┐
│                       2. ML PIPELINE (4 STAGES)                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

STAGE 1: USER SEGMENTATION (K-Means Clustering)
─────────────────────────────────────────────────
Input: User features (purchase_freq, avg_quota, price_sensitivity)

    All Users (10,000)
         │
         ├──→ Segment 0: Heavy Users (20%)
         │    • High purchase_freq (>15/month)
         │    • High quota usage (>10GB)
         │    • Low price sensitivity
         │
         ├──→ Segment 1: Moderate Users (50%)
         │    • Medium purchase_freq (5-15/month)
         │    • Medium quota (3-10GB)
         │    • Medium price sensitivity
         │
         └──→ Segment 2: Light Users (30%)
              • Low purchase_freq (<5/month)
              • Low quota (<3GB)
              • High price sensitivity

User X → Features → K-Means → Segment 1 (Moderate User)


STAGE 2: CANDIDATE GENERATION (LightFM Collaborative Filtering)
────────────────────────────────────────────────────────────────
Input: User X (segment 1) + Product Catalog (50 products)

    User-Item Matrix (Sparse)
    ┌─────────────────────────────────────┐
    │       PKT001 PKT002 PKT003 ... PKT50│
    │ U001    1      0      1    ...  0   │  1 = purchased
    │ U002    0      1      0    ...  1   │  0 = not purchased
    │ ...    ...    ...    ...   ... ...  │
    │ UserX   ?      ?      ?    ...  ?   │  ← Predict scores
    └─────────────────────────────────────┘

    LightFM Model (Hybrid: Collaborative + Content-based)
         │
         ├─ Collaborative Signal: "Users similar to User X liked PKT015"
         ├─ Content Signal: "User X likes Gaming, PKT015 is Gaming package"
         └─ Combined Score: 0.85 for PKT015

Output: Top 50 candidates with CF scores
    PKT015: 0.85  ← High match (gaming user + gaming package)
    PKT022: 0.78
    PKT033: 0.72
    ...
    PKT007: 0.45  ← Lower match


STAGE 3: RE-RANKING (XGBoost Learning-to-Rank)
───────────────────────────────────────────────
Input: 50 candidates + Rich features

For each candidate:
    ┌─────────────────────────────────────────────┐
    │ User Features:                              │
    │  • segment: 1                               │
    │  • purchase_freq: 12                        │
    │  • avg_quota_mb: 8500                       │
    │                                             │
    │ Product Features:                           │
    │  • product_family: "Gaming"                 │
    │  • quota_data_mb: 10240 (10GB)             │
    │  • price: 85000                             │
    │  • validity_days: 30                        │
    │                                             │
    │ Interaction Features:                       │
    │  • cf_score: 0.85 (from LightFM)           │
    │  • price_match: 0.9 (fits budget)          │
    │  • quota_match: 0.95 (matches usage)       │
    └─────────────────────────────────────────────┘
              ↓ XGBoost Model
         Final Score: 0.92

Output: Re-ranked top 20
    PKT015: 0.92  ← Best overall match
    PKT033: 0.88
    PKT022: 0.85
    ...


STAGE 4: DIVERSIFICATION (MMR - Maximal Marginal Relevance)
────────────────────────────────────────────────────────────
Input: Top 20 ranked candidates
Goal: Balance relevance vs. diversity

Before MMR (all similar):
    1. PKT015: Gaming 10GB (0.92)
    2. PKT016: Gaming 12GB (0.88)  ← Too similar to #1
    3. PKT017: Gaming 8GB (0.85)   ← Too similar to #1
    4. PKT022: Streaming 15GB (0.82)

MMR Algorithm (λ = 0.7):
    Score = λ × Relevance - (1-λ) × MaxSimilarity

    For PKT016:
    • Relevance: 0.88
    • Similarity to selected: 0.95 (very similar to PKT015)
    • MMR Score: 0.7×0.88 - 0.3×0.95 = 0.616 - 0.285 = 0.331 ← Penalized!

    For PKT022:
    • Relevance: 0.82
    • Similarity to selected: 0.2 (different family)
    • MMR Score: 0.7×0.82 - 0.3×0.2 = 0.574 - 0.06 = 0.514 ← Better!

After MMR (diverse):
    1. PKT015: Gaming 10GB (0.92)         ← High quota gaming
    2. PKT022: Streaming 15GB (0.82)      ← Different family
    3. PKT033: Budget 3GB (0.75)          ← Different price point
    4. PKT041: Unlimited Night (0.71)     ← Different benefit type


┌─────────────────────────────────────────────────────────────────────────────────┐
│                         3. CACHING & DELIVERY                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ↓ Final Recommendations

┌────────────────────────────────────────────────────────────────┐
│  Redis Cache (3-layer strategy)                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ Key: recommendations:user-id:limit                       │ │
│  │ Value: {                                                 │ │
│  │   "recommendations": [                                   │ │
│  │     { "product_id": "PKT015", "score": 0.92, ... },     │ │
│  │     { "product_id": "PKT022", "score": 0.82, ... },     │ │
│  │     ...                                                  │ │
│  │   ],                                                     │ │
│  │   "metadata": { "segment": 1, "cached": true }          │ │
│  │ }                                                        │ │
│  │ TTL: 300 seconds (5 minutes)                            │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘

                    ↓ API Response

┌────────────────────────────────────────────────────────────────┐
│  GET /api/v1/recommendations?user_id=X&limit=5                 │
│                                                                 │
│  Response:                                                      │
│  {                                                              │
│    "recommendations": [                                         │
│      {                                                          │
│        "product_id": "PKT015",                                 │
│        "product_name": "Paket Gaming Pro",                     │
│        "quota_data_mb": 10240,                                 │
│        "price": 85000,                                         │
│        "score": 0.92,                                          │
│        "reason": "Based on your gaming usage pattern"          │
│      },                                                         │
│      ...                                                        │
│    ],                                                           │
│    "metadata": {                                               │
│      "user_segment": 1,                                        │
│      "total_candidates": 50,                                   │
│      "cached": true                                            │
│    }                                                            │
│  }                                                              │
└────────────────────────────────────────────────────────────────┘

                    ↓ Frontend Display

┌────────────────────────────────────────────────────────────────┐
│  DASHBOARD - Personalized Recommendations                      │
│                                                                 │
│  🎮 Paket Gaming Pro                                           │
│     10 GB • 30 Days • Rp 85,000                               │
│     Match: 92%                                                 │
│     💡 Based on your gaming usage pattern                     │
│     [View Detail →]                                            │
│                                                                 │
│  📺 Paket Streaming Max                                        │
│     15 GB • 30 Days • Rp 100,000                              │
│     Match: 82%                                                 │
│     💡 Perfect for your video streaming habits                │
│     [View Detail →]                                            │
└────────────────────────────────────────────────────────────────┘
```

---

## 🎯 **Contoh Konkret: User X Journey**

```
USER X PROFILE:
├─ user_id: 550e8400-e29b-41d4-a716-446655440000
├─ purchase_frequency: 12 transactions/month
├─ avg_quota_usage: 8500 MB (8.5 GB)
├─ preferred_families: ["Gaming", "Streaming"]
├─ device: "Samsung Galaxy S21"
├─ price_budget: 50,000 - 100,000
└─ last_purchase: "PKT015" (Gaming 10GB) - 7 days ago

STEP-BY-STEP REASONING:
═══════════════════════════════════════════════════════════════

1️⃣ SEGMENTATION (K-Means)
   Features → [purchase_freq=12, avg_quota=8500, price_sens=0.3]
   K-Means Prediction → Segment 1 (Moderate User)

   Why Segment 1?
   ✓ 12 trans/month = moderate frequency (not light, not heavy)
   ✓ 8.5 GB usage = moderate quota
   ✓ 0.3 sensitivity = willing to pay moderate prices

2️⃣ CANDIDATE GENERATION (LightFM)

   Similar Users in Segment 1:
   ├─ User A: Likes PKT015, PKT022, PKT033
   ├─ User B: Likes PKT015, PKT041, PKT007
   └─ User C: Likes PKT022, PKT033, PKT015

   Collaborative Filtering Logic:
   "Users similar to User X (same segment, similar behavior)
    bought PKT015, PKT022, PKT033 → High CF scores"

   Content-Based Logic:
   "User X profile: Gaming + Streaming
    PKT015 = Gaming package → Content match!"

   Top Candidates (CF scores):
   ├─ PKT015: 0.87 (Gaming 10GB) ← Collaborative + Content match
   ├─ PKT022: 0.81 (Streaming 15GB)
   ├─ PKT033: 0.76 (Budget 5GB)
   ├─ PKT041: 0.72 (Unlimited Night)
   └─ ... 46 more

3️⃣ RE-RANKING (XGBoost)

   For PKT015:
   ┌─────────────────────────────────────┐
   │ Input Features:                     │
   │ • cf_score: 0.87                   │
   │ • quota_match: (10240/8500) = 1.2  │ ← Perfect size!
   │ • price_match: 85000 in budget ✓   │
   │ • recency: bought similar 7d ago   │ ← Repeat pattern
   │ • family_match: "Gaming" = 1.0     │
   └─────────────────────────────────────┘
            ↓ XGBoost Gradient Boosting
   Final Score: 0.94 ← Boosted from 0.87!

   Why boosted?
   ✓ Quota perfectly matches usage (1.2x headroom)
   ✓ Price within budget
   ✓ User bought similar package recently (repeat customer)
   ✓ Content match (Gaming = Gaming)

   For PKT033 (Budget 5GB):
   ┌─────────────────────────────────────┐
   │ • cf_score: 0.76                   │
   │ • quota_match: (5120/8500) = 0.6   │ ← Too small!
   │ • price_match: 35000 ✓ (but cheap) │
   └─────────────────────────────────────┘
   Final Score: 0.68 ← Penalized (quota too low)

4️⃣ DIVERSIFICATION (MMR)

   Top 5 after ranking:
   1. PKT015: Gaming 10GB (0.94)
   2. PKT016: Gaming 12GB (0.89)  ← Too similar!
   3. PKT017: Gaming 8GB (0.86)   ← Too similar!
   4. PKT022: Streaming 15GB (0.83)
   5. PKT041: Unlimited Night (0.79)

   MMR diversification:

   Select #1: PKT015 (Gaming 10GB) - score 0.94 ✓

   Evaluate PKT016:
   • Relevance: 0.89
   • Similarity to PKT015: 0.95 (both Gaming, similar quota)
   • MMR: 0.7×0.89 - 0.3×0.95 = 0.338 ← Penalized heavily!

   Evaluate PKT022:
   • Relevance: 0.83
   • Similarity to PKT015: 0.2 (different family)
   • MMR: 0.7×0.83 - 0.3×0.2 = 0.521 ← Better diversity!

   Select #2: PKT022 (Streaming 15GB) ✓

   Final Top 5 (Diverse):
   1. PKT015: Gaming 10GB (0.94)
   2. PKT022: Streaming 15GB (0.83)
   3. PKT033: Budget 5GB (0.68)
   4. PKT041: Unlimited Night (0.79)
   5. PKT007: Social Media (0.65)

5️⃣ EXPLANATION GENERATION (Rule-based)

   For PKT015:
   IF cf_score > 0.8 AND quota_match > 1.0:
     reason = "Based on your gaming usage pattern"

   For PKT022:
   IF family = "Streaming" AND user_history contains "Streaming":
     reason = "Perfect for your video streaming habits"

   For PKT033:
   IF price < avg_price AND recency > 30d:
     reason = "Budget-friendly option for moderate use"

FINAL RECOMMENDATION TO USER X:
═══════════════════════════════════════════════════════════════

✅ #1: Paket Gaming Pro (PKT015) - Rp 85,000
   Match: 94%
   💡 "Based on your gaming usage pattern"

   Why this is #1?
   ✓ You're a moderate gamer (8.5GB usage)
   ✓ 10GB quota = perfect fit
   ✓ You bought similar package 7 days ago
   ✓ Similar users in your segment love this
   ✓ Price fits your 50-100K budget

✅ #2: Paket Streaming Max (PKT022) - Rp 100,000
   Match: 83%
   💡 "Perfect for your video streaming habits"

   Why this is #2?
   ✓ Diverse from #1 (different family)
   ✓ 15GB for heavy streaming
   ✓ Your profile shows streaming interest
   ✓ Top of your budget but high value
```

---

## 🔑 **Key Insights**

1. **Segmentation** → Groups similar users (collaborative signal)
2. **LightFM** → Finds what similar users like + content match
3. **XGBoost** → Refines ranking dengan rich features (quota_match, price_match, dll)
4. **MMR** → Prevents showing 10 similar Gaming packages (diversity!)
5. **Caching** → Redis menyimpan hasil selama 5 menit (speed!)

**Why User X gets Gaming package as #1?**
- Similar users in Segment 1 bought it ✓
- Content matches (Gaming user → Gaming package) ✓
- Quota matches usage pattern (8.5GB → 10GB) ✓
- Repeat purchase pattern (bought similar 7 days ago) ✓
- Price fits budget ✓

Semua ini **data-driven**, bukan random! 🎯
