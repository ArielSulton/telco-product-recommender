# ASAH Capstone Project - Telco Product Recommendation Offer based on Customer Behaviour

![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)
![ML Pipeline](https://img.shields.io/badge/ML-LightFM%20%7C%20XGBoost-blue)
![Backend](https://img.shields.io/badge/Backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/Frontend-React%2018-61dafb)

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

**📖 For detailed setup instructions:**
- **[QUICK_START.md](QUICK_START.md)** - Complete Dev & Prod setup guide
- **[CHEAT_SHEET.md](CHEAT_SHEET.md)** - Quick command reference

### Super Quick (Development)
```bash
# 1. Copy environment
cp .env.example .env

# 2. Start everything
docker compose -f compose.dev.yaml up -d

# 3. Wait 2-3 minutes, then access:
# - Frontend: http://localhost:5173
# - Backend: http://localhost:8000/docs
# - Airflow: http://localhost:8080 (admin/admin)
# - Grafana: http://localhost:3000 (admin/admin)
```

## 📚 Documentation

### Quick Reference
- **[QUICK_START.md](QUICK_START.md)** - Dev & Prod setup guide
- **[CHEAT_SHEET.md](CHEAT_SHEET.md)** - Command reference
- **[IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)** - Complete implementation summary

### Detailed Guides
- **[docs/](docs/)** - All documentation (organized)
  - API Documentation
  - Deployment Guide
  - Monitoring Runbook
  - Troubleshooting Guide
  - Sprint Documentation (1-5)
- **[tests/](tests/)** - All test files & testing guide

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
