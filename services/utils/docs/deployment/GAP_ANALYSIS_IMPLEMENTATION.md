# Gap Analysis & Implementation Plan - PAKETIFY

**Last Updated**: 2025-01-17
**Status**: Pre-Demo Preparation
**Estimated Total Time**: 6-7 hours

---

## 🚨 **CRITICAL** (Wajib untuk demo nyala)

### 0. ❌ **Real Authentication & Registration** ⚠️ FOUNDATION

**Problem**: Sekarang masih mock auth (hardcoded credentials), belum ada real database-based authentication

**Current State**:
```javascript
// authService.js - MOCK
mockLogin(phone, password) {
  const validCredentials = [
    { phone: '08123456789', password: 'user123' }, // Hardcoded!
    { phone: 'admin', password: 'admin123' },
  ]
  // No database check, no bcrypt, no real JWT
}
```

**Impact**:
- Cannot register new users
- No real user data in database
- Mock data only in localStorage
- Cannot scale or persist users
- No security (plain text passwords)

**Solution**:
```
Backend (NEW):
├─ Create users table in PostgreSQL
│  ├─ id (UUID, primary key)
│  ├─ phone (VARCHAR, unique)
│  ├─ password_hash (VARCHAR - bcrypt)
│  ├─ name (VARCHAR)
│  ├─ role (ENUM: 'user', 'admin')
│  ├─ balance (INTEGER, default 100000)
│  ├─ created_at, updated_at
│
├─ POST /api/v1/auth/register
│  ├─ Validate phone format (08xxxxxxxxxx)
│  ├─ Hash password dengan bcrypt
│  ├─ Save to users table
│  ├─ Generate real JWT token
│  └─ Return: { access_token, user }
│
├─ POST /api/v1/auth/login
│  ├─ Find user by phone
│  ├─ Verify bcrypt hash
│  ├─ Generate JWT token
│  └─ Return: { access_token, user }
│
└─ GET /api/v1/users/me (Protected)
   ├─ Verify JWT token
   ├─ Return user profile
   └─ Include segment info

Frontend (UPDATE):
├─ Create RegisterPage.jsx (NEW)
│  ├─ Phone input (validated)
│  ├─ Name input
│  ├─ Password input (min 6 chars)
│  ├─ Confirm password
│  └─ Submit → POST /auth/register
│
├─ Update LoginPage.jsx
│  ├─ Call real API: POST /auth/login
│  ├─ Store JWT token (not mock)
│  └─ Handle errors gracefully
│
└─ Update authService.js
   ├─ Remove mockLogin
   ├─ Implement real login/register
   └─ Add JWT token management

Security (Simple for Demo):
├─ JWT with HS256 (SECRET_KEY in .env)
├─ bcrypt for password hashing
├─ No email verification (skip for demo)
├─ No password reset (skip for demo)
└─ Simple validation only
```

**Database Schema**:
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(15) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    balance INTEGER DEFAULT 100000,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Seed admin account
INSERT INTO users (phone, password_hash, name, role) VALUES
('admin', '$2b$12$...', 'Admin User', 'admin');
```

**Files to Create**:
- `backend/app/db/models/user.py`
- `backend/app/api/v1/endpoints/auth.py`
- `backend/app/core/security.py` (JWT + bcrypt utils)
- `backend/app/db/migrations/001_create_users_table.sql`
- `frontend/src/pages/RegisterPage.jsx`

**Files to Modify**:
- `frontend/src/services/authService.js` (remove mock)
- `frontend/src/pages/LoginPage.jsx` (call real API)
- `frontend/src/App.jsx` (add /register route)
- `frontend/src/components/Navbar.jsx` (add Register link)

**Estimated Time**: 2 hours

---

### 1. ❌ **Onboarding Questionnaire**

**Problem**: User baru gabisa dapet rekomendasi akurat (cold start problem)

**Impact**:
- New user dapat rekomendasi generic
- ML pipeline gabisa jalan tanpa data
- Poor first impression

**Solution**:
```
Frontend:
├─ Create OnboardingPage.jsx (3-5 questions)
│  ├─ Berapa data yang biasa kamu pakai per bulan?
│  ├─ Apa yang paling sering kamu lakukan?
│  ├─ Berapa budget kamu per bulan?
│  ├─ Device type (auto-detect)
│  └─ Save to user_profiles table
│
Backend:
├─ POST /api/v1/users/onboarding
├─ Save to user_profiles table
└─ Use for cold start recommendations

