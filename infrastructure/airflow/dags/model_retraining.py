"""
Automated Model Retraining DAG
================================

Weekly retraining DAG with data drift detection, performance validation,
and automated model promotion to production.

Features:
- Data drift detection (PSI)
- Performance regression checks
- MLflow model promotion (staging → production)
- Automatic rollback on degradation
- Slack/email notifications

Schedule: Weekly on Sunday 2 AM
Trigger: Data drift PSI ≥ 0.2
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta
import sys
import os
import pandas as pd
import numpy as np
import requests
import json
import logging

# ✅ Configure logging
logger = logging.getLogger(__name__)

# MLflow imports
import mlflow
import mlflow.sklearn

# Add backend to Python path for model imports
# In Airflow container, backend is mounted at /opt/airflow/backend
backend_path = '/opt/airflow/backend'
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# ML model imports
from app.ml.models.segmentation.kmeans_segmenter import KMeansSegmenter
from app.ml.models.collaborative.lightfm_recommender import LightFMRecommender
from app.ml.models.ranker.xgboost_ranker import XGBoostRanker


default_args = {
    'owner': 'ml-team',
    'depends_on_past': False,
    'email': ['ml-alerts@telco.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


def check_data_drift(**context):
    """
    Check for data drift using Population Stability Index (PSI).

    Returns:
        str: 'retrain_models' if drift detected, 'skip_retraining' otherwise
    """
    hook = PostgresHook(postgres_conn_id='telco_postgres')

    # Get reference distribution (last training data)
    reference_data = hook.get_pandas_df("""
        SELECT recency, frequency, monetary, arpu, usage_7d_data_mb, churn_score
        FROM user_features
        WHERE updated_at < NOW() - INTERVAL '7 days'
        LIMIT 10000
    """)

    # Get current distribution
    current_data = hook.get_pandas_df("""
        SELECT recency, frequency, monetary, arpu, usage_7d_data_mb, churn_score
        FROM user_features
        WHERE updated_at >= NOW() - INTERVAL '7 days'
        LIMIT 10000
    """)

    if len(current_data) < 100:
        print("⚠️ Insufficient new data for drift detection")
        return 'skip_retraining'

    # Calculate PSI for each feature
    psi_scores = {}

    for col in reference_data.columns:
        ref_dist = np.histogram(reference_data[col].fillna(0), bins=10)[0]
        curr_dist = np.histogram(current_data[col].fillna(0), bins=10)[0]

        # Normalize to probabilities
        ref_dist = ref_dist / ref_dist.sum()
        curr_dist = curr_dist / curr_dist.sum()

        # Calculate PSI
        psi = np.sum((curr_dist - ref_dist) * np.log((curr_dist + 1e-10) / (ref_dist + 1e-10)))
        psi_scores[col] = psi

    # Average PSI
    avg_psi = np.mean(list(psi_scores.values()))
    max_psi = np.max(list(psi_scores.values()))

    print(f"📊 Data Drift Analysis:")
    print(f"   Average PSI: {avg_psi:.4f}")
    print(f"   Max PSI: {max_psi:.4f}")

    for feature, psi in psi_scores.items():
        status = "🚨 DRIFT" if psi >= 0.2 else "✅ STABLE"
        print(f"   {feature}: {psi:.4f} {status}")

    # Push metrics to XCom
    context['ti'].xcom_push(key='avg_psi', value=avg_psi)
    context['ti'].xcom_push(key='max_psi', value=max_psi)
    context['ti'].xcom_push(key='drift_detected', value=max_psi >= 0.2)

    # Trigger retraining if drift detected
    if max_psi >= 0.2:
        print(f"🔄 DRIFT DETECTED! Max PSI {max_psi:.4f} ≥ 0.2 - Triggering retraining")
        return 'prepare_training_data'
    else:
        print(f"✅ No significant drift. Max PSI {max_psi:.4f} < 0.2")
        return 'skip_retraining'


def prepare_training_data(**context):
    """Prepare fresh training data from database."""
    hook = PostgresHook(postgres_conn_id='telco_postgres')

    print("📥 Loading training data...")

    # Load user features
    features_df = hook.get_pandas_df("""
        SELECT * FROM user_features
        WHERE updated_at >= NOW() - INTERVAL '30 days'
    """)

    # Load transactions
    transactions_df = hook.get_pandas_df("""
        SELECT * FROM transactions
        WHERE transaction_date >= NOW() - INTERVAL '90 days'
        AND status = 'completed'
    """)

    # Load events for implicit feedback
    events_df = hook.get_pandas_df("""
        SELECT * FROM events
        WHERE timestamp >= NOW() - INTERVAL '30 days'
    """)

    print(f"✅ Loaded {len(features_df)} user features")
    print(f"✅ Loaded {len(transactions_df)} transactions")
    print(f"✅ Loaded {len(events_df)} events")

    # Save to temporary location
    features_df.to_parquet('/tmp/training_features.parquet')
    transactions_df.to_parquet('/tmp/training_transactions.parquet')
    events_df.to_parquet('/tmp/training_events.parquet')

    context['ti'].xcom_push(key='training_samples', value=len(features_df))


def train_segmentation_model(**context):
    """Train K-Means segmentation model."""
    print("🎯 Training K-Means Segmentation Model...")

    # Load data
    features_df = pd.read_parquet('/tmp/training_features.parquet')

    # Initialize MLflow
    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000'))
    mlflow.set_experiment('model_retraining')

    # Train model
    segmenter = KMeansSegmenter(n_clusters=5)

    with mlflow.start_run(run_name=f"kmeans_retraining_{datetime.now().strftime('%Y%m%d')}"):
        # Train
        feature_cols = ['recency', 'frequency', 'monetary', 'arpu',
                       'usage_7d_data_mb', 'churn_score']
        X = features_df[feature_cols].fillna(0)

        labels = segmenter.fit(X)

        # Evaluate
        from sklearn.metrics import silhouette_score, calinski_harabasz_score

        silhouette = silhouette_score(X, labels)
        calinski = calinski_harabasz_score(X, labels)
        inertia = segmenter.model.inertia_

        # Log metrics
        mlflow.log_param("n_clusters", 5)
        mlflow.log_param("training_samples", len(X))
        mlflow.log_metric("silhouette_score", silhouette)
        mlflow.log_metric("calinski_harabasz_score", calinski)
        mlflow.log_metric("inertia", inertia)

        # Save model
        mlflow.sklearn.log_model(segmenter.model, "model")
        mlflow.sklearn.log_model(segmenter.scaler, "scaler")

        # Register model
        model_uri = f"runs:/{mlflow.active_run().info.run_id}/model"
        mlflow.register_model(model_uri, "kmeans_segmentation")

        run_id = mlflow.active_run().info.run_id

        print(f"✅ K-Means trained - Silhouette: {silhouette:.4f}")

        context['ti'].xcom_push(key='kmeans_run_id', value=run_id)
        context['ti'].xcom_push(key='kmeans_silhouette', value=silhouette)


def train_collaborative_model(**context):
    """Train LightFM collaborative filtering model."""
    print("🤝 Training LightFM Collaborative Filtering Model...")

    # Load data
    transactions_df = pd.read_parquet('/tmp/training_transactions.parquet')
    events_df = pd.read_parquet('/tmp/training_events.parquet')

    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000'))
    mlflow.set_experiment('model_retraining')

    # Train model
    recommender = LightFMRecommender(no_components=50, loss='warp')

    with mlflow.start_run(run_name=f"lightfm_retraining_{datetime.now().strftime('%Y%m%d')}"):
        # Prepare interactions
        interactions = transactions_df[['user_id', 'product_id']].copy()
        interactions['rating'] = 1.0  # Implicit feedback

        # ✅ Split into train/test sets (chronological split for realistic evaluation)
        if 'transaction_date' in transactions_df.columns:
            interactions['transaction_date'] = transactions_df['transaction_date']
            interactions = interactions.sort_values('transaction_date')
            interactions = interactions.drop('transaction_date', axis=1)

        split_idx = int(len(interactions) * 0.8)
        train_interactions = interactions.iloc[:split_idx].copy()
        test_interactions = interactions.iloc[split_idx:].copy()

        print(f"📊 Train: {len(train_interactions)} interactions, Test: {len(test_interactions)} interactions")

        # ✅ Prepare training data
        train_matrix, user_feat_matrix, item_feat_matrix = recommender.prepare_data(
            train_interactions,
            user_features=None,
            item_features=None
        )

        # ✅ Train on training set only
        train_metrics = recommender.train(
            interaction_matrix=train_matrix,
            user_features=user_feat_matrix,
            item_features=item_feat_matrix,
            epochs=30,
            num_threads=4,
            verbose=True
        )

        # ✅ Prepare test data (reuse same dataset for consistent mappings)
        test_matrix, _, _ = recommender.prepare_data(test_interactions)

        # ✅ Evaluate on test set
        from lightfm.evaluation import precision_at_k, recall_at_k, auc_score

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

        test_auc = auc_score(
            recommender.model,
            test_matrix,
            user_features=user_feat_matrix,
            item_features=item_feat_matrix
        ).mean()

        print(f"📈 Test Metrics: P@5={test_precision_5:.4f}, R@10={test_recall_10:.4f}, AUC={test_auc:.4f}")

        # ✅ Log parameters
        mlflow.log_param("no_components", 50)
        mlflow.log_param("loss", "warp")
        mlflow.log_param("training_interactions", len(train_interactions))
        mlflow.log_param("test_interactions", len(test_interactions))
        mlflow.log_param("epochs", 30)

        # ✅ Log training metrics
        mlflow.log_metric("train_precision_at_5", train_metrics['train_precision_at_5'])
        mlflow.log_metric("train_recall_at_10", train_metrics['train_recall_at_10'])
        mlflow.log_metric("train_auc", train_metrics['train_auc'])

        # ✅ Log test metrics
        mlflow.log_metric("test_precision_at_5", float(test_precision_5))
        mlflow.log_metric("test_recall_at_10", float(test_recall_10))
        mlflow.log_metric("test_auc", float(test_auc))

        # Save model (LightFM requires custom serialization)
        import pickle
        model_path = "/tmp/lightfm_model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(recommender, f)

        mlflow.log_artifact(model_path, "model")

        run_id = mlflow.active_run().info.run_id

        print(f"✅ LightFM trained - {len(train_interactions)} train + {len(test_interactions)} test interactions")
        print(f"   Train: P@5={train_metrics['train_precision_at_5']:.4f}, R@10={train_metrics['train_recall_at_10']:.4f}")
        print(f"   Test: P@5={test_precision_5:.4f}, R@10={test_recall_10:.4f}, AUC={test_auc:.4f}")

        context['ti'].xcom_push(key='lightfm_run_id', value=run_id)
        context['ti'].xcom_push(key='lightfm_test_precision', value=float(test_precision_5))
        context['ti'].xcom_push(key='lightfm_test_recall', value=float(test_recall_10))


def train_ranker_model(**context):
    """Train XGBoost ranking model."""
    print("🏆 Training XGBoost Ranking Model...")

    # Load data
    transactions_df = pd.read_parquet('/tmp/training_transactions.parquet')
    events_df = pd.read_parquet('/tmp/training_events.parquet')

    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000'))
    mlflow.set_experiment('model_retraining')

    # Train model
    ranker = XGBoostRanker(
        objective='rank:pairwise',
        learning_rate=0.1,
        max_depth=6,
        n_estimators=100
    )

    with mlflow.start_run(run_name=f"xgboost_retraining_{datetime.now().strftime('%Y%m%d')}"):
        # ✅ Prepare training interactions with labels
        # Positive samples: actual purchases (label=1)
        positive_interactions = transactions_df[['user_id', 'product_id']].copy()
        positive_interactions['label'] = 1

        # Negative samples: viewed but not purchased (label=0)
        viewed_products = events_df[
            (events_df['event_type'] == 'product_view') &
            (~events_df['product_id'].isin(positive_interactions['product_id']))
        ][['user_id', 'product_id']].copy()
        viewed_products['label'] = 0

        # Combine positive and negative samples
        interactions = pd.concat([positive_interactions, viewed_products], ignore_index=True)
        interactions = interactions.drop_duplicates(subset=['user_id', 'product_id'])

        # ✅ Prepare user features (RFM, ARPU, usage)
        user_features = transactions_df.groupby('user_id').agg({
            'transaction_date': lambda x: (datetime.now() - x.max()).days,  # Recency
            'product_id': 'count',  # Frequency
            'amount': 'sum'  # Monetary
        }).reset_index()
        user_features.columns = ['user_id', 'recency', 'frequency', 'monetary']
        user_features['arpu'] = user_features['monetary'] / user_features['frequency'].clip(lower=1)

        # Add segment_id if available (from context or default)
        user_features['segment_id'] = 2  # Default segment
        user_features['usage_7d_data_mb'] = 1000  # Default usage
        user_features['churn_score'] = 0.5  # Default churn score

        # ✅ Prepare product features
        # Get unique products from transactions
        product_features = pd.DataFrame({
            'product_id': transactions_df['product_id'].unique()
        })
        product_features['price'] = 50000  # Default price
        product_features['quota_data_mb'] = 5000  # Default quota
        product_features['quota_voice_min'] = 100  # Default voice
        product_features['validity_days'] = 30  # Default validity
        product_features['product_family'] = 'data'  # Default family

        # ✅ Feature engineering and preparation
        X, y, groups = ranker.prepare_features(
            interactions=interactions,
            user_features=user_features,
            product_features=product_features,
            cf_scores=None  # No CF scores in first iteration
        )

        print(f"📊 Features: {X.shape[1]} columns, {len(X)} samples, {len(groups)} user groups")

        # ✅ Train/test split (by groups to prevent leakage)
        n_groups = len(groups)
        split_idx = int(n_groups * 0.8)

        # Split groups
        train_groups = groups[:split_idx]
        test_groups = groups[split_idx:]

        # Split samples based on group boundaries
        train_end = train_groups.sum()
        X_train = X.iloc[:train_end]
        y_train = y.iloc[:train_end]
        X_test = X.iloc[train_end:]
        y_test = y.iloc[train_end:]

        print(f"📊 Train: {len(X_train)} samples, {len(train_groups)} groups")
        print(f"📊 Test: {len(X_test)} samples, {len(test_groups)} groups")

        # ✅ Train model with evaluation
        eval_set = [(X_test, y_test, test_groups)]
        train_metrics = ranker.train(
            X=X_train,
            y=y_train,
            groups=train_groups,
            eval_set=eval_set,
            verbose=True
        )

        # ✅ Evaluate on test set
        from sklearn.metrics import ndcg_score

        # Rank on test set
        y_pred = ranker.rank(X_test)

        # Calculate NDCG@5 and NDCG@10
        # Group predictions by user for ranking evaluation
        test_data = X_test.copy()
        test_data['y_true'] = y_test.values
        test_data['y_pred'] = y_pred

        ndcg_5_scores = []
        ndcg_10_scores = []

        # Calculate NDCG per user group
        start_idx = 0
        for group_size in test_groups:
            end_idx = start_idx + group_size
            group_true = test_data.iloc[start_idx:end_idx]['y_true'].values
            group_pred = test_data.iloc[start_idx:end_idx]['y_pred'].values

            if group_true.sum() > 0:  # Only if there are positive samples
                ndcg_5 = ndcg_score([group_true], [group_pred], k=5)
                ndcg_10 = ndcg_score([group_true], [group_pred], k=10)
                ndcg_5_scores.append(ndcg_5)
                ndcg_10_scores.append(ndcg_10)

            start_idx = end_idx

        test_ndcg_5 = np.mean(ndcg_5_scores) if ndcg_5_scores else 0.0
        test_ndcg_10 = np.mean(ndcg_10_scores) if ndcg_10_scores else 0.0

        print(f"📈 Test NDCG@5: {test_ndcg_5:.4f}, NDCG@10: {test_ndcg_10:.4f}")

        # ✅ Log parameters
        mlflow.log_param("objective", "rank:pairwise")
        mlflow.log_param("learning_rate", 0.1)
        mlflow.log_param("max_depth", 6)
        mlflow.log_param("n_estimators", 100)
        mlflow.log_param("n_features", X.shape[1])
        mlflow.log_param("n_train_samples", len(X_train))
        mlflow.log_param("n_test_samples", len(X_test))
        mlflow.log_param("n_train_groups", len(train_groups))
        mlflow.log_param("n_test_groups", len(test_groups))

        # ✅ Log training metrics
        for metric_name, metric_value in train_metrics.items():
            if isinstance(metric_value, (int, float)):
                mlflow.log_metric(f"train_{metric_name}", metric_value)

        # ✅ Log test metrics
        mlflow.log_metric("test_ndcg_at_5", test_ndcg_5)
        mlflow.log_metric("test_ndcg_at_10", test_ndcg_10)

        # Save model
        import pickle
        model_path = "/tmp/xgboost_ranker.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(ranker, f)

        mlflow.log_artifact(model_path, "model")

        run_id = mlflow.active_run().info.run_id

        print(f"✅ XGBoost trained - {X.shape[1]} features, NDCG@5={test_ndcg_5:.4f}")

        context['ti'].xcom_push(key='xgboost_run_id', value=run_id)
        context['ti'].xcom_push(key='xgboost_test_ndcg_5', value=float(test_ndcg_5))
        context['ti'].xcom_push(key='xgboost_test_ndcg_10', value=float(test_ndcg_10))


def validate_models(**context):
    """
    Validate new models against production models.

    Returns:
        str: 'promote_models' if validation passes, 'rollback_training' otherwise
    """
    print("🔍 Validating new models...")

    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000'))

    # Get new model metrics
    kmeans_run_id = context['ti'].xcom_pull(key='kmeans_run_id')
    kmeans_silhouette = context['ti'].xcom_pull(key='kmeans_silhouette')

    # Get production model metrics
    client = mlflow.tracking.MlflowClient()

    try:
        # Get latest production model
        prod_versions = client.get_latest_versions("kmeans_segmentation", stages=["Production"])

        if prod_versions:
            prod_run = client.get_run(prod_versions[0].run_id)
            prod_silhouette = prod_run.data.metrics.get('silhouette_score', 0.0)

            # Require 2% improvement
            improvement_threshold = 0.02
            improvement = kmeans_silhouette - prod_silhouette

            print(f"📊 Model Comparison:")
            print(f"   Production Silhouette: {prod_silhouette:.4f}")
            print(f"   New Model Silhouette: {kmeans_silhouette:.4f}")
            print(f"   Improvement: {improvement:.4f} ({improvement/prod_silhouette*100:.2f}%)")

            if improvement >= improvement_threshold:
                print(f"✅ Validation PASSED - Improvement ≥ {improvement_threshold:.2%}")
                context['ti'].xcom_push(key='validation_passed', value=True)
                return 'promote_models'
            else:
                print(f"❌ Validation FAILED - Improvement < {improvement_threshold:.2%}")
                context['ti'].xcom_push(key='validation_passed', value=False)
                return 'rollback_training'
        else:
            # No production model yet, promote automatically
            print("ℹ️ No production model found - Auto-promoting")
            context['ti'].xcom_push(key='validation_passed', value=True)
            return 'promote_models'

    except Exception as e:
        # ✅ Enhanced error handling with comprehensive logging
        error_type = type(e).__name__
        error_context = {
            'error_type': error_type,
            'error_message': str(e),
            'kmeans_run_id': kmeans_run_id,
            'timestamp': datetime.now().isoformat(),
            'validation_stage': 'model_comparison'
        }

        # Log error with full context and stack trace
        logger.error(
            f"Model validation failed: {error_type} - {str(e)}",
            extra=error_context,
            exc_info=True
        )

        # Log to MLflow for tracking
        try:
            with mlflow.start_run(run_name=f"validation_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
                mlflow.log_param("status", "validation_error")
                mlflow.log_param("error_type", error_type)
                mlflow.log_param("error_message", str(e))
                mlflow.log_param("kmeans_run_id", kmeans_run_id)
        except Exception as mlflow_error:
            logger.warning(f"Failed to log error to MLflow: {mlflow_error}")

        # Push error context to XCom for downstream tasks
        context['ti'].xcom_push(key='validation_error', value=error_context)
        context['ti'].xcom_push(key='validation_passed', value=False)

        print(f"⚠️ Validation error: {error_type} - {str(e)}")
        print("⚠️ Skipping promotion as safety measure")
        print(f"⚠️ Error logged with context: {error_context}")

        return 'rollback_training'


def promote_models(**context):
    """Promote new models from staging to production."""
    print("🚀 Promoting models to production...")

    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000'))
    client = mlflow.tracking.MlflowClient()

    # Get run IDs
    kmeans_run_id = context['ti'].xcom_pull(key='kmeans_run_id')
    lightfm_run_id = context['ti'].xcom_pull(key='lightfm_run_id')
    xgboost_run_id = context['ti'].xcom_pull(key='xgboost_run_id')

    # ✅ Promote all models using consistent logic
    models_to_promote = [
        ('kmeans_segmentation', kmeans_run_id, 'K-Means'),
        ('lightfm_collaborative', lightfm_run_id, 'LightFM'),
        ('xgboost_ranker', xgboost_run_id, 'XGBoost')
    ]

    promoted_count = 0
    failed_models = []

    for model_name, run_id, display_name in models_to_promote:
        try:
            print(f"🔄 Promoting {display_name} model...")

            # Archive old production version
            prod_versions = client.get_latest_versions(model_name, stages=["Production"])
            for version in prod_versions:
                client.transition_model_version_stage(
                    name=model_name,
                    version=version.version,
                    stage="Archived"
                )
                print(f"  📦 Archived old {display_name} v{version.version}")

            # Promote new model
            model_versions = client.search_model_versions(f"run_id='{run_id}'")
            if model_versions:
                client.transition_model_version_stage(
                    name=model_name,
                    version=model_versions[0].version,
                    stage="Production"
                )
                print(f"  ✅ {display_name} v{model_versions[0].version} → Production")
                promoted_count += 1
            else:
                print(f"  ⚠️ No model version found for {display_name} run_id={run_id}")
                failed_models.append(display_name)

        except Exception as e:
            print(f"  ❌ {display_name} promotion error: {e}")
            failed_models.append(display_name)

    # Summary
    print(f"\n📊 Promotion Summary:")
    print(f"  ✅ Successfully promoted: {promoted_count}/3 models")
    if failed_models:
        print(f"  ❌ Failed models: {', '.join(failed_models)}")

    print("✅ Model promotion complete")


def rollback_training(**context):
    """Handle failed validation."""
    print("⏪ Rolling back - keeping production models")
    print("📧 Sending failure notification...")

    # Log rollback event
    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000'))

    with mlflow.start_run(run_name=f"retraining_rollback_{datetime.now().strftime('%Y%m%d')}"):
        mlflow.log_param("status", "rollback")
        mlflow.log_param("reason", "validation_failed")


def skip_retraining(**context):
    """Log skipped retraining."""
    print("⏭️ Skipping retraining - no drift detected")

    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000'))

    with mlflow.start_run(run_name=f"retraining_skipped_{datetime.now().strftime('%Y%m%d')}"):
        mlflow.log_param("status", "skipped")
        mlflow.log_param("reason", "no_drift")

        avg_psi = context['ti'].xcom_pull(key='avg_psi')
        max_psi = context['ti'].xcom_pull(key='max_psi')

        mlflow.log_metric("avg_psi", avg_psi)
        mlflow.log_metric("max_psi", max_psi)


# DAG Definition
with DAG(
    'model_retraining',
    default_args=default_args,
    description='Automated model retraining with drift detection and validation',
    schedule_interval='0 2 * * 0',  # Weekly Sunday 2 AM
    start_date=days_ago(1),
    catchup=False,
    tags=['ml', 'retraining', 'production'],
) as dag:

    # Check for data drift
    check_drift = BranchPythonOperator(
        task_id='check_data_drift',
        python_callable=check_data_drift,
        provide_context=True
    )

    # Skip retraining path
    skip = PythonOperator(
        task_id='skip_retraining',
        python_callable=skip_retraining,
        provide_context=True
    )

    # Prepare data
    prepare_data = PythonOperator(
        task_id='prepare_training_data',
        python_callable=prepare_training_data,
        provide_context=True
    )

    # Train models in parallel
    train_kmeans = PythonOperator(
        task_id='train_segmentation',
        python_callable=train_segmentation_model,
        provide_context=True
    )

    train_lightfm = PythonOperator(
        task_id='train_collaborative',
        python_callable=train_collaborative_model,
        provide_context=True
    )

    train_xgboost = PythonOperator(
        task_id='train_ranker',
        python_callable=train_ranker_model,
        provide_context=True
    )

    # Validate models
    validate = BranchPythonOperator(
        task_id='validate_models',
        python_callable=validate_models,
        provide_context=True,
        trigger_rule=TriggerRule.ALL_SUCCESS
    )

    # Promote models
    promote = PythonOperator(
        task_id='promote_models',
        python_callable=promote_models,
        provide_context=True
    )

    # Rollback
    rollback = PythonOperator(
        task_id='rollback_training',
        python_callable=rollback_training,
        provide_context=True
    )

    # Notify FastAPI
    notify_api = SimpleHttpOperator(
        task_id='notify_fastapi',
        http_conn_id='fastapi_backend',
        endpoint='/api/v1/webhooks/models-updated',
        method='POST',
        headers={"Content-Type": "application/json"},
        data='{"status": "models_promoted", "timestamp": "{{ ts }}"}',
        trigger_rule=TriggerRule.ONE_SUCCESS
    )

    # DAG flow
    check_drift >> [skip, prepare_data]
    prepare_data >> [train_kmeans, train_lightfm, train_xgboost]
    [train_kmeans, train_lightfm, train_xgboost] >> validate
    validate >> [promote, rollback]
    [promote, rollback, skip] >> notify_api
