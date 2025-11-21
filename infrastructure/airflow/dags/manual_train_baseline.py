"""
Manual Baseline Model Training DAG
====================================

Simple DAG for manually triggering baseline model training.
Can be run on-demand from Airflow UI.

Features:
- Loads customer data from CSV
- Creates synthetic transactions
- Trains TopPopular baseline model
- Registers to MLflow with Production stage

Schedule: None (manual trigger only)
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path

# Add backend to Python path
backend_path = '/opt/airflow/backend'
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

default_args = {
    'owner': 'ml-team',
    'depends_on_past': False,
    'email': ['ml-alerts@telco.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=3),
}


def run_training_script(**context):
    """
    Execute the training script.

    This function runs the train_demo_model.py script
    which handles all training logic.
    """
    import subprocess
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting baseline model training...")

    # Path to training script
    script_path = '/opt/airflow/services/utils/tests/scripts/train_demo_model.py'

    # Check if script exists
    if not Path(script_path).exists():
        raise FileNotFoundError(f"Training script not found: {script_path}")

    # Set environment variables
    env = os.environ.copy()
    env['BACKEND_PATH'] = '/opt/airflow/backend'
    env['DATA_SOURCE_PATH'] = '/opt/airflow/ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv'
    env['MLFLOW_TRACKING_URI'] = os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000')

    logger.info(f"Environment: BACKEND_PATH={env['BACKEND_PATH']}")
    logger.info(f"Environment: DATA_SOURCE_PATH={env['DATA_SOURCE_PATH']}")
    logger.info(f"Environment: MLFLOW_TRACKING_URI={env['MLFLOW_TRACKING_URI']}")

    try:
        # Run training script
        result = subprocess.run(
            ['python', script_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )

        # Log output
        logger.info("=== Training Script Output ===")
        logger.info(result.stdout)

        if result.stderr:
            logger.warning("=== Training Script Errors ===")
            logger.warning(result.stderr)

        # Check exit code
        if result.returncode != 0:
            raise RuntimeError(f"Training script failed with exit code {result.returncode}")

        logger.info("✅ Training completed successfully")

        # Push metrics to XCom for monitoring
        context['task_instance'].xcom_push(key='training_status', value='success')
        context['task_instance'].xcom_push(key='model_name', value='baseline-recommender')

        return {
            'status': 'success',
            'model_name': 'baseline-recommender',
            'stage': 'Production'
        }

    except subprocess.TimeoutExpired:
        logger.error("❌ Training script timed out (5 minutes)")
        raise
    except Exception as e:
        logger.error(f"❌ Training failed: {str(e)}")
        raise


def validate_model(**context):
    """
    Validate that model was registered successfully in MLflow.
    """
    import mlflow
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Validating model registration in MLflow...")

    # Set MLflow tracking URI
    mlflow_uri = os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000')
    mlflow.set_tracking_uri(mlflow_uri)

    try:
        client = mlflow.tracking.MlflowClient()

        # Check if model exists in Production stage
        model_name = "baseline-recommender"
        versions = client.get_latest_versions(model_name, stages=["Production"])

        if not versions:
            raise ValueError(f"No Production version found for model: {model_name}")

        latest_version = versions[0]
        logger.info(f"✅ Model validated: {model_name} v{latest_version.version} (Production)")

        # Push to XCom
        context['task_instance'].xcom_push(key='model_version', value=latest_version.version)

        return {
            'model_name': model_name,
            'version': latest_version.version,
            'stage': 'Production'
        }

    except Exception as e:
        logger.error(f"❌ Model validation failed: {str(e)}")
        raise


def notify_completion(**context):
    """
    Send completion notification.
    """
    import logging

    logger = logging.getLogger(__name__)

    # Get results from previous tasks
    training_result = context['task_instance'].xcom_pull(task_ids='train_baseline_model')
    validation_result = context['task_instance'].xcom_pull(task_ids='validate_model')

    logger.info("=" * 60)
    logger.info("🎉 Baseline Model Training Pipeline Complete")
    logger.info("=" * 60)
    logger.info(f"Training Status: {training_result['status']}")
    logger.info(f"Model: {validation_result['model_name']}")
    logger.info(f"Version: {validation_result['version']}")
    logger.info(f"Stage: {validation_result['stage']}")
    logger.info("=" * 60)

    # TODO: Send Slack/email notification
    # For now, just log
    return {
        'pipeline_status': 'completed',
        'timestamp': datetime.now().isoformat()
    }


# Create DAG
with DAG(
    'manual_train_baseline',
    default_args=default_args,
    description='Manual baseline model training pipeline',
    schedule_interval=None,  # Manual trigger only
    start_date=days_ago(1),
    catchup=False,
    tags=['ml', 'training', 'baseline', 'manual'],
) as dag:

    # Task 1: Train baseline model
    train_task = PythonOperator(
        task_id='train_baseline_model',
        python_callable=run_training_script,
        provide_context=True,
    )

    # Task 2: Validate model registration
    validate_task = PythonOperator(
        task_id='validate_model',
        python_callable=validate_model,
        provide_context=True,
    )

    # Task 3: Send notification
    notify_task = PythonOperator(
        task_id='notify_completion',
        python_callable=notify_completion,
        provide_context=True,
    )

    # Define task dependencies
    train_task >> validate_task >> notify_task