Cold Start Logic:
├─ Content-based filtering (by preferences)
├─ Popularity-based ranking (TopPopular)
└─ Budget & quota filtering
```

**Files to Create**:
- `frontend/src/pages/OnboardingPage.jsx`
- `backend/app/api/v1/endpoints/onboarding.py`
- `backend/app/models/user_profile.py`

**Estimated Time**: 1.5 hours

---

### 2. ❌ **Simulasi Checkout** (Depends on #0)

**Problem**: User ga bisa "beli" paket → gabisa generate transaction data → ML ga belajar

**Impact**:
- User journey incomplete
- No transaction data for ML
- Can't test collaborative filtering

**Solution**:
```
ProductDetailPage:
├─ Add "Buy Now" button
├─ Checkout confirmation modal
│  ├─ Package summary
│  ├─ Price confirmation
│  └─ Payment method selector (MOCK)
│
├─ POST /api/v1/transactions/simulate
│  ├─ Save to transactions table
│  ├─ Mark as is_simulated=true
│  └─ Update user balance
│
└─ Success notification
   ├─ Toast: "Package activated!"
   └─ Redirect to Dashboard

Backend:
├─ POST /api/v1/transactions/simulate
├─ Create transaction record
├─ Trigger user feature recalculation
└─ Update recommendations cache
```

**Files to Modify**:
- `frontend/src/pages/ProductDetailPage.jsx`
- `backend/app/api/v1/endpoints/transactions.py`
- `backend/app/models/transaction.py`

**Estimated Time**: 1.5 hours

---

### 3. ❌ **Purchase History** (Depends on #0, #2)

**Problem**: Ga ada bukti user pernah beli apa

**Impact**:
- No user trust
- Can't show transaction proof
- No way to track spending

**Solution**:
```
Create PurchaseHistoryPage:
├─ List all user transactions
├─ Show: Date, Package, Price, Status
├─ Filter: Last 7 days, 30 days, All time
└─ Export to CSV (optional)

GET /api/v1/transactions?user_id={id}&limit=10
Response:
{
  "transactions": [
    {
      "id": "uuid",
      "product_name": "Paket Gaming 10GB",
      "price": 85000,
      "purchased_at": "2025-01-17T10:30:00Z",
      "status": "active",
      "is_simulated": true
    }
  ],
  "total": 5,
  "total_spent": 425000
}

Add to Dashboard:
├─ Recent transactions widget (last 3)
└─ Link to full history page
```

**Files to Create**:
- `frontend/src/pages/PurchaseHistoryPage.jsx`
- Update `frontend/src/App.jsx` (add route)

**Files to Modify**:
- `frontend/src/pages/DashboardPage.jsx` (add widget)
- `backend/app/api/v1/endpoints/transactions.py` (add GET endpoint)

**Estimated Time**: 1 hour

---

## ⚠️ **HIGH** (Sangat disarankan)

### 4. ⚠️ **Product Sync**

**Problem**: Frontend (6 paket) vs Admin (8 paket) beda → confusing

**Current State**:
```
Frontend mockProducts: 6 items (For You, Mania)
Admin packages: 8 items (mixed)
Backend ML: 4 offer types (PROD_*)
```

**Solution**:
```
1. Create products table in PostgreSQL
   ├─ Seed with 50 realistic packages
   ├─ Different families: Gaming, Streaming, Budget, Premium
   └─ Price range: Rp 15K - Rp 200K

2. Replace frontend mockProducts
   ├─ GET /api/v1/products (fetch from DB)
   ├─ Remove hardcoded mock data
   └─ Use real API responses

3. Connect Admin Dashboard to DB
   ├─ Admin CRUD → Updates products table
   ├─ Changes immediately reflected in frontend
   └─ ML can use latest product catalog
