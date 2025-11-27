# ML Pipeline - Telco Product Recommender

Machine learning pipeline for training and evaluating the hybrid recommendation system.

## Overview

Hybrid recommender combining:
1. **Segmentation**: K-Means clustering on user features
2. **Collaborative Filtering**: LightFM for candidate generation
3. **Ranking**: XGBoost for final product ordering
4. **Explainability**: SHAP for recommendation reasoning

## Technology Stack

- **Framework**: scikit-learn, LightFM, XGBoost
- **Data Processing**: pandas, numpy
- **Experiment Tracking**: MLflow
- **Evaluation**: Custom metrics (NDCG, MAP, ROC-AUC)
- **Notebooks**: Jupyter
- **Visualization**: matplotlib, seaborn

## Project Structure

```
ml/
├── data/
│   ├── raw/              # Raw transaction/event data
│   ├── processed/        # Cleaned datasets
│   └── features/         # Engineered features
├── notebooks/
│   ├── 01_eda.ipynb                     # Exploratory analysis
│   ├── 02_feature_engineering.ipynb
│   ├── 03_segmentation.ipynb           # K-Means
│   ├── 04_collaborative_filtering.ipynb # LightFM
│   ├── 05_ranking_model.ipynb          # XGBoost
│   └── 06_evaluation.ipynb
├── src/
│   ├── data/            # ETL & preprocessing
│   ├── features/        # Feature engineering (RFM, ARPU, etc.)
│   ├── models/          # Model training scripts
│   ├── evaluation/      # Metrics & analysis
│   └── utils/           # Helper functions
└── scripts/             # Training & evaluation scripts
```

## Setup Instructions

### Prerequisites
- Python 3.10+
- MLflow server running (for experiment tracking)

### Installation

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure MLflow**:
   ```bash
   export MLFLOW_TRACKING_URI=http://localhost:5000
   ```

4. **Start Jupyter**:
   ```bash
   jupyter notebook
   ```

## Feature Engineering

### RFM Features
- **Recency**: Days since last purchase
- **Frequency**: Number of purchases
- **Monetary**: Total spending

### Usage Metrics
- `usage_7d_data_mb`: Data consumption (last 7 days)
- `usage_7d_voice_min`: Voice minutes used
- `usage_7d_sms`: SMS count

### ARPU Buckets
- Low: <50K IDR/month
- Medium: 50K-100K
- High: 100K-200K
- Premium: >200K

### Churn Score
Predicted probability of churn using RandomForest on behavioral features.

## Model Training

### 1. Segmentation (K-Means)
```bash
python scripts/train_segmentation.py
```

**Output**: User segment labels (0-4)

**Target**: Silhouette score >0.6

### 2. Collaborative Filtering (LightFM)
```bash
python scripts/train_collaborative.py
```

**Output**: User/item embeddings for candidate generation

**Target**: Precision@50 >0.7

### 3. Ranking (XGBoost)
```bash
python scripts/train_ranker.py
```

**Output**: Pairwise ranking model

**Target**: NDCG@5 ≥0.75, MAP@5 ≥0.70

### 4. Full Pipeline Evaluation
```bash
python scripts/evaluate_models.py
```

## Evaluation Metrics

### Offline Metrics

| Metric | Target | Purpose |
|--------|--------|---------|
| ROC-AUC | ≥0.90 | Per-segment classification |
| NDCG@5 | ≥0.75 | Ranking quality (top-5) |
| MAP@5 | ≥0.70 | Precision at top-5 |
| Coverage | ≥80% | Catalog diversity |
| Cold-start Hit Rate | ≥60% | New user performance |

### Online Metrics (A/B Test)

| Metric | Target |
|--------|--------|
| CTR Uplift | ≥10% |
| Conversion Uplift | ≥5% |
| ARPU Increase | ≥3% |

## MLflow Integration

All experiments logged to MLflow:
- Hyperparameters
- Training metrics
- Model artifacts
- Feature importance

Access MLflow UI: http://localhost:5000

## Experiment Tracking

### Best Practices
1. Always set experiment name: `mlflow.set_experiment("name")`
2. Log all hyperparameters: `mlflow.log_param()`
3. Log evaluation metrics: `mlflow.log_metric()`
4. Save model artifacts: `mlflow.sklearn.log_model()`
5. Tag runs appropriately: `mlflow.set_tag()`

## Model Deployment

Trained models saved to MLflow Model Registry:
```python
# Register model
mlflow.register_model(
    f"runs:/{run_id}/model",
    "telco_recommender_ranker"
)

# Promote to production
client.transition_model_version_stage(
    name="telco_recommender_ranker",
    version=3,
    stage="Production"
)
```

## Retraining Schedule

- **Daily**: Feature recalculation (Airflow DAG)
- **Weekly**: Model retraining (if drift detected)
- **Monthly**: Full pipeline re-evaluation

## Data Requirements

### Minimum Dataset Size
- Users: ≥10K
- Products: ≥50
- Transactions: ≥100K
- Events: ≥500K

### Data Quality Checks
- Missing values: <5%
- Duplicate transactions: 0%
- Invalid product IDs: 0%
- Date range coverage: ≥6 months

## Status

🚧 **Under Development** - Sprint 2-4 implementation in progress

Waiting for:
- [ ] Historical transaction dataset
- [ ] Product catalog data
- [ ] User interaction events

See `../IMPLEMENTATION_FLOW.md` for detailed implementation roadmap.

## Quick Start (Once Data Available)

```bash
# 1. EDA
jupyter notebook notebooks/01_eda.ipynb

# 2. Feature engineering
jupyter notebook notebooks/02_feature_engineering.ipynb

# 3. Train models
python scripts/train_segmentation.py
python scripts/train_collaborative.py
python scripts/train_ranker.py

# 4. Evaluate
python scripts/evaluate_models.py
```
