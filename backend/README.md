# Backend - Telco Product Recommender API

FastAPI-based backend service for personalized telco product recommendations.

## Overview

Hybrid ML-powered recommendation system with RESTful API endpoints for:
- Product recommendations (`/api/v1/recommend`)
- Event tracking (`/api/v1/events`)
- Product catalog (`/api/v1/products`)
- User profiles (`/api/v1/users`)

## Technology Stack

- **Framework**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL 14+ (via SQLAlchemy ORM)
- **Cache**: Redis 7+
- **ML Serving**: MLflow + custom inference
- **Authentication**: JWT (python-jose)
- **Monitoring**: Prometheus metrics

## Project Structure

```
backend/
├── app/
│   ├── api/v1/endpoints/     # API route handlers
│   ├── core/                 # Config, security, logging
│   ├── models/               # Database & schema models
│   ├── services/             # Business logic layer
│   ├── ml/                   # ML inference & models
│   └── db/                   # Database session & migrations
├── tests/                    # Unit & integration tests
├── requirements.txt          # Production dependencies
├── requirements-dev.txt      # Development dependencies
└── Dockerfile               # Container image definition
```

## Setup Instructions

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Redis 7+

### Installation

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # for development
   ```

3. **Configure environment**:
   ```bash
   cp ../.env.example .env
   # Edit .env with your configuration
   ```

4. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

5. **Start development server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Documentation

Once the server is running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Development

### Running Tests
```bash
pytest tests/ -v --cov=app
```

### Code Quality
```bash
# Format code
black app/

# Lint
pylint app/

# Type checking
mypy app/
```

## Deployment

See `../docs/deployment/production_checklist.md` for production deployment guide.

## Key Features

- ✅ Hybrid recommendation pipeline (K-Means → LightFM → XGBoost)
- ✅ Sub-150ms latency (p95) with Redis caching
- ✅ SHAP-based recommendation explanations
- ✅ A/B testing framework
- ✅ Comprehensive monitoring (Prometheus metrics)
- ✅ Rate limiting & security hardening
- ✅ Async/await for high concurrency

## Performance Targets

| Metric | Target |
|--------|--------|
| Latency (p95) | ≤150ms |
| Error Rate | ≤1% |
| Throughput | 1000 req/s |
| Availability | ≥99.9% |

