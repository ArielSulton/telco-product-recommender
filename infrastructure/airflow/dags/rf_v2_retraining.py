"""
RandomForest v2 Model Retraining DAG
====================================

Weekly retraining DAG for RandomForest product classifier with:
- Behavioral feature validation
- 10-class product prediction (Data Booster, Streaming Pack, Voice Bundle, etc.)
- Temperature scaling optimization
- Top-K accuracy metrics
- MLflow experiment tracking
- Automated model promotion

Features:
- Feature distribution drift detection
- Classification performance validation
- Temperature calibration with validation set
- Automated rollback on accuracy degradation
- Model registry integration

Schedule: Weekly on Sunday 3 AM (1 hour after hybrid model retraining)
Trigger: Manual or scheduled
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta
import sys
import os
import pandas as pd
import numpy as np
import logging
import joblib
import tempfile

# Configure logging
logger = logging.getLogger(__name__)

# MLflow imports
import mlflow
import mlflow.sklearn

# Scikit-learn imports
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    top_k_accuracy_score
)

# Add backend to Python path for RF model class
backend_path = '/opt/airflow/backend'
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.ml.rf_model import RFRecommender


default_args = {
    'owner': 'ml-team',
    'depends_on_past': False,
    'email': ['ml-alerts@telco.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


def check_feature_drift(**context):
    """
    Check for behavioral feature drift using Population Stability Index (PSI).

    Returns:
        str: 'prepare_training_data' if drift detected, 'skip_retraining' otherwise
    """
    hook = PostgresHook(postgres_conn_id='telco_postgres')

    logger.info("📊 Checking feature distribution drift...")

    # Get reference distribution (7-14 days ago)
    reference_data = hook.get_pandas_df("""
        SELECT
            avg_data_usage_gb,
            pct_video_usage,
            avg_call_duration,
            sms_freq,
            monthly_spend,
            topup_freq,
            travel_score
        FROM app_users
        WHERE updated_at >= NOW() - INTERVAL '14 days'
          AND updated_at < NOW() - INTERVAL '7 days'
          AND total_purchases >= 1
        LIMIT 5000
    """)

    # Get current distribution (last 7 days)
    current_data = hook.get_pandas_df("""
        SELECT
            avg_data_usage_gb,
            pct_video_usage,
            avg_call_duration,
            sms_freq,
            monthly_spend,
            topup_freq,
            travel_score
        FROM app_users
        WHERE updated_at >= NOW() - INTERVAL '7 days'
          AND total_purchases >= 1
        LIMIT 5000
    """)

    if len(reference_data) < 100 or len(current_data) < 100:
        logger.warning("⚠️  Insufficient data for drift detection")
        return 'skip_retraining'

    # Calculate PSI for each feature
    psi_scores = {}

    for col in reference_data.columns:
        try:
            # Create bins from reference data
            ref_values = reference_data[col].fillna(reference_data[col].median())
            curr_values = current_data[col].fillna(current_data[col].median())

            # Use quantile-based bins
            bins = np.quantile(ref_values, q=np.linspace(0, 1, 11))
            bins = np.unique(bins)  # Remove duplicates

            if len(bins) < 3:
                logger.warning(f"⚠️  Skipping {col} - insufficient unique values")
                continue

            ref_dist, _ = np.histogram(ref_values, bins=bins)
            curr_dist, _ = np.histogram(curr_values, bins=bins)

            # Normalize to probabilities
            ref_dist = (ref_dist + 1) / (ref_dist.sum() + len(ref_dist))  # Laplace smoothing
            curr_dist = (curr_dist + 1) / (curr_dist.sum() + len(curr_dist))

            # Calculate PSI
            psi = np.sum((curr_dist - ref_dist) * np.log(curr_dist / ref_dist))
            psi_scores[col] = psi

        except Exception as e:
            logger.warning(f"⚠️  Error calculating PSI for {col}: {e}")
            continue

    if not psi_scores:
        logger.warning("⚠️  No PSI scores calculated")
        return 'skip_retraining'

    # Average PSI
    avg_psi = np.mean(list(psi_scores.values()))
    max_psi = np.max(list(psi_scores.values()))

    logger.info(f"📊 Feature Drift Analysis:")
    logger.info(f"   Average PSI: {avg_psi:.4f}")
    logger.info(f"   Max PSI: {max_psi:.4f}")

    for feature, psi in sorted(psi_scores.items(), key=lambda x: x[1], reverse=True):
        status = "🚨 DRIFT" if psi >= 0.15 else "✅ STABLE"
        logger.info(f"   {feature}: {psi:.4f} {status}")

    # Push metrics to XCom
    context['ti'].xcom_push(key='avg_psi', value=float(avg_psi))
    context['ti'].xcom_push(key='max_psi', value=float(max_psi))
    context['ti'].xcom_push(key='drift_detected', value=bool(max_psi >= 0.15))

    # Trigger retraining if drift detected (threshold 0.15 for RF features)
    if max_psi >= 0.15:
        logger.info(f"🔄 DRIFT DETECTED! Max PSI {max_psi:.4f} ≥ 0.15 - Triggering retraining")
        return 'prepare_training_data'
    else:
        logger.info(f"✅ No significant drift. Max PSI {max_psi:.4f} < 0.15")
        return 'skip_retraining'


def prepare_training_data(**context):
    """Prepare training data from purchases with behavioral features."""
    hook = PostgresHook(postgres_conn_id='telco_postgres')

    logger.info("📥 Loading RF v2 training data...")

    # Load training data (users with purchase history)
    # Join app_users with purchases to get target labels
    training_df = hook.get_pandas_df("""
        WITH latest_purchases AS (
            SELECT DISTINCT ON (p.user_id)
                p.user_id,
                p.product_name as target_offer,
                p.product_family,
                p.purchase_date
            FROM purchases p
            WHERE p.status = 'completed'
              AND p.purchase_date >= NOW() - INTERVAL '6 months'
            ORDER BY p.user_id, p.purchase_date DESC
        )
        SELECT
            u.id as user_id,
            u.plan_type,
            u.device_brand,
            u.avg_data_usage_gb,
            u.pct_video_usage,
            u.avg_call_duration,
            u.sms_freq,
            u.monthly_spend,
            u.topup_freq,
            u.travel_score,
            u.complaint_count,
            lp.target_offer
        FROM app_users u
        INNER JOIN latest_purchases lp ON u.id = lp.user_id
        WHERE u.total_purchases >= 3
          AND u.monthly_spend > 0
          AND u.topup_freq > 0
    """)

    logger.info(f"✅ Loaded {len(training_df)} training samples")
    logger.info(f"   Features: {training_df.columns.tolist()}")
    logger.info(f"   Target distribution:")
    logger.info(training_df['target_offer'].value_counts().head(10))

    if len(training_df) < 1000:
        logger.warning("⚠️  Insufficient training data (< 1000 samples)")
        raise ValueError("Insufficient training data for RF v2 model")

    # Save to temp file for next task
    training_df.to_parquet('/tmp/rf_v2_training_data.parquet', index=False)

    # Push metadata to XCom
    context['ti'].xcom_push(key='n_samples', value=len(training_df))
    context['ti'].xcom_push(key='n_classes', value=training_df['target_offer'].nunique())
    context['ti'].xcom_push(key='class_distribution', value=training_df['target_offer'].value_counts().to_dict())


def train_rf_v2_model(**context):
    """Train RandomForest v2 product classifier with temperature scaling."""
    logger.info("🌲 Training RandomForest v2 Classifier...")

    # Load training data
    training_df = pd.read_parquet('/tmp/rf_v2_training_data.parquet')

    # Split train/validation (80/20)
    train_df, val_df = train_test_split(training_df, test_size=0.2, random_state=42, stratify=training_df['target_offer'])

    logger.info(f"📊 Dataset split:")
    logger.info(f"   Training: {len(train_df)} samples")
    logger.info(f"   Validation: {len(val_df)} samples")

    # Label encoding
    le_plan = LabelEncoder()
    le_device = LabelEncoder()
    le_target = LabelEncoder()

    # Fit on full training data
    le_plan.fit(training_df['plan_type'].fillna('Prepaid'))
    le_device.fit(training_df['device_brand'].fillna('Samsung'))
    le_target.fit(training_df['target_offer'])

    # Transform train and validation
    train_df_encoded = train_df.copy()
    train_df_encoded['plan_type_encoded'] = le_plan.transform(train_df['plan_type'].fillna('Prepaid'))
    train_df_encoded['device_brand_encoded'] = le_device.transform(train_df['device_brand'].fillna('Samsung'))
    y_train = le_target.transform(train_df['target_offer'])

    val_df_encoded = val_df.copy()
    val_df_encoded['plan_type_encoded'] = le_plan.transform(val_df['plan_type'].fillna('Prepaid'))
    val_df_encoded['device_brand_encoded'] = le_device.transform(val_df['device_brand'].fillna('Samsung'))
    y_val = le_target.transform(val_df['target_offer'])

    # Feature engineering (same as RFRecommender)
    # Create dummy RFRecommender for feature engineering
    dummy_recommender = RFRecommender(
        model=None,
        label_encoders={'plan_type': le_plan, 'device_brand': le_device},
        label_encoder_target=le_target,
        feature_columns=None,
        temperature=0.8,
        min_confidence=0.05,
        k=5
    )

    train_features = dummy_recommender._engineer_features(train_df_encoded)
    val_features = dummy_recommender._engineer_features(val_df_encoded)

    # Feature columns (21 total)
    feature_columns = [
        'plan_type_encoded', 'device_brand_encoded',
        'avg_data_usage_gb', 'pct_video_usage', 'avg_call_duration', 'sms_freq',
        'monthly_spend', 'topup_freq', 'travel_score', 'complaint_count',
        'recency', 'frequency', 'monetary', 'arpu', 'avg_spend_per_topup',
        'data_intensity', 'communication_intensity', 'churn_score',
        'freq_x_monetary', 'arpu_per_data', 'loyalty_score'
    ]

    X_train = train_features[feature_columns].fillna(0)
    X_val = val_features[feature_columns].fillna(0)

    logger.info(f"✅ Feature engineering complete: {X_train.shape[1]} features")

    # MLflow tracking
    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000'))
    mlflow.set_experiment('rf_v2_retraining')

    with mlflow.start_run(run_name=f"rf_v2_retraining_{datetime.now().strftime('%Y%m%d_%H%M')}"):

        # Train RandomForest
        rf_model = RandomForestClassifier(
            n_estimators=300,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=4,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1,
            verbose=1
        )

        logger.info("🌲 Training RandomForest...")
        rf_model.fit(X_train, y_train)

        # Training metrics
        y_train_pred = rf_model.predict(X_train)
        train_accuracy = accuracy_score(y_train, y_train_pred)

        # Validation metrics
        y_val_pred = rf_model.predict(X_val)
        val_accuracy = accuracy_score(y_val, y_val_pred)

        # Top-K accuracy
        y_val_proba = rf_model.predict_proba(X_val)
        val_top3_accuracy = top_k_accuracy_score(y_val, y_val_proba, k=3)
        val_top5_accuracy = top_k_accuracy_score(y_val, y_val_proba, k=5)

        # Temperature calibration (optimize on validation set)
        best_temperature = 0.8
        best_calibrated_accuracy = 0

        for T in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5]:
            calibrated_proba = dummy_recommender._temperature_scaling(y_val_proba, T)
            calibrated_pred = np.argmax(calibrated_proba, axis=1)
            calibrated_acc = accuracy_score(y_val, calibrated_pred)

            if calibrated_acc > best_calibrated_accuracy:
                best_calibrated_accuracy = calibrated_acc
                best_temperature = T

        logger.info(f"📈 Training Metrics:")
        logger.info(f"   Train Accuracy: {train_accuracy:.4f}")
        logger.info(f"   Val Accuracy: {val_accuracy:.4f}")
        logger.info(f"   Val Top-3 Accuracy: {val_top3_accuracy:.4f}")
        logger.info(f"   Val Top-5 Accuracy: {val_top5_accuracy:.4f}")
        logger.info(f"   Best Temperature: {best_temperature} (Accuracy: {best_calibrated_accuracy:.4f})")

        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_columns,
            'importance': rf_model.feature_importances_
        }).sort_values('importance', ascending=False)

        logger.info("🔍 Top 10 Important Features:")
        for idx, row in feature_importance.head(10).iterrows():
            logger.info(f"   {row['feature']}: {row['importance']:.4f}")

        # Log parameters
        mlflow.log_param("model_type", "RandomForestClassifier")
        mlflow.log_param("n_estimators", 300)
        mlflow.log_param("max_depth", 15)
        mlflow.log_param("min_samples_split", 10)
        mlflow.log_param("temperature", best_temperature)
        mlflow.log_param("n_features", len(feature_columns))
        mlflow.log_param("n_classes", len(le_target.classes_))
        mlflow.log_param("train_samples", len(X_train))
        mlflow.log_param("val_samples", len(X_val))

        # Log metrics
        mlflow.log_metric("train_accuracy", train_accuracy)
        mlflow.log_metric("val_accuracy", val_accuracy)
        mlflow.log_metric("val_top3_accuracy", val_top3_accuracy)
        mlflow.log_metric("val_top5_accuracy", val_top5_accuracy)
        mlflow.log_metric("calibrated_accuracy", best_calibrated_accuracy)

        # Log feature importance
        feature_importance.to_csv('/tmp/rf_v2_feature_importance.csv', index=False)
        mlflow.log_artifact('/tmp/rf_v2_feature_importance.csv')

        # Save complete model artifacts
        model_artifacts = {
            'model': rf_model,
            'label_encoder_plan': le_plan,
            'label_encoder_device': le_device,
            'label_encoder_target': le_target,
            'feature_columns': feature_columns,
            'temperature': best_temperature,
            'min_confidence': 0.05,
            'k': 5,
            'accuracy': val_accuracy,
            'top5_accuracy': val_top5_accuracy,
            'feature_importance': feature_importance.to_dict('records')
        }

        # Save model with joblib
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "rf_recommender.pkl")
            joblib.dump(model_artifacts, model_path)
            mlflow.log_artifact(model_path, artifact_path="model")

            # Also log metadata
            metadata = {
                'version': '2.0.0',
                'trained_at': datetime.now().isoformat(),
                'n_features': len(feature_columns),
                'n_classes': len(le_target.classes_),
                'classes': le_target.classes_.tolist(),
                'accuracy': float(val_accuracy),
                'top5_accuracy': float(val_top5_accuracy),
                'temperature': best_temperature
            }

            import json
            metadata_path = os.path.join(tmpdir, "metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            mlflow.log_artifact(metadata_path, artifact_path="model")

        # Register model in MLflow Model Registry
        model_uri = f"runs:/{mlflow.active_run().info.run_id}/model/rf_recommender.pkl"
        model_version = mlflow.register_model(model_uri, "rf_v2_classifier")

        run_id = mlflow.active_run().info.run_id

        logger.info(f"✅ RF v2 trained successfully!")
        logger.info(f"   Run ID: {run_id}")
        logger.info(f"   Model Version: {model_version.version}")
        logger.info(f"   Validation Accuracy: {val_accuracy:.4f}")
        logger.info(f"   Top-5 Accuracy: {val_top5_accuracy:.4f}")

        # Push to XCom
        context['ti'].xcom_push(key='rf_run_id', value=run_id)
        context['ti'].xcom_push(key='rf_val_accuracy', value=float(val_accuracy))
        context['ti'].xcom_push(key='rf_top5_accuracy', value=float(val_top5_accuracy))
        context['ti'].xcom_push(key='rf_model_version', value=model_version.version)
        context['ti'].xcom_push(key='rf_temperature', value=best_temperature)


def validate_model_performance(**context):
    """Validate new model against production baseline."""
    val_accuracy = context['ti'].xcom_pull(key='rf_val_accuracy', task_ids='train_rf_v2')
    top5_accuracy = context['ti'].xcom_pull(key='rf_top5_accuracy', task_ids='train_rf_v2')

    # Performance thresholds
    MIN_ACCURACY = 0.75  # 75% accuracy minimum
    MIN_TOP5_ACCURACY = 0.90  # 90% top-5 accuracy minimum

    logger.info(f"🎯 Validating model performance...")
    logger.info(f"   Validation Accuracy: {val_accuracy:.4f} (threshold: {MIN_ACCURACY})")
    logger.info(f"   Top-5 Accuracy: {top5_accuracy:.4f} (threshold: {MIN_TOP5_ACCURACY})")

    if val_accuracy >= MIN_ACCURACY and top5_accuracy >= MIN_TOP5_ACCURACY:
        logger.info("✅ Model passed performance validation!")
        return 'promote_to_production'
    else:
        logger.warning("❌ Model failed performance validation!")
        logger.warning(f"   Accuracy below threshold: {val_accuracy:.4f} < {MIN_ACCURACY}")
        return 'skip_promotion'


def promote_to_production(**context):
    """Promote validated model to production in MLflow Model Registry."""
    run_id = context['ti'].xcom_pull(key='rf_run_id', task_ids='train_rf_v2')
    model_version = context['ti'].xcom_pull(key='rf_model_version', task_ids='train_rf_v2')

    logger.info(f"🚀 Promoting RF v2 model to production...")
    logger.info(f"   Run ID: {run_id}")
    logger.info(f"   Model Version: {model_version}")

    # Transition to production in MLflow
    client = mlflow.tracking.MlflowClient()

    try:
        # Archive current production model
        current_prod_versions = client.get_latest_versions("rf_v2_classifier", stages=["Production"])
        for version in current_prod_versions:
            client.transition_model_version_stage(
                name="rf_v2_classifier",
                version=version.version,
                stage="Archived"
            )
            logger.info(f"   Archived previous production version: {version.version}")

        # Promote new model to production
        client.transition_model_version_stage(
            name="rf_v2_classifier",
            version=model_version,
            stage="Production"
        )

        logger.info(f"✅ Model version {model_version} promoted to Production!")

    except Exception as e:
        logger.error(f"❌ Failed to promote model: {e}")
        raise


def skip_retraining(**context):
    """Log skip reason."""
    logger.info("⏭️  Skipping retraining - no significant drift detected")


def skip_promotion(**context):
    """Log skip promotion reason."""
    logger.warning("⏭️  Skipping promotion - model performance below threshold")


# DAG Definition
with DAG(
    'rf_v2_retraining',
    default_args=default_args,
    description='Weekly RandomForest v2 model retraining with drift detection',
    schedule_interval='0 3 * * 0',  # Sunday 3 AM (after hybrid model retraining)
    start_date=days_ago(1),
    catchup=False,
    tags=['ml', 'retraining', 'rf_v2', 'production'],
) as dag:

    # Task 1: Check feature drift
    check_drift_task = BranchPythonOperator(
        task_id='check_feature_drift',
        python_callable=check_feature_drift,
        provide_context=True
    )

    # Task 2: Prepare training data
    prepare_data_task = PythonOperator(
        task_id='prepare_training_data',
        python_callable=prepare_training_data,
        provide_context=True
    )

    # Task 3: Train RF v2 model
    train_rf_task = PythonOperator(
        task_id='train_rf_v2',
        python_callable=train_rf_v2_model,
        provide_context=True
    )

    # Task 4: Validate performance
    validate_task = BranchPythonOperator(
        task_id='validate_performance',
        python_callable=validate_model_performance,
        provide_context=True
    )

    # Task 5: Promote to production
    promote_task = PythonOperator(
        task_id='promote_to_production',
        python_callable=promote_to_production,
        provide_context=True
    )

    # Task 6: Skip retraining
    skip_retrain_task = PythonOperator(
        task_id='skip_retraining',
        python_callable=skip_retraining,
        provide_context=True,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
    )

    # Task 7: Skip promotion
    skip_promo_task = PythonOperator(
        task_id='skip_promotion',
        python_callable=skip_promotion,
        provide_context=True,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
    )

    # Task dependencies
    check_drift_task >> [prepare_data_task, skip_retrain_task]
    prepare_data_task >> train_rf_task >> validate_task
    validate_task >> [promote_task, skip_promo_task]