```

**Files to Create**:
- `backend/app/db/seeds/products.sql`
- `backend/app/models/product.py`

**Files to Modify**:
- `frontend/src/services/recommendationService.js` (remove mock)
- `frontend/src/pages/AdminDashboardPage.jsx` (connect to API)
- `backend/app/api/v1/endpoints/products.py` (full CRUD)

**Estimated Time**: 1.5 hours

---

### 5. ⚠️ **Segment Visualization**

**Problem**: Dashboard ga tampilkan user masuk segment berapa

**Impact**:
- User tidak tahu profilnya
- Tidak ada transparency
- Missed opportunity untuk engagement

**Solution**:
```
Dashboard Enhancement:
├─ Add Segment Badge
│  ├─ "You are a Heavy User 🚀"
│  ├─ Color-coded (Light: blue, Moderate: green, Heavy: gold)
│  └─ Tooltip: "Based on your usage pattern"
│
├─ Segment Stats Card
│  ├─ Avg monthly usage: 15 GB
│  ├─ Purchase frequency: 12 times/month
│  └─ Spending: Rp 500K/month
│
└─ Segment-specific Insights
   ├─ "90% of Heavy Users prefer Gaming packages"
   └─ "You're in top 20% of active users"

Backend:
├─ Add segment to user metadata
├─ GET /api/v1/users/me includes segment info
└─ Calculate segment in real-time or cache
```

**Files to Modify**:
- `frontend/src/pages/DashboardPage.jsx`
- `backend/app/api/v1/endpoints/users.py`
- `backend/app/services/segmentation_service.py`

**Estimated Time**: 1 hour

---

### 6. ⚠️ **Admin ↔ ML Integration**

**Problem**: Admin add paket baru, tapi ga masuk recommendation system

**Current State**:
```
Admin adds package → Only in frontend state
ML reads from CSV → Static data
No connection between Admin CRUD and ML pipeline
```

**Solution**:
```
1. Admin CRUD Updates Database
   ├─ POST /api/v1/products → Insert to products table
   ├─ PUT /api/v1/products/{id} → Update
   └─ DELETE /api/v1/products/{id} → Soft delete

2. ML Reads from Database
   ├─ Replace CSV data source with DB query
   ├─ HybridPipeline loads products from DB
   └─ Recommendations include latest packages

3. Trigger Model Refresh (optional)
   ├─ Admin action → Webhook to retrain
   ├─ Or: Daily cron job retrains model
   └─ Update MLflow registry
```

**Files to Modify**:
- `backend/app/ml/pipeline/hybrid_pipeline.py` (load from DB)
- `backend/app/api/v1/endpoints/products.py` (full CRUD)
- `infrastructure/airflow/dags/model_retraining.py` (add trigger)

**Estimated Time**: 1.5 hours

---

## 📝 **MEDIUM** (Nice to have)

### 7. 📝 **Loading States**

**Problem**: Beberapa page ga ada loading indicator

**Solution**:
```
Add LoadingSpinner to:
├─ DashboardPage (fetching recommendations)
├─ ProductsPage (fetching products)
├─ AdminDashboardPage (fetching stats)
└─ PurchaseHistoryPage (fetching transactions)

Pattern:
const [loading, setLoading] = useState(true)
const [data, setData] = useState(null)

useEffect(() => {
  fetchData()
    .then(res => setData(res))
    .finally(() => setLoading(false))
}, [])

if (loading) return <LoadingSpinner />
```

**Estimated Time**: 30 minutes

---

### 8. 📝 **Error Handling UI**

**Problem**: Error messages kurang user-friendly

**Solution**:
```
Create ErrorMessage component:
├─ User-friendly text (bukan technical error)
├─ Retry button
├─ Fallback suggestions
└─ Support contact (optional)

Example:
"Oops! Gagal memuat rekomendasi"
"Coba refresh halaman atau hubungi support"
[Retry Button]

Add to:
├─ RecommendationWidget
├─ ProductsPage
└─ DashboardPage
```

**Estimated Time**: 30 minutes

---

### 9. 📝 **User Profile Edit**

**Problem**: Ga bisa update preferences setelah register

**Solution**:
```
ProfilePage Enhancement:
├─ Add "Edit Preferences" section
├─ Re-show onboarding questions (editable)
├─ PUT /api/v1/users/me/preferences
└─ Update recommendations based on new prefs

