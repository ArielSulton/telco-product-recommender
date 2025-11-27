"""
Train Fixed LightFM Collaborative Filtering Model
==================================================

This script trains a properly implemented LightFM model using actual
product_id instead of segment_id.

Key Fixes:
- Uses transactions with product_id (not segment_id)
- Weighted ratings by transaction amount
- Proper train/test split (chronological)
- Comprehensive evaluation metrics
- MLflow experiment tracking

Expected Performance:
- Precision@5: ≥0.65 (vs 0.20 with old implementation)
- Recall@10: ≥0.75
- AUC: ≥0.85

Usage:
    python ml/scripts/train_fixed_lightfm.py
"""

import sys
import os

# Add backend to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend'))
sys.path.insert(0, backend_path)

from app.ml.models.collaborative.lightfm_recommender_fixed import FixedLightFMRecommender
import pandas as pd
import numpy as np
import mlflow
import mlflow.pyfunc
from sqlalchemy import create_engine
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_transaction_data(engine):
    """Load transaction data from database."""
    logger.info("Loading transaction data...")

    query = """
    SELECT
        user_id,
        product_id,
        amount,
        transaction_date
    FROM transactions
    WHERE status = 'completed'
    AND transaction_date >= NOW() - INTERVAL '90 days'
    ORDER BY transaction_date
    """

    transactions_df = pd.read_sql(query, engine)

    logger.info(f"Loaded {len(transactions_df)} transactions")
    logger.info(f"Unique users: {transactions_df['user_id'].nunique()}")
    logger.info(f"Unique products: {transactions_df['product_id'].nunique()}")
    logger.info(f"Date range: {transactions_df['transaction_date'].min()} to {transactions_df['transaction_date'].max()}")

    return transactions_df


def train_test_split(transactions_df, test_size=0.2):
    """
    Chronological train/test split.

    Args:
        transactions_df: Transaction DataFrame
        test_size: Fraction for test set (default: 0.2)

    Returns:
        train_df, test_df
    """
    logger.info("Splitting data chronologically...")

    # Sort by date
    transactions_sorted = transactions_df.sort_values('transaction_date')

    # Split index
    split_idx = int(len(transactions_sorted) * (1 - test_size))

    train_df = transactions_sorted.iloc[:split_idx].copy()
    test_df = transactions_sorted.iloc[split_idx:].copy()

    logger.info(f"Train set: {len(train_df)} transactions "
               f"({train_df['user_id'].nunique()} users, "
               f"{train_df['product_id'].nunique()} products)")
    logger.info(f"Test set: {len(test_df)} transactions "
               f"({test_df['user_id'].nunique()} users, "
               f"{test_df['product_id'].nunique()} products)")

    return train_df, test_df


def evaluate_model(model, test_interactions):
    """
    Evaluate model on test set.

    Args:
        model: Trained FixedLightFMRecommender
        test_interactions: Test interaction matrix

    Returns:
        Dictionary of metrics
    """
    logger.info("Evaluating model on test set...")

    metrics = model.evaluate(test_interactions, k_values=[5, 10, 20])

    logger.info("Test Metrics:")
    for metric_name, value in metrics.items():
        logger.info(f"  {metric_name}: {value:.4f}")

    return metrics


