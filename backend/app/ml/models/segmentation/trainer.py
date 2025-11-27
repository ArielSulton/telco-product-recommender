"""
K-Means Segmentation Training Script
====================================

Production training script for customer segmentation model.

Features:
- Data loading from PostgreSQL
- Feature engineering pipeline
- Model training with optimal K selection
- MLflow experiment tracking
- Model evaluation and validation
"""

import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
import pandas as pd
import numpy as np
import mlflow
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.ml.features import FeatureAggregator
from app.ml.models.segmentation.kmeans_segmenter import KMeansSegmenter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SegmentationTrainer:
    """Orchestrate K-Means segmentation model training."""

    def __init__(
        self,
        mlflow_tracking_uri: str = "http://localhost:5000",
        experiment_name: str = "user_segmentation"
    ):
        """
        Initialize training pipeline.

        Args:
            mlflow_tracking_uri: MLflow tracking server URI
            experiment_name: Experiment name for MLflow
        """
        self.mlflow_tracking_uri = mlflow_tracking_uri
        self.experiment_name = experiment_name

        # Setup MLflow
        mlflow.set_tracking_uri(mlflow_tracking_uri)
        mlflow.set_experiment(experiment_name)

        # Initialize components
        self.feature_aggregator = FeatureAggregator()
        self.segmenter = None

    def load_data_from_db(self) -> pd.DataFrame:
        """
        Load transaction data from PostgreSQL.

        Returns:
            DataFrame with transaction data
        """
        from sqlalchemy import create_engine

        engine = create_engine(settings.database_url_sync)

        query = """
            SELECT
                t.user_id,
                t.transaction_id,
                t.transaction_date,
                t.amount,
                u.registration_date
            FROM transactions t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.status = 'completed'
            ORDER BY t.transaction_date
        """

        df = pd.read_sql(query, engine)
        logger.info(f"Loaded {len(df)} transactions from database")

        return df

    def load_data_from_csv(self, csv_path: str) -> pd.DataFrame:
        """
        Load transaction data from CSV (fallback).

        Args:
            csv_path: Path to CSV file

        Returns:
            DataFrame with transaction data
        """
        df = pd.read_csv(csv_path)
        df['transaction_date'] = pd.to_datetime(df['transaction_date'])
        logger.info(f"Loaded {len(df)} transactions from CSV")

        return df

    def train(
        self,
        transactions: pd.DataFrame,
        n_clusters: Optional[int] = None,
        find_optimal: bool = True,
        save_path: Optional[str] = None
    ) -> dict:
        """
        Train K-Means segmentation model.

        Args:
            transactions: Transaction DataFrame
            n_clusters: Number of clusters (if not finding optimal)
            find_optimal: Whether to find optimal K automatically
            save_path: Optional path to save trained model

        Returns:
            Dictionary with training results
        """
        logger.info("Starting segmentation model training...")

        with mlflow.start_run(run_name=f"kmeans_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            # Log input data statistics
            mlflow.log_params({
                "n_transactions": len(transactions),
                "n_users": transactions['user_id'].nunique(),
                "date_range_days": (
                    transactions['transaction_date'].max() -
                    transactions['transaction_date'].min()
                ).days
            })

            # Compute features
            logger.info("Computing user features...")
            features = self.feature_aggregator.compute_batch_features(transactions)
            logger.info(f"Computed features for {len(features)} users")

            mlflow.log_param("n_features", len(features.columns) - 1)  # Exclude user_id

            # Initialize segmenter
            if n_clusters is None:
                n_clusters = settings.N_CLUSTERS

            self.segmenter = KMeansSegmenter(n_clusters=n_clusters)

            # Train model
            logger.info("Training K-Means model...")
            training_metrics = self.segmenter.train(
                features,
                find_optimal=find_optimal
            )

            # Log metrics to MLflow
            for metric_name, metric_value in training_metrics.items():
                if isinstance(metric_value, (int, float)):
                    mlflow.log_metric(metric_name, metric_value)
                elif isinstance(metric_value, dict):
                    mlflow.log_dict(metric_value, f"{metric_name}.json")

            # Log model to MLflow
            mlflow.sklearn.log_model(
                self.segmenter.model,
                "model",
                registered_model_name="kmeans_segmentation"
            )
            mlflow.sklearn.log_model(self.segmenter.scaler, "scaler")

            # Save cluster interpretations
            interpretations = self.segmenter.interpret_segments()
            mlflow.log_dict(interpretations, "segment_interpretations.json")

            logger.info("Segment interpretations:")
            for seg_id, label in interpretations.items():
                logger.info(f"  Segment {seg_id}: {label}")

            # Save model locally if path provided
            if save_path:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                self.segmenter.save_model(save_path)
                logger.info(f"Model saved to {save_path}")

            # Create segment distribution plot
            segment_counts = pd.Series(training_metrics['cluster_sizes'])
            self._plot_segment_distribution(segment_counts, interpretations)

            results = {
                **training_metrics,
                'interpretations': interpretations,
                'feature_names': features.columns.tolist()
            }

            logger.info("Training completed successfully!")
            logger.info(f"Silhouette Score: {training_metrics['silhouette_score']:.4f}")
            logger.info(f"Davies-Bouldin Score: {training_metrics['davies_bouldin_score']:.4f}")

            return results

    def _plot_segment_distribution(
        self,
        segment_counts: pd.Series,
        interpretations: dict
    ) -> None:
        """
        Plot segment distribution and log to MLflow.

        Args:
            segment_counts: Series with segment counts
            interpretations: Dictionary with segment labels
        """
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 6))

        # Create bar plot
        labels = [interpretations.get(seg_id, f"Segment {seg_id}")
                 for seg_id in segment_counts.index]

        ax.bar(range(len(segment_counts)), segment_counts.values)
        ax.set_xticks(range(len(segment_counts)))
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_xlabel('Segment')
        ax.set_ylabel('Number of Users')
        ax.set_title('Customer Segment Distribution')

        plt.tight_layout()

        # Log to MLflow
        mlflow.log_figure(fig, "segment_distribution.png")
        plt.close()

    def evaluate(
        self,
        transactions: pd.DataFrame,
        segmenter: Optional[KMeansSegmenter] = None
    ) -> dict:
        """
        Evaluate segmentation model.

        Args:
            transactions: Transaction DataFrame
            segmenter: Trained segmenter (uses self.segmenter if None)

        Returns:
            Dictionary with evaluation metrics
        """
        if segmenter is None:
            segmenter = self.segmenter

        if segmenter is None or not segmenter.is_trained:
            raise ValueError("No trained segmenter available")

        # Compute features
        features = self.feature_aggregator.compute_batch_features(transactions)

        # Predict segments
        segments = segmenter.predict(features)

        # Analyze segment characteristics
        features['segment_id'] = segments

        segment_stats = {}
        for seg_id in range(segmenter.n_clusters):
            seg_data = features[features['segment_id'] == seg_id]

            segment_stats[seg_id] = {
                'size': len(seg_data),
                'avg_recency': float(seg_data['recency'].mean()),
                'avg_frequency': float(seg_data['frequency'].mean()),
                'avg_monetary': float(seg_data['monetary'].mean()),
                'avg_arpu': float(seg_data['arpu'].mean()) if 'arpu' in seg_data.columns else 0
            }

        return segment_stats


