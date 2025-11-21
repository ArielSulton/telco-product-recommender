"""
Demo ML Training Script
=======================

Simple training script for bootcamp demo that:
1. Loads customer data from CSV
2. Creates synthetic transaction data
3. Trains TopPopular baseline model
4. Registers model to MLflow with "Production" stage

Usage:
    python scripts/train_demo_model.py
"""

import os
import sys
import pandas as pd
import mlflow
import mlflow.pyfunc
from pathlib import Path
from datetime import datetime, timedelta
import logging
import random

# Determine backend path (works in both dev and production)
BACKEND_PATH = os.getenv('BACKEND_PATH', '/opt/airflow/backend')
if not Path(BACKEND_PATH).exists():
    # Fallback to relative path for local development
    BACKEND_PATH = str(Path(__file__).resolve().parent.parent.parent.parent.parent / "backend")

sys.path.insert(0, BACKEND_PATH)

from app.ml.models.baseline.top_popular import TopPopularRecommender
from app.core.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_customer_data(csv_path: str) -> pd.DataFrame:
    """Load customer data from CSV."""
    logger.info(f"Loading customer data from {csv_path}")
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} customers")
        return df
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")
        raise


def create_synthetic_transactions(customers: pd.DataFrame, n_transactions: int = 5000) -> pd.DataFrame:
    """
    Create synthetic transaction data from customer offers.

    For demo purposes, we simulate transactions where customers
    interact with their target offers.
    """
    logger.info(f"Creating {n_transactions} synthetic transactions")

    transactions = []
    base_date = datetime.now() - timedelta(days=90)

    # Map offers to product IDs
    offer_to_product = {
        'General Offer': 'PROD_GEN_001',
        'Top-up Promo': 'PROD_TOPUP_001',
        'Device Upgrade Offer': 'PROD_DEVICE_001',
        'Data Booster': 'PROD_DATA_001'
    }

    for _ in range(n_transactions):
        # Random customer
        customer = customers.sample(n=1).iloc[0]
        customer_id = customer['customer_id']
        target_offer = customer['target_offer']

        # Map to product ID
        product_id = offer_to_product.get(target_offer, 'PROD_GEN_001')

        # Random date in last 90 days
        days_ago = random.randint(0, 90)
        transaction_date = base_date + timedelta(days=days_ago)

        transactions.append({
            'user_id': customer_id,
            'product_id': product_id,
            'transaction_date': transaction_date
        })

    df_transactions = pd.DataFrame(transactions)
    logger.info(f"Created {len(df_transactions)} transactions")
    logger.info(f"Unique products: {df_transactions['product_id'].nunique()}")
    logger.info(f"Unique users: {df_transactions['user_id'].nunique()}")

    return df_transactions


def train_baseline_model(transactions: pd.DataFrame) -> TopPopularRecommender:
    """Train TopPopular baseline model."""
    logger.info("Training TopPopular baseline model")

    model = TopPopularRecommender(time_window_days=30)
    model.fit(transactions)

    # Get statistics
    stats = model.get_popularity_stats()
    logger.info(f"Model statistics: {stats}")

    return model


def register_to_mlflow(model: TopPopularRecommender, experiment_name: str = "telco-recommender-demo"):
    """Register model to MLflow with Production stage."""
    logger.info(f"Registering model to MLflow experiment: {experiment_name}")

    # Set tracking URI
    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name="baseline-demo"):
        # Log model parameters
        mlflow.log_param("model_type", "TopPopularRecommender")
        mlflow.log_param("time_window_days", model.time_window_days)
        mlflow.log_param("n_products", len(model.global_popularity))

        # Log model statistics
        stats = model.get_popularity_stats()
        for key, value in stats.items():
            mlflow.log_metric(key, value)

        # Save model locally first
        model_path = "/tmp/baseline_model.pkl"
        model.save_model(model_path)

        # Log model to MLflow
        mlflow.log_artifact(model_path, artifact_path="model")

        # Register model
        model_uri = f"runs:/{mlflow.active_run().info.run_id}/model"
        model_name = "baseline-recommender"

        logger.info(f"Registering model: {model_name}")
        mlflow.register_model(model_uri, model_name)

        # Get run ID for promotion
        run_id = mlflow.active_run().info.run_id
        logger.info(f"Model registered. Run ID: {run_id}")

    # Promote to Production stage
    client = mlflow.tracking.MlflowClient()

    # Get latest version
    latest_versions = client.get_latest_versions(model_name, stages=["None"])
    if latest_versions:
        version = latest_versions[0].version
        logger.info(f"Promoting version {version} to Production stage")

        client.transition_model_version_stage(
            name=model_name,
            version=version,
            stage="Production"
        )

        logger.info(f"✅ Model promoted to Production stage (version {version})")

    return run_id


def main():
    """Main training workflow."""
    logger.info("=" * 60)
    logger.info("Starting Demo ML Training")
    logger.info("=" * 60)

    # Paths - flexible for dev and production
    csv_path = os.getenv('DATA_SOURCE_PATH', None)

    if csv_path is None:
        # Try multiple locations
        possible_paths = [
            Path(__file__).resolve().parent.parent.parent.parent.parent / "ml" / "data" / "raw" / "ac-01_telco_customer_behavior_mock_data.csv",
            Path("/app/ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv"),
            Path("/opt/airflow/ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv"),
        ]

        for path in possible_paths:
            if path.exists():
                csv_path = str(path)
                break

    if csv_path is None or not Path(csv_path).exists():
        logger.error(f"CSV file not found. Tried: {possible_paths}")
        sys.exit(1)

    logger.info(f"Using data file: {csv_path}")

    try:
        # 1. Load customer data
        customers = load_customer_data(str(csv_path))

        # 2. Create synthetic transactions
        transactions = create_synthetic_transactions(customers, n_transactions=5000)

        # 3. Train baseline model
        model = train_baseline_model(transactions)

        # 4. Register to MLflow
        run_id = register_to_mlflow(model)

        logger.info("=" * 60)
        logger.info("✅ Demo ML Training Complete")
        logger.info(f"Run ID: {run_id}")
        logger.info(f"Model: baseline-recommender (Production stage)")
        logger.info(f"MLflow URI: {settings.MLFLOW_TRACKING_URI}")
        logger.info("=" * 60)

        # Test recommendation
        logger.info("\nTesting recommendation:")
        test_recs = model.recommend(top_k=5)
        logger.info(f"Top 5 popular products: {test_recs}")

        return 0

    except Exception as e:
        logger.error(f"❌ Training failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
