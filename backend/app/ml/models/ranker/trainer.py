"""
XGBoost Ranker Training Pipeline
==================================

Training script with cross-validation and hyperparameter tuning.

Features:
- Data preparation from interaction logs
- Cross-validation with group-aware splitting
- Hyperparameter tuning with Optuna
- Model evaluation and validation
- MLflow experiment tracking
"""

from typing import Optional, Dict, Tuple
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import optuna
import mlflow
import logging

from .xgboost_ranker import XGBoostRanker

logger = logging.getLogger(__name__)


class RankerTrainer:
    """
    Training pipeline for XGBoost ranker.

    Handles data preparation, training, validation, and hyperparameter tuning.
    """

    def __init__(
        self,
        mlflow_tracking_uri: Optional[str] = None,
        experiment_name: str = "xgboost_ranking"
    ):
        """
        Initialize ranker trainer.

        Args:
            mlflow_tracking_uri: MLflow tracking server URI
            experiment_name: MLflow experiment name
        """
        self.experiment_name = experiment_name

        if mlflow_tracking_uri:
            mlflow.set_tracking_uri(mlflow_tracking_uri)

        mlflow.set_experiment(experiment_name)

    def prepare_training_data(
        self,
        interactions: pd.DataFrame,
        user_features: pd.DataFrame,
        product_features: pd.DataFrame,
        cf_scores: Optional[pd.DataFrame] = None,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Tuple:
        """
        Prepare and split training data.

        Args:
            interactions: User-product interactions with labels
            user_features: User feature DataFrame
            product_features: Product feature DataFrame
            cf_scores: Optional CF scores
            test_size: Test set proportion
            random_state: Random seed

        Returns:
            Tuple of (X_train, X_test, y_train, y_test, groups_train, groups_test, user_ids_train, user_ids_test)
        """
        logger.info("Preparing training data...")

        # Initialize ranker for feature engineering
        ranker = XGBoostRanker()
        X, y, groups = ranker.prepare_features(
            interactions, user_features, product_features, cf_scores
        )

        # Get user IDs for group splitting
        user_ids = interactions.groupby(interactions.index)['user_id'].first().values

        # Split data by users (not by samples)
        unique_users = np.unique(user_ids)
        train_users, test_users = train_test_split(
            unique_users,
            test_size=test_size,
            random_state=random_state
        )

        # Create train/test masks
        train_mask = np.isin(user_ids, train_users)
        test_mask = np.isin(user_ids, test_users)

        # Split data
        X_train, X_test = X[train_mask], X[test_mask]
        y_train, y_test = y[train_mask], y[test_mask]

        # Recalculate groups
        train_user_ids = user_ids[train_mask]
        test_user_ids = user_ids[test_mask]
        groups_train = pd.Series(train_user_ids).value_counts().sort_index().values
        groups_test = pd.Series(test_user_ids).value_counts().sort_index().values

        logger.info(f"Train: {len(X_train)} samples, {len(groups_train)} groups")
        logger.info(f"Test: {len(X_test)} samples, {len(groups_test)} groups")

        return (
            X_train, X_test,
            y_train, y_test,
            groups_train, groups_test,
            train_user_ids, test_user_ids
        )

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        groups_train: np.ndarray,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        groups_val: Optional[np.ndarray] = None,
        params: Optional[Dict] = None,
        run_name: Optional[str] = None
    ) -> Tuple[XGBoostRanker, Dict]:
        """
        Train XGBoost ranker.

        Args:
            X_train: Training features
            y_train: Training labels
            groups_train: Training group sizes
            X_val: Validation features
            y_val: Validation labels
            groups_val: Validation group sizes
            params: Optional model hyperparameters
            run_name: MLflow run name

        Returns:
            Tuple of (trained_model, metrics)
        """
        logger.info("Training XGBoost ranker...")

        # Initialize model
        if params is None:
            params = {
                'objective': 'rank:pairwise',
                'learning_rate': 0.1,
                'max_depth': 6,
                'n_estimators': 100,
                'subsample': 0.8,
                'colsample_bytree': 0.8
            }

        ranker = XGBoostRanker(**params)

        # Prepare eval set
        eval_set = None
        if X_val is not None and y_val is not None and groups_val is not None:
            eval_set = [(X_val, y_val, groups_val)]

        # Train model
        with mlflow.start_run(run_name=run_name) as run:
            metrics = ranker.train(
                X_train, y_train, groups_train,
                eval_set=eval_set,
                verbose=True
            )

            # Log to MLflow
            run_id = ranker.log_to_mlflow(metrics, self.experiment_name)

            logger.info(f"Training completed. MLflow run: {run_id}")

        return ranker, metrics

    def cross_validate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        groups: np.ndarray,
        user_ids: np.ndarray,
        params: Optional[Dict] = None,
        n_splits: int = 5
    ) -> Dict:
        """
        Perform cross-validation.

        Args:
            X: Feature matrix
            y: Labels
            groups: Group sizes
            user_ids: User IDs for splitting
            params: Model hyperparameters
            n_splits: Number of CV folds

        Returns:
            Cross-validation metrics
        """
        logger.info(f"Starting {n_splits}-fold cross-validation...")

        if params is None:
            params = {}

        ranker = XGBoostRanker(**params)
        cv_metrics = ranker.cross_validate(X, y, groups, user_ids, n_splits=n_splits)

        logger.info(f"CV NDCG@5: {cv_metrics['ndcg@5_mean']:.4f} ± {cv_metrics['ndcg@5_std']:.4f}")

        return cv_metrics

    def tune_hyperparameters(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        groups_train: np.ndarray,
        user_ids_train: np.ndarray,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        groups_val: np.ndarray,
        n_trials: int = 50,
        n_splits: int = 3
    ) -> Dict:
        """
        Tune hyperparameters using Optuna.

        Args:
            X_train: Training features
            y_train: Training labels
            groups_train: Training groups
            user_ids_train: Training user IDs
            X_val: Validation features
            y_val: Validation labels
            groups_val: Validation groups
            n_trials: Number of Optuna trials
            n_splits: Number of CV folds per trial

        Returns:
            Best hyperparameters
        """
        logger.info(f"Starting hyperparameter tuning with {n_trials} trials...")

        def objective(trial):
            """Optuna objective function."""
            params = {
                'objective': trial.suggest_categorical('objective', ['rank:pairwise', 'rank:ndcg']),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0)
            }

            # Cross-validation
            ranker = XGBoostRanker(**params)
            cv_metrics = ranker.cross_validate(
                X_train, y_train, groups_train, user_ids_train,
                n_splits=n_splits
            )

            # Optimize for NDCG@5
            return cv_metrics['ndcg@5_mean']

        # Run optimization
        study = optuna.create_study(
            direction='maximize',
            study_name='xgboost_ranker_tuning'
        )
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        best_params = study.best_params
        best_score = study.best_value

        logger.info(f"Best NDCG@5: {best_score:.4f}")
        logger.info(f"Best params: {best_params}")

        # Log to MLflow
        with mlflow.start_run(run_name="hyperparameter_tuning"):
            mlflow.log_params(best_params)
            mlflow.log_metric("best_ndcg@5", best_score)
            mlflow.log_metric("n_trials", n_trials)

        return best_params

    def evaluate(
        self,
        ranker: XGBoostRanker,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        groups_test: np.ndarray
    ) -> Dict:
        """
        Evaluate trained ranker on test set.

        Args:
            ranker: Trained XGBoost ranker
            X_test: Test features
            y_test: Test labels
            groups_test: Test groups

        Returns:
            Test metrics
        """
        logger.info("Evaluating ranker on test set...")

        # Predict
        y_pred = ranker.rank(X_test)

        # Calculate metrics
        test_metrics = ranker._calculate_metrics(y_test, y_pred, groups_test)

        logger.info(f"Test NDCG@5: {test_metrics['ndcg@5']:.4f}")
        logger.info(f"Test Precision@5: {test_metrics['precision@5']:.4f}")
        logger.info(f"Test MRR: {test_metrics['mrr']:.4f}")

        # Log to MLflow
        with mlflow.start_run(run_name="test_evaluation"):
            for metric_name, metric_value in test_metrics.items():
                mlflow.log_metric(f"test_{metric_name}", metric_value)

        return test_metrics

    def train_full_pipeline(
        self,
        interactions: pd.DataFrame,
        user_features: pd.DataFrame,
        product_features: pd.DataFrame,
        cf_scores: Optional[pd.DataFrame] = None,
        tune_hyperparams: bool = False,
        n_trials: int = 50,
        save_path: Optional[str] = None
    ) -> Tuple[XGBoostRanker, Dict]:
        """
        Full training pipeline with data prep, training, and evaluation.

        Args:
            interactions: User-product interactions
            user_features: User features
            product_features: Product features
            cf_scores: Optional CF scores
            tune_hyperparams: Whether to tune hyperparameters
            n_trials: Number of tuning trials
            save_path: Path to save trained model

        Returns:
            Tuple of (trained_model, metrics)
        """
        logger.info("=" * 60)
        logger.info("XGBoost Ranker Training Pipeline")
        logger.info("=" * 60)

        # Step 1: Prepare data
        (
            X_train, X_test,
            y_train, y_test,
            groups_train, groups_test,
            user_ids_train, user_ids_test
        ) = self.prepare_training_data(
            interactions, user_features, product_features, cf_scores
        )

        # Step 2: Hyperparameter tuning (optional)
        best_params = None
        if tune_hyperparams:
            # Split train into train/val for tuning
            train_users = np.unique(user_ids_train)
            train_users_split, val_users_split = train_test_split(
                train_users, test_size=0.2, random_state=42
            )

            train_mask = np.isin(user_ids_train, train_users_split)
            val_mask = np.isin(user_ids_train, val_users_split)

            X_train_split = X_train[train_mask]
            X_val_split = X_train[val_mask]
            y_train_split = y_train[train_mask]
            y_val_split = y_train[val_mask]

            train_user_ids_split = user_ids_train[train_mask]
            val_user_ids_split = user_ids_train[val_mask]
            groups_train_split = pd.Series(train_user_ids_split).value_counts().sort_index().values
            groups_val_split = pd.Series(val_user_ids_split).value_counts().sort_index().values

            best_params = self.tune_hyperparameters(
                X_train_split, y_train_split, groups_train_split, train_user_ids_split,
                X_val_split, y_val_split, groups_val_split,
                n_trials=n_trials
            )

        # Step 3: Train final model
        ranker, train_metrics = self.train(
            X_train, y_train, groups_train,
            X_test, y_test, groups_test,
            params=best_params,
            run_name="final_model"
        )

        # Step 4: Evaluate on test set
        test_metrics = self.evaluate(ranker, X_test, y_test, groups_test)

        # Step 5: Save model
        if save_path:
            ranker.save_model(save_path)

        # Combine metrics
        final_metrics = {
            **{f'train_{k}': v for k, v in train_metrics.items()},
            **{f'test_{k}': v for k, v in test_metrics.items()}
        }

        logger.info("=" * 60)
        logger.info("Training Pipeline Completed")
        logger.info(f"Test NDCG@5: {test_metrics['ndcg@5']:.4f}")
        logger.info(f"Test Precision@5: {test_metrics['precision@5']:.4f}")
        logger.info("=" * 60)

        return ranker, final_metrics


