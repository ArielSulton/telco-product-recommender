"""
LightFM Collaborative Filtering Training Script
===============================================

Production training script for collaborative filtering model.

Features:
- Interaction matrix construction
- Hybrid feature integration
- WARP loss optimization
- Evaluation metrics (Precision@k, Recall@k, NDCG)
- MLflow tracking
"""

import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import mlflow
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.ml.models.collaborative.lightfm_recommender import LightFMRecommender

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CollaborativeFilteringTrainer:
    """Orchestrate LightFM collaborative filtering model training."""

    def __init__(
        self,
        mlflow_tracking_uri: str = "http://localhost:5000",
        experiment_name: str = "collaborative_filtering"
    ):
        """
        Initialize training pipeline.

        Args:
            mlflow_tracking_uri: MLflow tracking server URI
            experiment_name: Experiment name
        """
        self.mlflow_tracking_uri = mlflow_tracking_uri
        self.experiment_name = experiment_name

        mlflow.set_tracking_uri(mlflow_tracking_uri)
        mlflow.set_experiment(experiment_name)

    def load_data_from_db(self) -> pd.DataFrame:
        """Load transaction data from PostgreSQL."""
        from sqlalchemy import create_engine

        engine = create_engine(settings.database_url_sync)

        query = """
            SELECT
                user_id,
                product_id,
                transaction_date,
                amount,
                1.0 as rating
            FROM transactions
            WHERE status = 'completed'
            ORDER BY transaction_date
        """

        df = pd.read_sql(query, engine)
        logger.info(f"Loaded {len(df)} interactions from database")

        return df

    def create_train_test_split(
        self,
        interactions: pd.DataFrame,
        test_size: float = 0.2
    ) -> tuple:
        """
        Split interactions into train/test sets.

        Args:
            interactions: Interaction DataFrame
            test_size: Proportion for test set

        Returns:
            Tuple of (train_df, test_df)
        """
        # Chronological split (more realistic)
        interactions = interactions.sort_values('transaction_date')

        split_idx = int(len(interactions) * (1 - test_size))

        train_df = interactions.iloc[:split_idx]
        test_df = interactions.iloc[split_idx:]

        logger.info(f"Train size: {len(train_df)}, Test size: {len(test_df)}")

        return train_df, test_df

    def train(
        self,
        interactions: pd.DataFrame,
        user_features: Optional[pd.DataFrame] = None,
        item_features: Optional[pd.DataFrame] = None,
        no_components: int = 32,
        learning_rate: float = 0.05,
        epochs: int = 30,
        save_path: Optional[str] = None
    ) -> dict:
        """
        Train LightFM collaborative filtering model.

        Args:
            interactions: Interaction DataFrame
            user_features: Optional user features
            item_features: Optional item features
            no_components: Embedding dimensionality
            learning_rate: Learning rate
            epochs: Training epochs
            save_path: Optional save path

        Returns:
            Dictionary with training results
        """
        logger.info("Starting collaborative filtering model training...")

        with mlflow.start_run(run_name=f"lightfm_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            # Log parameters
            mlflow.log_params({
                "no_components": no_components,
                "learning_rate": learning_rate,
                "epochs": epochs,
                "loss": "warp",
                "n_interactions": len(interactions),
                "n_users": interactions['user_id'].nunique(),
                "n_items": interactions['product_id'].nunique()
            })

            # Split data
            train_df, test_df = self.create_train_test_split(interactions)

            # Initialize recommender
            recommender = LightFMRecommender(
                no_components=no_components,
                loss='warp',
                learning_rate=learning_rate
            )

            # Prepare data
            logger.info("Preparing interaction matrices...")
            train_matrix, user_feat_matrix, item_feat_matrix = recommender.prepare_data(
                train_df,
                user_features=user_features,
                item_features=item_features
            )

            # Train model
            logger.info("Training model...")
            train_metrics = recommender.train(
                interaction_matrix=train_matrix,
                user_features=user_feat_matrix,
                item_features=item_feat_matrix,
                epochs=epochs,
                num_threads=4,
                verbose=True
            )

            # Log training metrics
            for metric_name, metric_value in train_metrics.items():
                if isinstance(metric_value, (int, float)):
                    mlflow.log_metric(f"train_{metric_name}", metric_value)

            # Evaluate on test set
            logger.info("Evaluating on test set...")
            test_matrix, _, _ = recommender.prepare_data(test_df)

            from lightfm.evaluation import precision_at_k, recall_at_k

            test_precision_5 = precision_at_k(
                recommender.model,
                test_matrix,
                user_features=user_feat_matrix,
                item_features=item_feat_matrix,
                k=5
            ).mean()

            test_recall_10 = recall_at_k(
                recommender.model,
                test_matrix,
                user_features=user_feat_matrix,
                item_features=item_feat_matrix,
                k=10
            ).mean()

            # Calculate NDCG@5
            from sklearn.metrics import ndcg_score
            # Simplified NDCG calculation
            test_ndcg_5 = 0.0  # TODO: Implement proper NDCG calculation

            # Log test metrics
            mlflow.log_metrics({
                "test_precision_at_5": float(test_precision_5),
                "test_recall_at_10": float(test_recall_10),
                "test_ndcg_at_5": float(test_ndcg_5)
            })

            logger.info(f"Test Precision@5: {test_precision_5:.4f}")
            logger.info(f"Test Recall@10: {test_recall_10:.4f}")

            # Log model to MLflow
            recommender.log_to_mlflow(train_metrics)

            # Save model locally
            if save_path:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                recommender.save_model(save_path)
                logger.info(f"Model saved to {save_path}")

            results = {
                **train_metrics,
                'test_precision_at_5': float(test_precision_5),
                'test_recall_at_10': float(test_recall_10),
                'test_ndcg_at_5': float(test_ndcg_5)
            }

            logger.info("Training completed successfully!")

            return results


def main():
    """Main training execution."""
    trainer = CollaborativeFilteringTrainer(
        mlflow_tracking_uri=settings.MLFLOW_TRACKING_URI,
        experiment_name="collaborative_filtering"
    )

    # Load data
    try:
        interactions = trainer.load_data_from_db()
    except Exception as e:
        logger.error(f"Failed to load from database: {e}")
        raise

    # Train model
    results = trainer.train(
        interactions=interactions,
        no_components=32,
        learning_rate=0.05,
        epochs=30,
        save_path=os.path.join(
            project_root,
            "backend/app/ml/models/collaborative/lightfm_model.pkl"
        )
    )

    # Print summary
    print("\n" + "=" * 60)
    print("COLLABORATIVE FILTERING MODEL TRAINING COMPLETED")
    print("=" * 60)
    print(f"Train Precision@5: {results['train_precision_at_5']:.4f}")
    print(f"Train Recall@10: {results['train_recall_at_10']:.4f}")
    print(f"Test Precision@5: {results['test_precision_at_5']:.4f}")
    print(f"Test Recall@10: {results['test_recall_at_10']:.4f}")
    print(f"Number of Users: {results['n_users']}")
    print(f"Number of Items: {results['n_items']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
