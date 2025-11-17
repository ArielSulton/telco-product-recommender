# Testing Documentation

Comprehensive test suite for the Telco Product Recommender System.

## 📁 Test Structure

All tests are organized by testing level following industry best practices:

```
tests/
├── integration/                # Integration tests (medium speed)
│   ├── test_sprint1.py         # Database & backend infrastructure
│   ├── test_sprint2.py         # ML models & feature engineering
│   ├── test_sprint3.py         # API & pipeline integration
│   └── test_data_pipeline.sh   # Data pipeline end-to-end
│
├── e2e/                        # End-to-end tests (slow, full system)
│   └── test_e2e_production.py  # Production E2E validation
│
├── security/                   # Security & vulnerability testing
│   └── security_audit.py       # Security vulnerability scanner
│
├── frontend/                   # Frontend validation
│   └── verify_frontend.sh      # Frontend setup validation
│
└── scripts/                    # Utility scripts
    └── train_demo_model.py     # Demo model training script
```

---

## 🚀 Quick Start

### Run All Tests (Recommended)

```bash
# From project root
cd /path/to/ASAH\ Capstone

# Integration tests (requires services running)
python services/utils/tests/integration/test_sprint1.py
python services/utils/tests/integration/test_sprint2.py
python services/utils/tests/integration/test_sprint3.py
bash services/utils/tests/integration/test_data_pipeline.sh

# Frontend validation
bash services/utils/tests/frontend/verify_frontend.sh

# E2E tests (full stack must be running)
python services/utils/tests/e2e/test_e2e_production.py --base-url http://localhost:8000

# Security audit
python services/utils/tests/security/security_audit.py --target http://localhost:8000

# Demo model training (optional)
python services/utils/tests/scripts/train_demo_model.py
```

---

## 📋 Test Categories

### 1️⃣ Integration Tests

**Location**: `tests/integration/`

**Purpose**: Test component interactions and system integration

#### **test_sprint1.py** - Database & Infrastructure

**Coverage**:
- Database connectivity
- Schema creation
- ORM model validation
- Configuration loading

**Requirements**:
- PostgreSQL running (port 5434)
- Backend dependencies installed

**Run**:
```bash
python services/utils/tests/integration/test_sprint1.py
```

**Expected**: ✅ 4/4 tests passing

---

#### **test_sprint2.py** - ML Models

**Coverage**:
- K-Means segmentation
- LightFM collaborative filtering
- Feature engineering
- Model training & evaluation

**Requirements**:
- Python 3.10+
- ML libraries (scikit-learn, lightfm, xgboost)

**Run**:
```bash
python services/utils/tests/integration/test_sprint2.py
```

**Expected**: ✅ 7/7 tests passing

---

#### **test_sprint3.py** - API & Pipeline

**Coverage**:
- XGBoost ranker training
- Hybrid ML pipeline
- MMR diversification
- MLflow registry integration
- Performance benchmarks

**Requirements**:
- Backend dependencies
- MLflow server (optional, some tests will skip)

**Run**:
```bash
python services/utils/tests/integration/test_sprint3.py
```

**Expected**: ✅ 5/5 tests passing (MLflow test may skip if server not running)

---

#### **test_data_pipeline.sh** - Data Pipeline

**Coverage**:
- CSV data loading
- Database ingestion
- Data validation (30+ checks)
- Pipeline health monitoring

**Requirements**:
- PostgreSQL running
- CSV data at `ml/data/raw/`
- Docker services running

**Run**:
```bash
bash services/utils/tests/integration/test_data_pipeline.sh
```

**Expected**: ✅ 30+ tests passing

---

### 2️⃣ End-to-End Tests

**Location**: `services/utils/tests/e2e/`

**Purpose**: Full system validation with real workflows

#### **test_e2e_production.py** - Production E2E

**Coverage**:
- Health checks (API, DB, Redis, MLflow)
- User authentication flow (register, login)
- Recommendation generation
- Event tracking
- Performance metrics
- Error handling
- Security headers
- Data integrity
- System resilience

**Requirements**:
- **Full stack running** (docker-compose up)
- API: http://localhost:8000
- Frontend: http://localhost:5173
- All services healthy

**Run**:
```bash
# Start services first
docker-compose -f compose.dev.yaml up -d

# Wait for services to be healthy
sleep 10

# Run E2E tests
python services/utils/tests/e2e/test_e2e_production.py --base-url http://localhost:8000
```

**Expected**: ✅ 9/9 test categories passing

**Test Categories**:
1. Health Checks
2. Authentication
3. Recommendations
4. Events
5. Performance
6. Error Handling
7. Security
8. Data Integrity
9. Resilience

---

### 3️⃣ Security Tests

**Location**: `services/utils/tests/security/`

**Purpose**: Vulnerability scanning and security validation

#### **security_audit.py** - Security Scanner

**Coverage**:
- Security headers (CSP, HSTS, X-Frame-Options)
- TLS/SSL configuration
- Authentication enforcement
- Rate limiting validation
- Input validation testing
- CORS configuration
- Sensitive data exposure checks
- Known vulnerability scanning

**Requirements**:
- API running (production or staging)
- Network access to target

**Run**:
```bash
# Against local dev
python services/utils/tests/security/security_audit.py --target http://localhost:8000

# Against production (use HTTPS!)
python services/utils/tests/security/security_audit.py --target https://api.your-domain.com
```

**Expected**:
- ✅ Risk score < 30 (production)
- ⚠️ Risk score < 50 (development)