Fields:
├─ Estimated monthly quota
├─ Preferred activities (multi-select)
├─ Price budget range
└─ Device type
```

**Estimated Time**: 1 hour

---

### 10. 📝 **Empty States**

**Problem**: Ga ada tampilan "No recommendations yet" untuk user baru

**Solution**:
```
Cold Start Handling:
├─ Show popular packages instead
├─ Message: "Based on popular choices"
├─ CTA: "Complete profile for better recommendations"
└─ Fallback to TopPopular baseline

Empty Purchase History:
├─ Message: "Belum ada pembelian"
├─ CTA: "Browse paket yang tersedia"
└─ Link to ProductsPage

No Search Results:
├─ Message: "Tidak ditemukan paket yang cocok"
├─ Show alternative suggestions
└─ Clear filter button
```

**Estimated Time**: 45 minutes

---

## 📊 **Implementation Priority**

```
Week 1 (CRITICAL - 4 hours):
├─ Day 1: Onboarding Questionnaire (1.5h)
├─ Day 2: Simulasi Checkout (1.5h)
└─ Day 3: Purchase History (1h)

Week 2 (HIGH - 4 hours):
├─ Day 1: Product Sync (1.5h)
├─ Day 2: Segment Visualization (1h)
└─ Day 3: Admin ML Integration (1.5h)

Week 3 (MEDIUM - 2.5 hours):
├─ Day 1: Loading + Error States (1h)
├─ Day 2: Profile Edit (1h)
└─ Day 3: Empty States (0.5h)
```

---

## ✅ **Demo Readiness Checklist**

After implementing CRITICAL + HIGH items:

**User Journey**:
- [ ] User dapat register dengan mudah
- [ ] Onboarding dalam 30 detik
- [ ] Browse products dari database
- [ ] Checkout dan simulate payment
- [ ] Purchase history tersimpan
- [ ] Dashboard show segment badge
- [ ] Recommendations akurat dan personal

**Admin Capabilities**:
- [ ] Login sebagai admin
- [ ] CRUD products → Langsung masuk DB
- [ ] Products immediately available for users
- [ ] ML pipeline uses latest products

**ML Pipeline**:
- [ ] Cold start handled (onboarding + popularity)
- [ ] Warm start (event tracking)
- [ ] Hot start (transaction-based collaborative)
- [ ] Segment visualization working
- [ ] Recommendations improve over time

**Technical Quality**:
- [ ] Loading states di semua pages
- [ ] Error handling graceful
- [ ] Empty states handled
- [ ] Responsive di mobile
- [ ] No console errors

---

## 🎯 **Demo Script (After Implementation)**

```
SCENARIO 1: New User (3 menit)
════════════════════════════════
1. Register → Onboarding (3 questions)
2. Dashboard → See cold start recommendations
3. Browse products → Click "Paket Gaming"
4. "Buy Now" → Simulate checkout
5. Success! → Purchase history updated
6. Dashboard → Better recommendations!
7. Check segment badge: "You are a Moderate User"

SCENARIO 2: Admin Power (2 menit)
══════════════════════════════════
1. Login admin/admin123
2. Admin Dashboard → Add "Paket Drakor 50GB"
3. Save → Product in database
4. Logout → Login as regular user
5. Browse products → NEW package appears!
6. Buy it → ML learns from purchase

SCENARIO 3: ML Learning (2 menit)
════════════════════════════════
1. User A buys 3x Gaming packages
2. User B (new) selects "Gaming" in onboarding
3. User B dashboard → Gaming packages di top!
4. Show segment: User A = Heavy, User B = Light
5. Collaborative filtering works!
```

---

## 📝 **Next Steps**

1. **Prioritize CRITICAL items** (Week 1)
2. **Test each feature** after implementation
3. **Run full demo scenario** to verify flow
4. **Document any blockers** or issues
5. **Polish UI/UX** if time permits

**Questions?** Review this doc and start with Item #1 (Onboarding Questionnaire).
