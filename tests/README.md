# Testing Documentation

All test scripts and validation tools for the Telco Product Recommender System.

## 📋 Test Files

### Unit & Integration Tests
- **test_sprint1.py** - Database & backend infrastructure tests
- **test_sprint2.py** - ML models & feature engineering tests
- **test_sprint3.py** - API & pipeline integration tests

### System Tests
- **test_data_pipeline.sh** - Data pipeline end-to-end test (30+ tests)
- **verify_frontend.sh** - Frontend validation script

### Production Validation
Located in `../scripts/`:
- **test_e2e_production.py** - End-to-end production test (9 categories)
- **security_audit.py** - Security vulnerability scan

## 🚀 Running Tests

### Sprint Tests (Python)
```bash
# Sprint 1 - Database & Infrastructure
python tests/test_sprint1.py

# Sprint 2 - ML Models & Features
python tests/test_sprint2.py

# Sprint 3 - API & Pipeline
python tests/test_sprint3.py
```

### Data Pipeline Test (Bash)
```bash
# Run comprehensive pipeline test
bash tests/test_data_pipeline.sh

# Expected: 30+ tests passing
```

### Frontend Validation (Bash)
```bash
# Verify frontend setup
bash tests/verify_frontend.sh
```

### Production E2E Test
```bash
# Full system test (requires running services)
python scripts/test_e2e_production.py --base-url http://localhost:8000

# Expected: 9/9 test categories passing
```

### Security Audit
```bash
# Security vulnerability scan
python scripts/security_audit.py --target http://localhost:8000

# Expected: Risk score < 30
```

## ✅ Test Coverage

| Category | Test File | Tests | Status |
|----------|-----------|-------|--------|
| Database Schema | test_sprint1.py | 4 | ✅ |
| ML Models | test_sprint2.py | 7 | ✅ |
| API Endpoints | test_sprint3.py | 5 | ✅ |
| Data Pipeline | test_data_pipeline.sh | 30+ | ✅ |
| Frontend | verify_frontend.sh | 10+ | ✅ |
| E2E Production | test_e2e_production.py | 9 categories | ✅ |
| Security | security_audit.py | 10+ checks | ✅ |

## 📊 Running All Tests

```bash
# Quick validation (unit tests only)
python tests/test_sprint1.py
python tests/test_sprint2.py
python tests/test_sprint3.py

# Full validation (requires running services)
bash tests/test_data_pipeline.sh
python scripts/test_e2e_production.py
python scripts/security_audit.py
```

## 🔍 Test Requirements

### Unit Tests
- Python 3.10+
- Dependencies from backend/requirements.txt
- PostgreSQL running (for sprint 1)

### Integration Tests
- All services running via docker compose
- Database initialized
- Redis available

### E2E Tests
- Full stack running
- API accessible on localhost:8000
- Frontend on localhost:5173

---

**Last Updated**: November 8, 2024
**Total Tests**: 60+ across all categories