def main():
    """Main training function."""
    logger.info("=" * 60)
    logger.info("Fixed LightFM Collaborative Filtering Training")
    logger.info("=" * 60)

    # Database connection
    db_url = os.getenv(
        'DATABASE_URL',
        'postgresql://telco:password@localhost:5432/telco_recommender'
    )
    engine = create_engine(db_url)

    # Load data
    transactions_df = load_transaction_data(engine)

    # Train/test split
    train_df, test_df = train_test_split(transactions_df, test_size=0.2)

    # Initialize model
    logger.info("\nInitializing FixedLightFMRecommender...")
    cf_model = FixedLightFMRecommender(
        no_components=50,
        loss='warp',
        learning_rate=0.05,
        user_alpha=1e-6,
        item_alpha=1e-6
    )

    # Prepare training data
    logger.info("\nPreparing training interaction matrix...")
    train_interactions = cf_model.prepare_data(
        interactions_df=train_df[['user_id', 'product_id', 'amount']],
        weight_by_amount=True
    )

    # Prepare test data (using same model mappings)
    logger.info("Preparing test interaction matrix...")
    # Re-use model's mappings for test data
    test_user_indices = test_df['user_id'].map(cf_model.user_id_map)
    test_product_indices = test_df['product_id'].map(cf_model.product_id_map)

    # Filter out users/products not in training
    test_mask = test_user_indices.notna() & test_product_indices.notna()
    test_filtered = test_df[test_mask].copy()

    logger.info(f"Test samples after filtering: {len(test_filtered)} "
               f"(removed {len(test_df) - len(test_filtered)} cold-start samples)")

    # Create test interaction matrix
    from scipy.sparse import coo_matrix

    if len(test_filtered) > 0:
        test_user_idx = test_filtered['user_id'].map(cf_model.user_id_map).values
        test_product_idx = test_filtered['product_id'].map(cf_model.product_id_map).values

        # Weighted ratings
        amounts = test_filtered['amount'].values
        min_amount = amounts.min()
        max_amount = amounts.max()
        if max_amount > min_amount:
            test_ratings = 0.5 + 0.5 * (amounts - min_amount) / (max_amount - min_amount)
        else:
            test_ratings = np.ones(len(amounts))

        test_interactions = coo_matrix(
            (test_ratings, (test_user_idx, test_product_idx)),
            shape=train_interactions.shape,
            dtype=np.float32
        )

        logger.info(f"Test interaction matrix: {test_interactions.shape}, "
                   f"nnz: {test_interactions.nnz}")
    else:
        logger.warning("No test data after filtering! Using train as test.")
        test_interactions = train_interactions

    # MLflow tracking
    mlflow_uri = os.getenv('MLFLOW_TRACKING_URI', 'http://localhost:5000')
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment('collaborative_filtering_fixed')

    logger.info(f"\nMLflow tracking URI: {mlflow_uri}")

    # Train with MLflow tracking
    with mlflow.start_run(run_name=f"lightfm_fixed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
        # Log parameters
        mlflow.log_param('model_type', 'FixedLightFMRecommender')
        mlflow.log_param('no_components', 50)
        mlflow.log_param('loss', 'warp')
        mlflow.log_param('learning_rate', 0.05)
        mlflow.log_param('user_alpha', 1e-6)
        mlflow.log_param('item_alpha', 1e-6)
        mlflow.log_param('epochs', 30)
        mlflow.log_param('n_users', train_interactions.shape[0])
        mlflow.log_param('n_products', train_interactions.shape[1])
        mlflow.log_param('n_train_interactions', train_interactions.nnz)
        mlflow.log_param('n_test_interactions', test_interactions.nnz)
        mlflow.log_param('sparsity', 1 - train_interactions.nnz / (train_interactions.shape[0] * train_interactions.shape[1]))

        # Train
        logger.info("\nTraining model (30 epochs)...")
        train_metrics = cf_model.train(
            interaction_matrix=train_interactions,
            epochs=30,
            num_threads=4,
            verbose=True
        )

        # Log training metrics
        for metric_name, value in train_metrics.items():
            mlflow.log_metric(metric_name, value)

        # Evaluate on test set
        test_metrics = evaluate_model(cf_model, test_interactions)

        # Log test metrics
        for metric_name, value in test_metrics.items():
            mlflow.log_metric(metric_name, value)

        # Save model
        model_path = '/tmp/lightfm_fixed.pkl'
        cf_model.save_model(model_path)
        mlflow.log_artifact(model_path, 'model')

        # Register model to MLflow Model Registry
        model_uri = f"runs:/{mlflow.active_run().info.run_id}/model/lightfm_fixed.pkl"
        mlflow.register_model(model_uri, "lightfm_collaborative_fixed")

        run_id = mlflow.active_run().info.run_id

        logger.info("\n" + "=" * 60)
        logger.info("✅ Training Complete!")
        logger.info("=" * 60)
        logger.info(f"MLflow Run ID: {run_id}")
        logger.info(f"Model saved to: {model_path}")
        logger.info("\nTraining Metrics:")
        for metric, value in train_metrics.items():
            logger.info(f"  {metric}: {value:.4f}")
        logger.info("\nTest Metrics:")
        for metric, value in test_metrics.items():
            logger.info(f"  {metric}: {value:.4f}")

        # Performance comparison
        logger.info("\n" + "-" * 60)
        logger.info("Performance Comparison:")
        logger.info("-" * 60)
        logger.info("Metric              | Old LightFM | Fixed LightFM | Improvement")
        logger.info("-" * 60)
        logger.info(f"Precision@5         |    0.200    |    {test_metrics.get('test_precision_at_5', 0):.3f}     |  {(test_metrics.get('test_precision_at_5', 0) - 0.200) / 0.200 * 100:+.1f}%")
        logger.info(f"Recall@10           |    0.350    |    {test_metrics.get('test_recall_at_10', 0):.3f}     |  {(test_metrics.get('test_recall_at_10', 0) - 0.350) / 0.350 * 100:+.1f}%")
        logger.info(f"AUC                 |    0.450    |    {test_metrics.get('test_auc', 0):.3f}     |  {(test_metrics.get('test_auc', 0) - 0.450) / 0.450 * 100:+.1f}%")
        logger.info("-" * 60)

        # Targets check
        logger.info("\n" + "-" * 60)
        logger.info("Target Achievement:")
        logger.info("-" * 60)

        p5_target = 0.65
        r10_target = 0.75
        auc_target = 0.85

        p5_status = "✅ PASS" if test_metrics.get('test_precision_at_5', 0) >= p5_target else "❌ FAIL"
        r10_status = "✅ PASS" if test_metrics.get('test_recall_at_10', 0) >= r10_target else "❌ FAIL"
        auc_status = "✅ PASS" if test_metrics.get('test_auc', 0) >= auc_target else "❌ FAIL"

        logger.info(f"Precision@5 ≥ {p5_target}: {test_metrics.get('test_precision_at_5', 0):.4f} {p5_status}")
        logger.info(f"Recall@10 ≥ {r10_target}:  {test_metrics.get('test_recall_at_10', 0):.4f} {r10_status}")
        logger.info(f"AUC ≥ {auc_target}:        {test_metrics.get('test_auc', 0):.4f} {auc_status}")
        logger.info("-" * 60)

    logger.info("\nNext Steps:")
    logger.info("1. Review MLflow UI: http://localhost:5000")
    logger.info("2. Promote model to Production stage if metrics are good")
    logger.info("3. Update model loading in backend/app/main.py")
    logger.info("4. Run A/B test: FixedLightFM vs EnhancedBaseline")
    logger.info("5. Deploy to staging environment")


if __name__ == '__main__':
    main()
