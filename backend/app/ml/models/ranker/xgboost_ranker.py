"""
XGBoost Learning-to-Rank Model
================================

LambdaRank implementation for re-ranking candidate recommendations.

Features:
- Pairwise/listwise ranking objective
- Cross-validation with stratified groups
- Feature importance analysis with SHAP
- MLflow experiment tracking
- NDCG@k, Precision@k, MRR evaluation
"""

from typing import Optional, Dict, List, Tuple
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import GroupKFold
from sklearn.metrics import ndcg_score
import shap
import mlflow
import mlflow.xgboost
import joblib
import logging

logger = logging.getLogger(__name__)


class XGBoostRanker:
    """
    XGBoost learning-to-rank model for product recommendation re-ranking.

    Uses LambdaRank objective to optimize ranking metrics (NDCG, MRR).
    """

    def __init__(
        self,
        objective: str = 'rank:pairwise',
        learning_rate: float = 0.1,
        max_depth: int = 6,
        n_estimators: int = 100,
        min_child_weight: int = 1,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42
    ):
        """
        Initialize XGBoost ranker.

        Args:
            objective: Ranking objective ('rank:pairwise', 'rank:ndcg', 'rank:map')
            learning_rate: Boosting learning rate
            max_depth: Maximum tree depth
            n_estimators: Number of boosting rounds
            min_child_weight: Minimum sum of instance weight in child
            subsample: Subsample ratio of training instances
            colsample_bytree: Subsample ratio of features
            random_state: Random seed
        """
        self.objective = objective
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.n_estimators = n_estimators
        self.min_child_weight = min_child_weight
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.random_state = random_state

        self.model = xgb.XGBRanker(
            objective=objective,
            learning_rate=learning_rate,
            max_depth=max_depth,
            n_estimators=n_estimators,
            min_child_weight=min_child_weight,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            random_state=random_state
        )

        self.feature_names = []
        self.is_trained = False
        self.explainer = None

    def prepare_features(
        self,
        interactions: pd.DataFrame,
        user_features: pd.DataFrame,
        product_features: pd.DataFrame,
        cf_scores: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.DataFrame, pd.Series, np.ndarray]:
        """
        Engineer features for ranking model.

        Args:
            interactions: User-product interactions with labels
            user_features: User RFM, ARPU, segment features
            product_features: Product metadata features
            cf_scores: Optional collaborative filtering scores

        Returns:
            Tuple of (X, y, groups) for ranking
        """
        # Merge user features
        data = interactions.merge(
            user_features,
            on='user_id',
            how='left'
        )

        # Merge product features
        data = data.merge(
            product_features,
            on='product_id',
            how='left'
        )

        # Add CF scores if available
        if cf_scores is not None:
            data = data.merge(
                cf_scores,
                on=['user_id', 'product_id'],
                how='left'
            )
            data['cf_score'] = data['cf_score'].fillna(0)

        # Engineer interaction features
        data = self._engineer_features(data)

        # Define feature columns
        feature_cols = self._get_feature_columns(data)
        self.feature_names = feature_cols

        # Prepare X, y, groups
        X = data[feature_cols].fillna(0)
        y = data['label']  # 1 for purchased, 0 for not purchased

        # Groups for ranking (one group per user)
        groups = data.groupby('user_id').size().values

        logger.info(f"Prepared {len(X)} samples, {len(feature_cols)} features, {len(groups)} groups")

        return X, y, groups

    def _engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Engineer additional ranking features."""
        df = data.copy()

        # User-product fit features
        if 'arpu' in df.columns and 'price' in df.columns:
            df['price_to_arpu_ratio'] = df['price'] / (df['arpu'] + 1)
            df['can_afford'] = (df['price'] <= df['arpu'] * 1.5).astype(int)

        # Usage-quota fit features
        if 'usage_7d_data_mb' in df.columns and 'quota_data_mb' in df.columns:
            df['quota_to_usage_ratio'] = df['quota_data_mb'] / (df['usage_7d_data_mb'] + 1)
            df['quota_sufficient'] = (df['quota_data_mb'] >= df['usage_7d_data_mb'] * 0.8).astype(int)

        # Recency features
        if 'recency' in df.columns:
            df['is_recent_customer'] = (df['recency'] < 30).astype(int)
            df['is_dormant'] = (df['recency'] > 180).astype(int)

        # Frequency features
        if 'frequency' in df.columns:
            df['is_frequent_buyer'] = (df['frequency'] > 5).astype(int)
            df['log_frequency'] = np.log1p(df['frequency'])

        # Monetary features
        if 'monetary' in df.columns:
            df['log_monetary'] = np.log1p(df['monetary'])

        # Churn risk features
        if 'churn_score' in df.columns:
            df['high_churn_risk'] = (df['churn_score'] > 0.7).astype(int)

        return df

    def _get_feature_columns(self, data: pd.DataFrame) -> List[str]:
        """Get list of feature columns for model."""
        # Core user features
        user_feats = ['recency', 'frequency', 'monetary', 'arpu', 'usage_7d_data_mb', 'churn_score']

        # Core product features
        product_feats = ['price', 'quota_data_mb', 'quota_voice_min', 'validity_days']

        # Engineered features
        engineered_feats = [
            'price_to_arpu_ratio', 'can_afford',
            'quota_to_usage_ratio', 'quota_sufficient',
            'is_recent_customer', 'is_dormant',
            'is_frequent_buyer', 'log_frequency',
            'log_monetary', 'high_churn_risk'
        ]

        # CF score
        cf_feats = ['cf_score']

        # Categorical features (one-hot encoded)
        cat_feats = []
        if 'segment_id' in data.columns:
            cat_feats.extend([f'segment_{i}' for i in range(5)])
        if 'product_family' in data.columns:
            for family in data['product_family'].unique():
                if pd.notna(family):
                    cat_feats.append(f'family_{family}')

        all_feats = user_feats + product_feats + engineered_feats + cf_feats + cat_feats

        # Filter to only available columns
        available_feats = [col for col in all_feats if col in data.columns]

        return available_feats

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        groups: np.ndarray,
        eval_set: Optional[List[Tuple]] = None,
        verbose: bool = True
    ) -> Dict:
        """
        Train XGBoost ranker with group-based evaluation.

        Args:
            X: Feature matrix
            y: Target labels (relevance scores)
            groups: Group sizes (one per query/user)
            eval_set: Optional validation set [(X_val, y_val)]
            verbose: Print training progress

        Returns:
            Training metrics dictionary
        """
        logger.info("Training XGBoost ranker...")

        # Prepare evaluation set
        eval_group = None
        if eval_set is not None:
            X_val, y_val, eval_group = eval_set[0]
            eval_set_prepared = [(X_val, y_val)]
        else:
            eval_set_prepared = None

        # Train model
        self.model.fit(
            X, y,
            group=groups,
            eval_set=eval_set_prepared,
            eval_group=[eval_group] if eval_group is not None else None,
            verbose=verbose
        )

        self.is_trained = True

        # Calculate training metrics
        train_preds = self.model.predict(X)
        train_metrics = self._calculate_metrics(y, train_preds, groups)

        # Calculate validation metrics
        val_metrics = {}
        if eval_set is not None:
            val_preds = self.model.predict(X_val)
            val_metrics = self._calculate_metrics(y_val, val_preds, eval_group)
            val_metrics = {f'val_{k}': v for k, v in val_metrics.items()}

        # Combine metrics
        metrics = {
            **train_metrics,
            **val_metrics,
            'n_features': len(self.feature_names),
            'n_groups': len(groups)
        }

        logger.info(f"Training completed: NDCG@5={train_metrics.get('ndcg@5', 0):.4f}")

        return metrics

    def cross_validate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        groups: np.ndarray,
        user_ids: np.ndarray,
        n_splits: int = 5
    ) -> Dict:
        """
        Perform cross-validation with group-aware splitting.

        Args:
            X: Feature matrix
            y: Target labels
            groups: Group sizes
            user_ids: User IDs for group splitting
            n_splits: Number of CV folds

        Returns:
            Cross-validation metrics
        """
        logger.info(f"Performing {n_splits}-fold cross-validation...")

        group_kfold = GroupKFold(n_splits=n_splits)
        cv_metrics = []

        for fold, (train_idx, val_idx) in enumerate(group_kfold.split(X, y, user_ids)):
            logger.info(f"Training fold {fold + 1}/{n_splits}...")

            # Split data
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            # Recalculate groups for train/val
            train_users = user_ids[train_idx]
            val_users = user_ids[val_idx]
            train_groups = pd.Series(train_users).value_counts().sort_index().values
            val_groups = pd.Series(val_users).value_counts().sort_index().values

            # Train fold model
            fold_model = xgb.XGBRanker(**self.model.get_params())
            fold_model.fit(X_train, y_train, group=train_groups, verbose=False)

            # Evaluate
            val_preds = fold_model.predict(X_val)
            fold_metrics = self._calculate_metrics(y_val, val_preds, val_groups)
            cv_metrics.append(fold_metrics)

        # Aggregate metrics
        agg_metrics = {}
        for metric_name in cv_metrics[0].keys():
            values = [m[metric_name] for m in cv_metrics]
            agg_metrics[f'{metric_name}_mean'] = float(np.mean(values))
            agg_metrics[f'{metric_name}_std'] = float(np.std(values))

        logger.info(f"CV completed: NDCG@5={agg_metrics['ndcg@5_mean']:.4f} ± {agg_metrics['ndcg@5_std']:.4f}")

        return agg_metrics

    def _calculate_metrics(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
        groups: np.ndarray
    ) -> Dict:
        """Calculate ranking metrics."""
        # Split by groups
        metrics = {'ndcg@5': 0, 'ndcg@10': 0, 'precision@5': 0, 'mrr': 0}

        start_idx = 0
        valid_groups = 0

        for group_size in groups:
            end_idx = start_idx + group_size

            if group_size < 2:
                start_idx = end_idx
                continue

            group_true = y_true.iloc[start_idx:end_idx].values
            group_pred = y_pred[start_idx:end_idx]

            # NDCG@5
            k = min(5, group_size)
            try:
                ndcg_5 = ndcg_score([group_true], [group_pred], k=k)
                metrics['ndcg@5'] += ndcg_5
            except:
                pass

            # NDCG@10
            k = min(10, group_size)
            try:
                ndcg_10 = ndcg_score([group_true], [group_pred], k=k)
                metrics['ndcg@10'] += ndcg_10
            except:
                pass

            # Precision@5
            top_k_idx = np.argsort(-group_pred)[:min(5, group_size)]
            precision_5 = group_true[top_k_idx].sum() / min(5, group_size)
            metrics['precision@5'] += precision_5

            # MRR (Mean Reciprocal Rank)
            sorted_idx = np.argsort(-group_pred)
            for rank, idx in enumerate(sorted_idx, 1):
                if group_true[idx] == 1:
                    metrics['mrr'] += 1.0 / rank
                    break

            valid_groups += 1
            start_idx = end_idx

        # Average metrics
        if valid_groups > 0:
            for key in metrics:
                metrics[key] /= valid_groups

        return metrics

    def rank(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict ranking scores for candidates.

        Args:
            X: Feature matrix

        Returns:
            Array of ranking scores
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        return self.model.predict(X)

    def explain(self, X: pd.DataFrame, top_n: int = 5) -> List[Dict]:
        """
        Generate SHAP explanations for top-N predictions.

        Args:
            X: Feature matrix
            top_n: Number of samples to explain

        Returns:
            List of explanation dictionaries
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        # Create SHAP explainer
        if self.explainer is None:
            self.explainer = shap.TreeExplainer(self.model)

        # Get SHAP values
        X_sample = X.head(top_n)
        shap_values = self.explainer.shap_values(X_sample)

        # Format explanations
        explanations = []
        for i in range(len(X_sample)):
            # Get top 3 contributing features
            feature_contributions = [
                (self.feature_names[j], float(shap_values[i][j]))
                for j in range(len(self.feature_names))
            ]
            feature_contributions.sort(key=lambda x: abs(x[1]), reverse=True)

            explanations.append({
                'top_features': feature_contributions[:3],
                'base_value': float(self.explainer.expected_value),
                'prediction': float(self.model.predict(X_sample.iloc[[i]])[0])
            })

        return explanations

    def get_feature_importance(self) -> pd.DataFrame:
        """
        Get feature importance scores.

        Returns:
            DataFrame with feature importance
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_,
            'gain': self.model.get_booster().get_score(importance_type='gain').values()
            if hasattr(self.model, 'get_booster') else [0] * len(self.feature_names)
        }).sort_values('importance', ascending=False)

        return importance

    def save_model(self, path: str) -> None:
        """Save trained model to disk."""
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        model_data = {
            'model': self.model,
            'feature_names': self.feature_names,
            'params': self.model.get_params()
        }

        joblib.dump(model_data, path)
        logger.info(f"XGBoost ranker saved to {path}")

    def load_model(self, path: str) -> None:
        """Load trained model from disk."""
        model_data = joblib.load(path)

        self.model = model_data['model']
        self.feature_names = model_data['feature_names']
        self.is_trained = True

        logger.info(f"XGBoost ranker loaded from {path}")

    def log_to_mlflow(
        self,
        metrics: Dict,
        experiment_name: str = "xgboost_ranking",
        run_name: Optional[str] = None
    ) -> str:
        """
        Log model and metrics to MLflow.

        Args:
            metrics: Training metrics
            experiment_name: Experiment name
            run_name: Optional run name

        Returns:
            MLflow run ID
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        mlflow.set_experiment(experiment_name)

        with mlflow.start_run(run_name=run_name) as run:
            # Log parameters
            mlflow.log_params({
                "objective": self.objective,
                "learning_rate": self.learning_rate,
                "max_depth": self.max_depth,
                "n_estimators": self.n_estimators,
                "subsample": self.subsample,
                "colsample_bytree": self.colsample_bytree
            })

            # Log metrics
            for metric_name, metric_value in metrics.items():
                if isinstance(metric_value, (int, float)):
                    mlflow.log_metric(metric_name, metric_value)

            # Log model
            mlflow.xgboost.log_model(
                self.model,
                "xgboost_ranker",
                registered_model_name="xgboost_ranker"
            )

            # Log feature importance
            importance = self.get_feature_importance()
            mlflow.log_dict(importance.to_dict('records'), "feature_importance.json")

            logger.info(f"Model logged to MLflow. Run ID: {run.info.run_id}")

            return run.info.run_id
