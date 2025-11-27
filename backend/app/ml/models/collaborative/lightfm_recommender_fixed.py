"""
Fixed LightFM Collaborative Filtering Recommender
==================================================

Corrects the critical bug where segment_id was used instead of product_id.

Key Changes from Original:
1. ✅ Uses actual product_id from transactions
2. ✅ Proper user/item mapping with reverse lookup
3. ✅ Weighted ratings (transaction amount)
4. ✅ Cold start handling
5. ✅ Comprehensive evaluation metrics

Author: ML Team
Date: 2025-11-27
"""

from lightfm import LightFM
from lightfm.evaluation import precision_at_k, recall_at_k, auc_score
from scipy.sparse import coo_matrix
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import pickle
import logging

logger = logging.getLogger(__name__)


class FixedLightFMRecommender:
    """
    Collaborative Filtering using LightFM with WARP loss.

    FIXED: Uses actual product_id instead of segment_id for item embeddings.

    This implementation corrects the fundamental issue in the original
    LightFMRecommender where segment_id (5 values) was incorrectly used
    instead of product_id (50 values), resulting in poor recommendation quality.

    Architecture:
    - Matrix Factorization with WARP loss (optimized for ranking)
    - Learns latent user and item representations
    - Supports implicit feedback (purchases, views)
    - Handles cold start with graceful degradation

    Performance Targets:
    - Precision@5: ≥0.65 (vs 0.20 with old implementation)
    - Recall@10: ≥0.75
    - AUC: ≥0.85
    """

    def __init__(
        self,
        no_components: int = 50,
        loss: str = 'warp',
        learning_rate: float = 0.05,
        user_alpha: float = 1e-6,
        item_alpha: float = 1e-6
    ):
        """
        Initialize LightFM recommender.

        Args:
            no_components: Number of latent factors (embedding dimension)
            loss: Loss function:
                - 'warp': WARP loss (best for ranking tasks)
                - 'bpr': Bayesian Personalized Ranking
                - 'logistic': Logistic loss
            learning_rate: Learning rate for gradient descent
            user_alpha: L2 penalty on user feature weights
            item_alpha: L2 penalty on item feature weights
        """
        self.model = LightFM(
            no_components=no_components,
            loss=loss,
            learning_rate=learning_rate,
            user_alpha=user_alpha,
            item_alpha=item_alpha,
            random_state=42
        )

        # ID mappings for user and product indices
        self.user_id_map = {}
        self.product_id_map = {}
        self.reverse_user_map = {}
        self.reverse_product_map = {}

        self.is_fitted = False

        # Hyperparameters for reference
        self.no_components = no_components
        self.loss = loss
        self.learning_rate = learning_rate

    def prepare_data(
        self,
        interactions_df: pd.DataFrame,
        weight_by_amount: bool = True
    ) -> coo_matrix:
        """
        Prepare interaction matrix from transaction data.

        Args:
            interactions_df: DataFrame with columns:
                - user_id (int): User identifier
                - product_id (int): Product identifier
                - amount (float, optional): Transaction amount for weighting
            weight_by_amount: If True and 'amount' column exists,
                weight interactions by normalized transaction amount.
                Otherwise use binary (1.0) implicit feedback.

        Returns:
            Sparse COO matrix (users x products) with interaction strengths

        Raises:
            ValueError: If required columns missing
        """
        # Validate input
        required_cols = ['user_id', 'product_id']
        if not all(col in interactions_df.columns for col in required_cols):
            raise ValueError(f"interactions_df must have columns: {required_cols}")

        logger.info(f"Preparing data from {len(interactions_df)} interactions")

        # Create mappings (CRITICAL FIX: using product_id, not segment_id!)
        unique_users = interactions_df['user_id'].unique()
        unique_products = interactions_df['product_id'].unique()

        self.user_id_map = {uid: idx for idx, uid in enumerate(unique_users)}
        self.product_id_map = {pid: idx for idx, pid in enumerate(unique_products)}
        self.reverse_user_map = {idx: uid for uid, idx in self.user_id_map.items()}
        self.reverse_product_map = {idx: pid for pid, idx in self.product_id_map.items()}

        logger.info(f"Created mappings: {len(unique_users)} users, {len(unique_products)} products")

        # Map IDs to indices
        user_indices = interactions_df['user_id'].map(self.user_id_map).values
        product_indices = interactions_df['product_id'].map(self.product_id_map).values

        # Calculate ratings
        if weight_by_amount and 'amount' in interactions_df.columns:
            # Normalize amounts to [0.5, 1.0] range
            # Higher amounts = stronger signal
            amounts = interactions_df['amount'].values
            min_amount = amounts.min()
            max_amount = amounts.max()

            if max_amount > min_amount:
                ratings = 0.5 + 0.5 * (amounts - min_amount) / (max_amount - min_amount)
            else:
                ratings = np.ones(len(amounts))

            logger.info(f"Using weighted ratings (range: {ratings.min():.2f} - {ratings.max():.2f})")
        else:
            # Implicit feedback (binary)
            ratings = np.ones(len(interactions_df))
            logger.info("Using binary implicit feedback")

        # Create sparse matrix
        interaction_matrix = coo_matrix(
            (ratings, (user_indices, product_indices)),
            shape=(len(unique_users), len(unique_products)),
            dtype=np.float32
        )

        sparsity = 1 - interaction_matrix.nnz / (interaction_matrix.shape[0] * interaction_matrix.shape[1])
        logger.info(f"Interaction matrix: {interaction_matrix.shape}, "
                   f"sparsity: {sparsity:.4f}, "
                   f"nnz: {interaction_matrix.nnz}")

        return interaction_matrix

    def train(
        self,
        interaction_matrix: coo_matrix,
        epochs: int = 30,
        num_threads: int = 4,
        verbose: bool = False
    ) -> Dict[str, float]:
        """
        Train LightFM model using WARP loss.

        Args:
            interaction_matrix: User-item interaction matrix (sparse COO)
            epochs: Number of training epochs
            num_threads: Number of parallel threads for training
            verbose: Print training progress

        Returns:
            Dictionary of training metrics:
            - train_precision_at_5: Precision@5 on training set
            - train_recall_at_10: Recall@10 on training set
            - train_auc: Area Under ROC Curve
        """
        logger.info(f"Training LightFM model for {epochs} epochs...")

        # Train model
        self.model.fit(
            interaction_matrix,
            epochs=epochs,
            num_threads=num_threads,
            verbose=verbose
        )

        self.is_fitted = True
        logger.info("✅ Training complete")

        # Evaluate on training set (as baseline)
        train_precision = precision_at_k(self.model, interaction_matrix, k=5).mean()
        train_recall = recall_at_k(self.model, interaction_matrix, k=10).mean()
        train_auc = auc_score(self.model, interaction_matrix).mean()

        metrics = {
            'train_precision_at_5': float(train_precision),
            'train_recall_at_10': float(train_recall),
            'train_auc': float(train_auc)
        }

        logger.info(f"Training metrics: P@5={train_precision:.4f}, "
                   f"R@10={train_recall:.4f}, AUC={train_auc:.4f}")

        return metrics

    def recommend(
        self,
        user_id: int,
        n_recommendations: int = 50,
        exclude_products: Optional[List[int]] = None
    ) -> List[Dict]:
        """
        Generate collaborative filtering recommendations for a user.

        Args:
            user_id: User ID to generate recommendations for
            n_recommendations: Number of recommendations to return
            exclude_products: List of product IDs to exclude (e.g., already purchased)

        Returns:
            List of recommendation dictionaries with:
            - product_id (int): Recommended product ID
            - score (float): Recommendation score
            - strategy (str): 'collaborative_filtering'

        Raises:
            ValueError: If model not trained
        """
        if not self.is_fitted:
            raise ValueError("Model not trained. Call train() first.")

        # Cold start handling - return empty if user unknown
        if user_id not in self.user_id_map:
            logger.warning(f"Cold start: user_id {user_id} not in training data")
            return []

        user_idx = self.user_id_map[user_id]
        n_items = len(self.product_id_map)

        # Predict scores for all products
        item_indices = np.arange(n_items)
        scores = self.model.predict(user_idx, item_indices)

        # Exclude products if specified
        if exclude_products:
            exclude_indices = [
                self.product_id_map.get(pid)
                for pid in exclude_products
                if pid in self.product_id_map
            ]
            if exclude_indices:
                scores[exclude_indices] = -np.inf

        # Get top N
        top_indices = np.argsort(-scores)[:n_recommendations]

        recommendations = [
            {
                'product_id': self.reverse_product_map[idx],
                'score': float(scores[idx]),
                'strategy': 'collaborative_filtering'
            }
            for idx in top_indices
            if scores[idx] > -np.inf  # Filter out excluded products
        ]

        logger.debug(f"Generated {len(recommendations)} CF recommendations for user {user_id}")

        return recommendations

    def evaluate(
        self,
        test_interactions: coo_matrix,
        k_values: List[int] = [5, 10]
    ) -> Dict[str, float]:
        """
        Evaluate model on test set.

        Args:
            test_interactions: Test interaction matrix (same shape as training)
            k_values: List of k values for precision@k and recall@k

        Returns:
            Dictionary of evaluation metrics
        """
        if not self.is_fitted:
            raise ValueError("Model not trained. Call train() first.")

        metrics = {}

        # Precision@k and Recall@k for each k
        for k in k_values:
            precision = precision_at_k(self.model, test_interactions, k=k).mean()
            recall = recall_at_k(self.model, test_interactions, k=k).mean()

            metrics[f'test_precision_at_{k}'] = float(precision)
            metrics[f'test_recall_at_{k}'] = float(recall)

        # AUC
        auc = auc_score(self.model, test_interactions).mean()
        metrics['test_auc'] = float(auc)

        logger.info(f"Test metrics: {metrics}")

        return metrics

    def get_user_embeddings(self, user_ids: Optional[List[int]] = None) -> np.ndarray:
        """
        Get user embeddings (latent representations).

        Args:
            user_ids: List of user IDs. If None, returns all user embeddings.

        Returns:
            Array of user embeddings (n_users x no_components)
        """
        if not self.is_fitted:
            raise ValueError("Model not trained. Call train() first.")

        if user_ids is None:
            # Return all user embeddings
            user_indices = np.arange(len(self.user_id_map))
        else:
            # Map user IDs to indices
            user_indices = [
                self.user_id_map[uid]
                for uid in user_ids
                if uid in self.user_id_map
            ]

        # Get embeddings from model
        user_embeddings, _ = self.model.get_user_representations()

        return user_embeddings[user_indices]

    def get_item_embeddings(self, product_ids: Optional[List[int]] = None) -> np.ndarray:
        """
        Get item embeddings (latent representations).

        Args:
            product_ids: List of product IDs. If None, returns all item embeddings.

        Returns:
            Array of item embeddings (n_items x no_components)
        """
        if not self.is_fitted:
            raise ValueError("Model not trained. Call train() first.")

        if product_ids is None:
            # Return all item embeddings
            item_indices = np.arange(len(self.product_id_map))
        else:
            # Map product IDs to indices
            item_indices = [
                self.product_id_map[pid]
                for pid in product_ids
                if pid in self.product_id_map
            ]

        # Get embeddings from model
        _, item_embeddings = self.model.get_item_representations()

        return item_embeddings[item_indices]

    def save_model(self, filepath: str):
        """
        Save model to disk.

        Args:
            filepath: Path to save model (e.g., 'models/lightfm_fixed.pkl')
        """
        model_data = {
            'model': self.model,
            'user_id_map': self.user_id_map,
            'product_id_map': self.product_id_map,
            'reverse_user_map': self.reverse_user_map,
            'reverse_product_map': self.reverse_product_map,
            'is_fitted': self.is_fitted,
            'no_components': self.no_components,
            'loss': self.loss,
            'learning_rate': self.learning_rate
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Model saved to {filepath}")

    def load_model(self, filepath: str):
        """
        Load model from disk.

        Args:
            filepath: Path to load model from
        """
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data['model']
        self.user_id_map = model_data['user_id_map']
        self.product_id_map = model_data['product_id_map']
        self.reverse_user_map = model_data['reverse_user_map']
        self.reverse_product_map = model_data['reverse_product_map']
        self.is_fitted = model_data['is_fitted']
        self.no_components = model_data.get('no_components', 50)
        self.loss = model_data.get('loss', 'warp')
        self.learning_rate = model_data.get('learning_rate', 0.05)

        logger.info(f"Model loaded from {filepath}")

    def __repr__(self):
        """String representation of the recommender."""
        status = "fitted" if self.is_fitted else "not fitted"
        n_users = len(self.user_id_map) if self.user_id_map else 0
        n_products = len(self.product_id_map) if self.product_id_map else 0

        return (f"FixedLightFMRecommender("
                f"no_components={self.no_components}, "
                f"loss='{self.loss}', "
                f"users={n_users}, "
                f"products={n_products}, "
                f"status={status})")