**Risk Levels**:
- 🔴 Critical (90-100): Immediate action required
- 🟠 High (70-89): Fix before production
- 🟡 Medium (40-69): Schedule fix
- 🟢 Low (0-39): Acceptable

---

### 4️⃣ Frontend Tests

**Location**: `services/utils/tests/frontend/`

**Purpose**: Frontend validation and setup verification

#### **verify_frontend.sh** - Frontend Validator

**Coverage**:
- Package.json validation
- Dependencies check
- Component existence
- Route configuration
- Build verification

**Requirements**:
- Node.js 18+
- Frontend dependencies installed

**Run**:
```bash
bash services/utils/tests/frontend/verify_frontend.sh
```

**Expected**: ✅ 10+ checks passing

---

### 5️⃣ Utility Scripts

**Location**: `services/utils/tests/scripts/`

**Purpose**: Helper scripts for testing and development

#### **train_demo_model.py** - Demo Model Training

**Coverage**:
- Quick model training for demo purposes
- Lightweight model creation
- Rapid prototyping and testing

**Requirements**:
- Python 3.10+
- ML libraries installed

**Run**:
```bash
python services/utils/tests/scripts/train_demo_model.py
```

**Use Case**: Generate demo models for presentations and testing without full pipeline

---

## 📊 Test Matrix

| Test Level | Location | Speed | Isolation | Coverage |
|------------|----------|-------|-----------|----------|
| Integration | `integration/` | 🔄 Medium | ⚠️ Medium | Systems |
| E2E | `e2e/` | 🐢 Slow | ❌ Low | Full Stack |
| Security | `security/` | 🔄 Medium | ✅ High | Vulnerabilities |
| Frontend | `frontend/` | ⚡ Fast | ✅ High | UI Setup |
| Scripts | `scripts/` | ⚡ Fast | ✅ High | Utilities |

---

## 🔧 Test Requirements by Level

### Integration Tests
```bash
# Services must be running
docker-compose -f compose.dev.yaml up -d postgres redis

# Wait for services
sleep 5

# Install dependencies
pip install -r backend/requirements.txt
```

### E2E Tests
```bash
# Full stack must be running
docker-compose -f compose.dev.yaml up -d

# Verify all services healthy
docker-compose -f compose.dev.yaml ps
```

### Security Tests
```bash
pip install httpx
# Target API must be accessible
```

### Frontend Tests
```bash
cd frontend
npm install
```

### Utility Scripts
```bash
# No additional requirements
# Uses existing backend dependencies
```

---

## 🎯 CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Start services
        run: docker-compose -f compose.dev.yaml up -d

      - name: Wait for services
        run: sleep 10

      - name: Run integration tests
        run: |
          python services/utils/tests/integration/test_sprint1.py
          python services/utils/tests/integration/test_sprint2.py
          python services/utils/tests/integration/test_sprint3.py

      - name: Run E2E tests
        run: python services/utils/tests/e2e/test_e2e_production.py

      - name: Security audit
        run: python services/utils/tests/security/security_audit.py --target http://localhost:8000
```

---

## 📈 Test Coverage Goals

| Category | Current | Target |
|----------|---------|--------|
| Integration Tests | ✅ Complete | Maintain |
| E2E Tests | ✅ Complete | Expand |
| Security Tests | ✅ Complete | Maintain |
| Frontend Tests | ⚠️ Basic | 60% |
| Utility Scripts | ✅ Available | Maintain |

---

## 🚨 Troubleshooting

### Common Issues

**Issue**: Tests fail with "Connection refused"
```bash
# Solution: Ensure services are running
docker-compose -f compose.dev.yaml ps
docker-compose -f compose.dev.yaml up -d
```

**Issue**: Database tests fail
```bash
# Solution: Reset database
docker-compose -f compose.dev.yaml down -v
docker-compose -f compose.dev.yaml up -d
```

**Issue**: MLflow tests skip
```bash
# Expected behavior - MLflow server optional
# To enable: mlflow server --host 0.0.0.0 --port 5000
```

**Issue**: Security audit shows high risk score
```bash
# Development: Acceptable if < 50
# Production: Must be < 30 before deployment
```

---

## 📝 Test Development Guidelines

### Adding New Tests

1. **Choose the right level**:
   - Integration: Component interactions, database/API
   - E2E: Full user workflows, all services
   - Scripts: Utility and helper scripts

2. **Follow naming conventions**:
   - `test_*.py` for Python tests
   - `test_*.sh` for Bash scripts
   - Descriptive function names: `test_user_registration_with_valid_phone()`

3. **Include documentation**:
   - Docstrings for test functions
   - Comments for complex assertions
   - README updates for new test categories

4. **Maintain test independence**:
   - No shared state between tests
   - Clean up after execution
   - Use fixtures/setup/teardown

---

## 🔄 Next Steps

### Planned Improvements

- [ ] Expand frontend tests to include React component testing
- [ ] Add performance regression tests
- [ ] Implement test coverage reporting (pytest-cov)
- [ ] Add mutation testing for ML models
- [ ] Create API contract tests (Pact/OpenAPI)
- [ ] Add more utility scripts for common testing scenarios

---

**Last Updated**: 2025-01-17 (v1.2.0 - Updated for new test structure)
**Total Tests**: 60+ across all categories
**Test Structure**: Integration, E2E, Security, Frontend, Scripts
**Maintainer**: ASAH Capstone Team

For questions or issues, see the main project README or create an issue.
