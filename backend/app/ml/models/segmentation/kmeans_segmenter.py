"""
K-Means Customer Segmentation
==============================

User segmentation using K-Means clustering on RFM and ARPU features.

Features:
- Optimal K selection with elbow method
- Silhouette score validation
- Cluster profiling and interpretation
- MLflow experiment tracking
- Model persistence
"""

from typing import Optional, Dict, Tuple
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, davies_bouldin_score
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import joblib
import logging

logger = logging.getLogger(__name__)


class KMeansSegmenter:
    """
    K-Means clustering for customer segmentation.

    Segments users based on RFM + ARPU features for targeted recommendations.
    """

    def __init__(
        self,
        n_clusters: int = 5,
        random_state: int = 42,
        max_iter: int = 300
    ):
        """
        Initialize K-Means segmenter.

        Args:
            n_clusters: Number of clusters (default: 5)
            random_state: Random seed for reproducibility
            max_iter: Maximum iterations for convergence
        """
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.max_iter = max_iter

        self.model = KMeans(
            n_clusters=n_clusters,
            random_state=random_state,
            max_iter=max_iter,
            n_init=10
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_cols = []
        self.cluster_profiles = None

    def prepare_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare and select features for clustering.

        Args:
            features: DataFrame with user features

        Returns:
            DataFrame with selected features
        """
        # Define feature columns for segmentation
        self.feature_cols = [
            'recency',
            'frequency',
            'monetary',
            'arpu',
            'usage_7d_data_mb',
            'churn_score'
        ]

        # Select available features
        available_cols = [col for col in self.feature_cols if col in features.columns]

        if not available_cols:
            raise ValueError("No valid feature columns found for segmentation")

        X = features[available_cols].copy()

        # Fill missing values
        X = X.fillna(0)

        # Log transform skewed features
        for col in ['monetary', 'arpu']:
            if col in X.columns:
                X[f'log_{col}'] = np.log1p(X[col])
                available_cols.append(f'log_{col}')

        self.feature_cols = available_cols

        return X

    def find_optimal_k(
        self,
        features: pd.DataFrame,
        k_range: range = range(2, 11)
    ) -> Tuple[int, Dict]:
        """
        Find optimal number of clusters using elbow method and silhouette score.

        Args:
            features: Feature DataFrame
            k_range: Range of K values to test

        Returns:
            Tuple of (optimal_k, metrics_dict)
        """
        X = self.prepare_features(features)
        X_scaled = self.scaler.fit_transform(X)

        inertias = []
        silhouette_scores = []
        davies_bouldin_scores = []

        for k in k_range:
            kmeans = KMeans(
                n_clusters=k,
                random_state=self.random_state,
                n_init=10
            )
            labels = kmeans.fit_predict(X_scaled)

            inertias.append(kmeans.inertia_)
            silhouette_scores.append(silhouette_score(X_scaled, labels))
            davies_bouldin_scores.append(davies_bouldin_score(X_scaled, labels))

        # Find elbow point using second derivative
        if len(inertias) >= 3:
            second_derivatives = np.diff(np.diff(inertias))
            optimal_k = k_range[np.argmin(second_derivatives) + 2]
        else:
            # Fallback: use highest silhouette score
            optimal_k = k_range[np.argmax(silhouette_scores)]

        metrics = {
            'k_range': list(k_range),
            'inertias': inertias,
            'silhouette_scores': silhouette_scores,
            'davies_bouldin_scores': davies_bouldin_scores,
            'optimal_k': optimal_k
        }

        logger.info(f"Optimal K found: {optimal_k}")
        logger.info(f"Silhouette scores: {silhouette_scores}")

        return optimal_k, metrics

    def train(
        self,
        features: pd.DataFrame,
        find_optimal: bool = False
    ) -> Dict:
        """
        Train K-Means clustering model.

        Args:
            features: DataFrame with user features
            find_optimal: Whether to find optimal K automatically

        Returns:
            Dictionary with training metrics
        """
        # Find optimal K if requested
        if find_optimal:
            optimal_k, elbow_metrics = self.find_optimal_k(features)
            self.n_clusters = optimal_k
            self.model = KMeans(
                n_clusters=optimal_k,
                random_state=self.random_state,
                max_iter=self.max_iter,
                n_init=10
            )

        # Prepare features
        X = self.prepare_features(features)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Fit K-Means
        labels = self.model.fit_predict(X_scaled)
        self.is_trained = True

        # Calculate metrics
        silhouette = silhouette_score(X_scaled, labels)
        davies_bouldin = davies_bouldin_score(X_scaled, labels)

        # Create cluster profiles
        features_copy = features.copy()
        features_copy['segment_id'] = labels
        self.cluster_profiles = self._profile_clusters(features_copy)

        metrics = {
            'n_clusters': self.n_clusters,
            'silhouette_score': float(silhouette),
            'davies_bouldin_score': float(davies_bouldin),
            'inertia': float(self.model.inertia_),
            'n_features': len(self.feature_cols),
            'cluster_sizes': pd.Series(labels).value_counts().to_dict()
        }

        logger.info(f"K-Means trained: silhouette={silhouette:.4f}, DB={davies_bouldin:.4f}")
        logger.info(f"Cluster sizes: {metrics['cluster_sizes']}")

        return metrics

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """
        Predict cluster assignments for new data.

        Args:
            features: Feature DataFrame

        Returns:
            Array of cluster labels
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        X = self.prepare_features(features)
        X_scaled = self.scaler.transform(X)

        return self.model.predict(X_scaled)

    def _profile_clusters(self, features_with_labels: pd.DataFrame) -> pd.DataFrame:
        """
        Create statistical profiles for each cluster.

        Args:
            features_with_labels: DataFrame with segment_id column

        Returns:
            DataFrame with cluster profiles
        """
        profile_cols = ['recency', 'frequency', 'monetary', 'arpu', 'churn_score']
        available_cols = [col for col in profile_cols if col in features_with_labels.columns]

        if not available_cols:
            return pd.DataFrame()

        profiles = features_with_labels.groupby('segment_id')[available_cols].agg([
            'mean', 'median', 'std', 'min', 'max', 'count'
        ]).round(2)

        return profiles

    def get_cluster_profile(self, segment_id: int) -> Dict:
        """
        Get profile for specific cluster.

        Args:
            segment_id: Cluster ID

        Returns:
            Dictionary with cluster statistics
        """
        if self.cluster_profiles is None:
            return {}

        if segment_id not in self.cluster_profiles.index:
            return {}

        profile = self.cluster_profiles.loc[segment_id].to_dict()
        return profile

    def interpret_segments(self) -> Dict[int, str]:
        """
        Interpret business meaning of each segment.

        Returns:
            Dictionary mapping segment_id to interpretation
        """
        if self.cluster_profiles is None:
            return {}

        interpretations = {}

        for segment_id in range(self.n_clusters):
            profile = self.get_cluster_profile(segment_id)

            if not profile:
                interpretations[segment_id] = f"Segment {segment_id}"
                continue

            # Extract key metrics
            freq = profile.get(('frequency', 'mean'), 0)
            monetary = profile.get(('monetary', 'mean'), 0)
            recency = profile.get(('recency', 'mean'), 999)
            churn = profile.get(('churn_score', 'mean'), 0.5)

            # Interpret based on RFM + churn
            if freq > 10 and monetary > 100000 and recency < 30:
                label = "Champions (High Value, Active)"
            elif freq > 5 and recency < 60:
                label = "Loyal Customers"
            elif churn > 0.7:
                label = "At Risk (High Churn)"
            elif recency > 180:
                label = "Hibernating"
            elif freq < 3:
                label = "New/Occasional Customers"
            else:
                label = f"Segment {segment_id}"

            interpretations[segment_id] = label

        return interpretations

    def log_to_mlflow(
        self,
        experiment_name: str = "user_segmentation",
        run_name: Optional[str] = None
    ) -> str:
        """
        Log model and metrics to MLflow.

        Args:
            experiment_name: MLflow experiment name
            run_name: Optional run name

        Returns:
            MLflow run ID
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        mlflow.set_experiment(experiment_name)

        with mlflow.start_run(run_name=run_name) as run:
            # Log parameters
            mlflow.log_param("n_clusters", self.n_clusters)
            mlflow.log_param("max_iter", self.max_iter)
            mlflow.log_param("n_features", len(self.feature_cols))

            # Log metrics
            mlflow.log_metric("inertia", self.model.inertia_)

            # Log model
            mlflow.sklearn.log_model(
                self.model,
                "kmeans_model",
                registered_model_name="kmeans_segmentation"
            )
            mlflow.sklearn.log_model(self.scaler, "scaler")

            # Log cluster interpretations
            interpretations = self.interpret_segments()
            mlflow.log_dict(interpretations, "cluster_interpretations.json")

            # Log cluster profiles
            if self.cluster_profiles is not None:
                mlflow.log_dict(
                    self.cluster_profiles.to_dict(),
                    "cluster_profiles.json"
                )

            logger.info(f"Model logged to MLflow. Run ID: {run.info.run_id}")

            return run.info.run_id

    def save_model(self, path: str) -> None:
        """
        Save trained model to disk.

        Args:
            path: File path for model serialization
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_cols': self.feature_cols,
            'cluster_profiles': self.cluster_profiles,
            'n_clusters': self.n_clusters
        }

        joblib.dump(model_data, path)
        logger.info(f"K-Means model saved to {path}")

    def load_model(self, path: str) -> None:
        """
        Load trained model from disk.

        Args:
            path: File path to load model from
        """
        model_data = joblib.load(path)

        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_cols = model_data['feature_cols']
        self.cluster_profiles = model_data.get('cluster_profiles')
        self.n_clusters = model_data['n_clusters']
        self.is_trained = True

        logger.info(f"K-Means model loaded from {path}")
