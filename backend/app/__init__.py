"""
Telco Product Recommender System - Backend Application
========================================================

A production-grade recommendation system for telco products using hybrid ML approach:
- Segmentation: K-Means clustering for user groups
- Candidate Generation: LightFM collaborative filtering
- Ranking: XGBoost for final product scoring
- Diversification: MMR for result variety

Architecture:
- FastAPI for high-performance async API serving
- PostgreSQL for OLTP and feature store
- Redis for real-time feature caching
- MLflow for model versioning and deployment

Author: ASAH Capstone Team
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "ASAH Capstone Team"
