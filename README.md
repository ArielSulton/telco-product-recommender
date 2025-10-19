# ASAH Capstone Project - Telco Product Recommendation Offer based on Customer Behaviour

Sistem rekomendasi produk telekomunikasi berbasis AI untuk meningkatkan personalisasi dan konversi penjualan.

## 🎯 Overview

Hybrid recommendation system yang menggabungkan:
- **Segmentation**: K-Means clustering untuk grouping user
- **Collaborative Filtering**: LightFM untuk candidate generation
- **Ranking**: XGBoost untuk final product ordering
- **Explainability**: SHAP untuk reasoning rekomendasi

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL 14
- **Cache**: Redis 7
- **ML Tracking**: MLflow

### Frontend
- **Framework**: React 18 + Vite
- **Styling**: Tailwind CSS
- **Router**: React Router v6

### ML Pipeline
- **Libraries**: scikit-learn, LightFM, XGBoost, SHAP
- **Training**: Jupyter notebooks + Python scripts
- **Orchestration**: Apache Airflow

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Deployment**: Dokploy (with Traefik reverse proxy)
- **Monitoring**: Prometheus + Grafana

## 📁 Project Structure

```
├── backend/         # FastAPI application
├── frontend/        # React application
├── ml/              # ML training pipeline
├── infrastructure/  # Docker, monitoring, Airflow
├── docs/            # Documentation
└── tests/           # E2E & load tests
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.10+ (for backend/ML development)

### Development Setup

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd ASAH-Capstone
   ```

2. **Setup environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services**
   ```bash
   docker-compose -f compose.dev.yaml up -d
   ```

4. **Access applications**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - MLflow: http://localhost:5000
   - Grafana: http://localhost:3000

## 📚 Documentation

- [Implementation Flow](IMPLEMENTATION_FLOW.md) - Sprint-by-sprint development guide
- [Backend Documentation](backend/README.md)
- [Frontend Documentation](frontend/README.md)
- [ML Pipeline Documentation](ml/README.md)
- [Infrastructure Documentation](infrastructure/README.md)

## 🎯 Target Metrics

### Offline Metrics (ML)
- ROC-AUC: ≥0.90
- NDCG@5: ≥0.75
- MAP@5: ≥0.70

### Online Metrics (A/B Testing)
- CTR Uplift: ≥10%
- Conversion Uplift: ≥5%
- ARPU Increase: ≥3%

### Performance Targets
- API Latency p95: ≤150ms
- Error Rate: ≤1%
- Frontend Load Time: <3s

## 🤝 Contributing

This is a capstone project. For development workflow:
1. Follow implementation flow sprints
2. Keep documentation updated
3. Write tests for new features
4. Follow code quality standards (linting, formatting)

## 📄 License

Capstone Project - Dicoding ASAH Program

---

**Note**: This project is under active development. Documentation and features will be updated incrementally following the sprint plan.
