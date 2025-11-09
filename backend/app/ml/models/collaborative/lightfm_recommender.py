"""
LightFM Collaborative Filtering
================================

Hybrid collaborative filtering using LightFM with WARP loss.

Features:
- User-item interaction matrix
- Hybrid model with user/item features
- WARP loss for implicit feedback
- Precision@k, Recall@k evaluation
- MLflow integration
"""

from typing import Optional, Dict, List, Tuple
import pandas as pd
import numpy as np
from lightfm import LightFM
from lightfm.data import Dataset
from lightfm.evaluation import precision_at_k, recall_at_k, auc_score
from scipy.sparse import coo_matrix, csr_matrix
import mlflow
import mlflow.pyfunc
import joblib
import logging

logger = logging.getLogger(__name__)


class LightFMRecommender:
    """
    Hybrid collaborative filtering using LightFM.

    Combines user-item interactions with user/item features for personalized recommendations.
    """

    def __init__(
        self,
        no_components: int = 32,
        loss: str = 'warp',
        learning_rate: float = 0.05,
        random_state: int = 42
    ):
        """
        Initialize LightFM recommender.

        Args:
            no_components: Dimensionality of feature latent embeddings
            loss: Loss function ('warp', 'bpr', 'logistic')
            learning_rate: Initial learning rate
            random_state: Random seed
        """
        self.no_components = no_components
        self.loss = loss
        self.learning_rate = learning_rate
        self.random_state = random_state

        self.model = LightFM(
            no_components=no_components,
            loss=loss,
            learning_rate=learning_rate,
            random_state=random_state
        )

        self.dataset = Dataset()
        self.user_id_map = {}
        self.item_id_map = {}
        self.is_trained = False

    def prepare_data(
        self,
        interactions: pd.DataFrame,
        user_features: Optional[pd.DataFrame] = None,
        item_features: Optional[pd.DataFrame] = None
    ) -> Tuple[csr_matrix, Optional[csr_matrix], Optional[csr_matrix]]:
        """
        Prepare interaction matrix and feature matrices.

        Args:
            interactions: DataFrame with [user_id, product_id, rating/weight]
            user_features: Optional user feature DataFrame
            item_features: Optional item feature DataFrame

        Returns:
            Tuple of (interaction_matrix, user_features_matrix, item_features_matrix)
        """
        # Build dataset with users and items
        unique_users = interactions['user_id'].unique()
        unique_items = interactions['product_id'].unique()

        self.dataset.fit(
            users=unique_users,
            items=unique_items
        )

        # Build interaction matrix
        if 'rating' in interactions.columns:
            rating_col = 'rating'
        elif 'weight' in interactions.columns:
            rating_col = 'weight'
        else:
            # Create binary interactions
            interactions['rating'] = 1.0
            rating_col = 'rating'

        (interaction_matrix, weights) = self.dataset.build_interactions(
            interactions[['user_id', 'product_id', rating_col]].itertuples(index=False)
        )

        # Store ID mappings
        user_id_map, _, item_id_map, _ = self.dataset.mapping()
        self.user_id_map = user_id_map
        self.item_id_map = item_id_map

        logger.info(f"Interaction matrix shape: {interaction_matrix.shape}")
        logger.info(f"Number of interactions: {interaction_matrix.nnz}")

        # Build user features matrix (optional)
        user_features_matrix = None
        if user_features is not None:
            user_features_matrix = self._build_user_features(user_features)

        # Build item features matrix (optional)
        item_features_matrix = None
        if item_features is not None:
            item_features_matrix = self._build_item_features(item_features)

        return interaction_matrix, user_features_matrix, item_features_matrix

    def _build_user_features(self, user_features: pd.DataFrame) -> csr_matrix:
        """Build user features matrix for hybrid model."""
        # For now, using simple categorical features
        # Can be extended with continuous features

        feature_list = []
        for _, row in user_features.iterrows():
            user_id = row['user_id']
            features = []

            # Add segment feature
            if 'segment_id' in row:
                features.append(f"segment:{row['segment_id']}")

            # Add ARPU bucket feature
            if 'arpu_bucket' in row:
                features.append(f"arpu:{row['arpu_bucket']}")

            feature_list.append((user_id, features))

        # Fit and build features
        self.dataset.fit_partial(user_features=set(
            feat for _, feats in feature_list for feat in feats
        ))

        user_features_matrix = self.dataset.build_user_features(feature_list)
        logger.info(f"User features matrix shape: {user_features_matrix.shape}")

        return user_features_matrix

    def _build_item_features(self, item_features: pd.DataFrame) -> csr_matrix:
        """Build item features matrix for hybrid model."""
        feature_list = []
        for _, row in item_features.iterrows():
            item_id = row['product_id']
            features = []

            # Add product family feature
            if 'product_family' in row:
                features.append(f"family:{row['product_family']}")

            # Add price bucket feature
            if 'price' in row:
                price_bucket = self._price_bucket(row['price'])
                features.append(f"price:{price_bucket}")

            feature_list.append((item_id, features))

        # Fit and build features
        self.dataset.fit_partial(item_features=set(
            feat for _, feats in feature_list for feat in feats
        ))

        item_features_matrix = self.dataset.build_item_features(feature_list)
        logger.info(f"Item features matrix shape: {item_features_matrix.shape}")

        return item_features_matrix

    def _price_bucket(self, price: float) -> str:
        """Bucket price into categories."""
        if price < 50000:
            return 'low'
        elif price < 100000:
            return 'medium'
        elif price < 200000:
            return 'high'
        else:
            return 'premium'

    def train(
        self,
        interaction_matrix: csr_matrix,
        user_features: Optional[csr_matrix] = None,
        item_features: Optional[csr_matrix] = None,
        epochs: int = 30,
        num_threads: int = 4,
        verbose: bool = True
    ) -> Dict:
        """
        Train LightFM model.

        Args:
            interaction_matrix: User-item interaction matrix
            user_features: Optional user features matrix
            item_features: Optional item features matrix
            epochs: Number of training epochs
            num_threads: Number of parallel threads
            verbose: Whether to print progress

        Returns:
            Dictionary with training metrics
        """
        logger.info("Training LightFM model...")

        self.model.fit(
            interactions=interaction_matrix,
            user_features=user_features,
            item_features=item_features,
            epochs=epochs,
            num_threads=num_threads,
            verbose=verbose
        )

        self.is_trained = True

        # Calculate training metrics
        train_precision = precision_at_k(
            self.model,
            interaction_matrix,
            user_features=user_features,
            item_features=item_features,
            k=5
        ).mean()

        train_recall = recall_at_k(
            self.model,
            interaction_matrix,
            user_features=user_features,
            item_features=item_features,
            k=10
        ).mean()

        train_auc = auc_score(
            self.model,
            interaction_matrix,
            user_features=user_features,
            item_features=item_features
        ).mean()

        metrics = {
            'train_precision_at_5': float(train_precision),
            'train_recall_at_10': float(train_recall),
            'train_auc': float(train_auc),
            'n_users': interaction_matrix.shape[0],
            'n_items': interaction_matrix.shape[1],
            'n_interactions': interaction_matrix.nnz,
            'epochs': epochs
        }

        logger.info(f"Training completed: P@5={train_precision:.4f}, R@10={train_recall:.4f}, AUC={train_auc:.4f}")

        return metrics

    def predict(
        self,
        user_ids: List[str],
        item_ids: Optional[List[str]] = None,
        user_features: Optional[csr_matrix] = None,
        item_features: Optional[csr_matrix] = None,
        top_k: int = 50
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Generate recommendations for users.

        Args:
            user_ids: List of user IDs
            item_ids: Optional list of candidate items (all items if None)
            user_features: Optional user features matrix
            item_features: Optional item features matrix
            top_k: Number of recommendations per user

        Returns:
            Dictionary mapping user_id to list of (product_id, score) tuples
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        recommendations = {}

        # Get all items if not specified
        if item_ids is None:
            item_ids = list(self.item_id_map.keys())

        for user_id in user_ids:
            if user_id not in self.user_id_map:
                recommendations[user_id] = []
                continue

            user_idx = self.user_id_map[user_id]

            # Get item indices
            item_indices = [self.item_id_map[item_id]
                          for item_id in item_ids
                          if item_id in self.item_id_map]

            if not item_indices:
                recommendations[user_id] = []
                continue

            # Predict scores
            scores = self.model.predict(
                user_ids=user_idx,
                item_ids=item_indices,
                user_features=user_features,
                item_features=item_features
            )

            # Get top-K items
            top_indices = np.argsort(-scores)[:top_k]
            top_items = [(item_ids[idx], float(scores[idx])) for idx in top_indices]

            recommendations[user_id] = top_items

        return recommendations

    def save_model(self, path: str) -> None:
        """
        Save trained model to disk.

        Args:
            path: File path for serialization
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        model_data = {
            'model': self.model,
            'dataset': self.dataset,
            'user_id_map': self.user_id_map,
            'item_id_map': self.item_id_map,
            'no_components': self.no_components,
            'loss': self.loss
        }

        joblib.dump(model_data, path)
        logger.info(f"LightFM model saved to {path}")

    def load_model(self, path: str) -> None:
        """
        Load trained model from disk.

        Args:
            path: File path to load from
        """
        model_data = joblib.load(path)

        self.model = model_data['model']
        self.dataset = model_data['dataset']
        self.user_id_map = model_data['user_id_map']
        self.item_id_map = model_data['item_id_map']
        self.no_components = model_data['no_components']
        self.loss = model_data['loss']
        self.is_trained = True

        logger.info(f"LightFM model loaded from {path}")

    def log_to_mlflow(
        self,
        metrics: Dict,
        experiment_name: str = "collaborative_filtering"
    ) -> str:
        """
        Log model and metrics to MLflow.

        Args:
            metrics: Training metrics dictionary
            experiment_name: MLflow experiment name

        Returns:
            MLflow run ID
        """
        mlflow.set_experiment(experiment_name)

        with mlflow.start_run() as run:
            # Log parameters
            mlflow.log_params({
                "no_components": self.no_components,
                "loss": self.loss,
                "learning_rate": self.learning_rate,
                "epochs": metrics.get('epochs', 0)
            })

            # Log metrics
            for metric_name, metric_value in metrics.items():
                if isinstance(metric_value, (int, float)):
                    mlflow.log_metric(metric_name, metric_value)

            # Log model (custom serialization due to LightFM)
            mlflow.log_dict({
                'n_users': len(self.user_id_map),
                'n_items': len(self.item_id_map),
                'model_params': {
                    'no_components': self.no_components,
                    'loss': self.loss
                }
            }, "model_info.json")

            logger.info(f"Model logged to MLflow. Run ID: {run.info.run_id}")

            return run.info.run_id
