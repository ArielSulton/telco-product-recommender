# Project Structure - Telco Product Recommender

Organized project structure with clean separation of documentation and tests.

## 📁 Root Directory Structure

```
ASAH Capstone/
├── backend/                    # FastAPI backend application
├── frontend/                   # React frontend application
├── infrastructure/             # Infrastructure configs (Airflow, monitoring)
├── services/                   # Microservices (data-simulator)
├── ml/                        # ML data and notebooks
├── docs/                      # 📚 All documentation (organized)
├── tests/                     # 🧪 All test files (organized)
├── scripts/                   # Utility scripts (E2E test, security audit)
├── compose.dev.yaml           # Development Docker config
├── compose.prod.yaml          # Production Docker config
├── .env.example               # Environment template
├── IMPLEMENTATION_FLOW.md     # Original requirements
├── IMPLEMENTATION_COMPLETE.md # ✅ Complete implementation summary
└── PROJECT_STRUCTURE.md       # This file
```

## 📚 Documentation (`docs/`)

### Main Docs
- `README.md` - Documentation index
- `PRODUCTION_QUICK_START.md` - Quick setup guide
- `API_DOCUMENTATION.md` - Complete API reference
- `DEPLOYMENT_GUIDE.md` - Deployment procedures
- `MONITORING_RUNBOOK.md` - Monitoring & alerts
- `TROUBLESHOOTING_GUIDE.md` - Common issues

### Sprint Documentation (`docs/sprints/`)
- **Sprint 1** (3 files): Infrastructure & streaming
- **Sprint 2** (2 files): ML models & features
- **Sprint 3** (3 files): API & frontend
- **Sprint 4** (1 file): Automation & monitoring
- **Sprint 5** (1 file): Production hardening

### Implementation Details (`docs/implementation/`)
- `DATA_SIMULATOR_IMPLEMENTATION.md` - Data streaming details

## 🧪 Testing (`tests/`)

### Test Files
- `README.md` - Testing documentation
- `test_sprint1.py` - Database & infrastructure tests
- `test_sprint2.py` - ML models tests
- `test_sprint3.py` - API & pipeline tests
- `test_data_pipeline.sh` - Data pipeline test (30+ tests)
- `verify_frontend.sh` - Frontend validation

### Production Tests (`scripts/`)
- `test_e2e_production.py` - End-to-end system test
- `security_audit.py` - Security scan

## 🚀 Quick Navigation

### Want to start the system?
→ See `docs/PRODUCTION_QUICK_START.md`

### Want to understand the API?
→ See `docs/API_DOCUMENTATION.md`

### Want to deploy to production?
→ See `docs/DEPLOYMENT_GUIDE.md`

### Want to run tests?
→ See `tests/README.md`

### Want implementation details?
→ See `docs/sprints/` for each sprint

### Having issues?
→ See `docs/TROUBLESHOOTING_GUIDE.md`

## 📊 File Statistics

- **Total Documentation**: 15+ markdown files
- **Sprint Docs**: 11 files (organized by sprint)
- **Test Files**: 7 files (unit, integration, E2E, security)
- **Main Guides**: 4 files (deployment, monitoring, API, troubleshooting)

## 🎯 Clean Structure Benefits

✅ **Easy Navigation** - Clear folder organization
✅ **No Clutter** - All docs in `docs/`, all tests in `tests/`
✅ **Easy to Find** - README files in each folder
✅ **Professional** - Standard project structure
✅ **Maintainable** - Easy to add new docs/tests

---

**Last Updated**: November 8, 2024
**Status**: Production Ready