def train_ranker_from_db(
    db_connection_string: str,
    mlflow_tracking_uri: str,
    save_path: str,
    tune_hyperparams: bool = False
) -> Tuple[XGBoostRanker, Dict]:
    """
    Train ranker directly from database.

    Args:
        db_connection_string: Database connection string
        mlflow_tracking_uri: MLflow tracking URI
        save_path: Path to save model
        tune_hyperparams: Whether to tune hyperparameters

    Returns:
        Tuple of (trained_model, metrics)
    """
    import sqlalchemy as sa

    logger.info("Loading data from database...")

    # Create database engine
    engine = sa.create_engine(db_connection_string)

    # Load interactions
    interactions_query = """
    SELECT
        e.user_id,
        e.product_id,
        CASE WHEN e.event_type = 'subscribe' THEN 1 ELSE 0 END as label,
        e.timestamp
    FROM events e
    WHERE e.event_type IN ('view', 'click', 'subscribe')
    ORDER BY e.timestamp
    """
    interactions = pd.read_sql(interactions_query, engine)

    # Load user features
    user_features = pd.read_sql("SELECT * FROM user_features", engine)

    # Load product features
    product_features = pd.read_sql("SELECT * FROM products", engine)

    # Initialize trainer
    trainer = RankerTrainer(mlflow_tracking_uri=mlflow_tracking_uri)

    # Train full pipeline
    ranker, metrics = trainer.train_full_pipeline(
        interactions=interactions,
        user_features=user_features,
        product_features=product_features,
        tune_hyperparams=tune_hyperparams,
        save_path=save_path
    )

    return ranker, metrics