def main():
    """Main training execution."""
    # Initialize trainer
    trainer = SegmentationTrainer(
        mlflow_tracking_uri=settings.MLFLOW_TRACKING_URI,
        experiment_name="user_segmentation"
    )

    # Load data (try database first, fallback to CSV)
    try:
        transactions = trainer.load_data_from_db()
    except Exception as e:
        logger.warning(f"Failed to load from database: {e}")
        logger.info("Falling back to CSV data...")

        csv_path = os.path.join(
            project_root,
            "ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv"
        )
        transactions = trainer.load_data_from_csv(csv_path)

    # Train model
    results = trainer.train(
        transactions=transactions,
        find_optimal=True,
        save_path=os.path.join(
            project_root,
            "backend/app/ml/models/segmentation/kmeans_model.pkl"
        )
    )

    # Print summary
    print("\n" + "=" * 60)
    print("SEGMENTATION MODEL TRAINING COMPLETED")
    print("=" * 60)
    print(f"Number of Clusters: {results['n_clusters']}")
    print(f"Silhouette Score: {results['silhouette_score']:.4f}")
    print(f"Davies-Bouldin Score: {results['davies_bouldin_score']:.4f}")
    print("\nCluster Distribution:")
    for seg_id, count in results['cluster_sizes'].items():
        interpretation = results['interpretations'].get(seg_id, f"Segment {seg_id}")
        print(f"  {interpretation}: {count} users")
    print("=" * 60)


if __name__ == "__main__":
    main()
