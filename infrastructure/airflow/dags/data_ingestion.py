"""
Data Ingestion Monitoring DAG
Sprint 1: Infrastructure & Streaming Foundation

Monitors new data ingestion every 4 hours and triggers feature computation
Event-driven architecture: ingestion detection → feature computation trigger
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime, timedelta
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Default arguments
default_args = {
    'owner': 'telco-ml-team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}


def check_new_data(**context):
    """
    Check if new data has been ingested since last check

    Returns:
        str: 'trigger_features' if new data exists, 'skip_trigger' otherwise
    """
    hook = PostgresHook(postgres_conn_id='telco_postgres')

    # Check for new transactions in last 4 hours
    query = """
        SELECT COUNT(*) as new_count,
               MAX(created_at) as latest_timestamp
        FROM transactions
        WHERE created_at > NOW() - INTERVAL '4 hours'
    """

    result = hook.get_first(query)
    new_count = result[0] if result else 0
    latest_timestamp = result[1] if result and len(result) > 1 else None

    logger.info(f"📊 New records in last 4 hours: {new_count}")
    logger.info(f"⏰ Latest timestamp: {latest_timestamp}")

    # Push to XCom for downstream tasks
    context['task_instance'].xcom_push(key='new_record_count', value=new_count)
    context['task_instance'].xcom_push(key='latest_timestamp', value=str(latest_timestamp))

    # Branch based on new data availability
    if new_count > 0:
        logger.info("✅ New data detected - triggering feature computation")
        return 'log_detection'
    else:
        logger.info("📭 No new data - skipping feature computation")
        return 'skip_trigger'


def log_data_detection(**context):
    """Log data detection details"""
    ti = context['task_instance']
    new_count = ti.xcom_pull(key='new_record_count', task_ids='check_new_data')
    latest_timestamp = ti.xcom_pull(key='latest_timestamp', task_ids='check_new_data')

    logger.info(f"🔔 Data Detection Summary:")
    logger.info(f"  - New Records: {new_count}")
    logger.info(f"  - Latest Timestamp: {latest_timestamp}")
    logger.info(f"  - Check Time: {datetime.now()}")


def get_ingestion_stats(**context):
    """Get detailed ingestion statistics"""
    hook = PostgresHook(postgres_conn_id='telco_postgres')

    # Get batch statistics
    query = """
        SELECT
            batch_id,
            batch_start_time,
            batch_end_time,
            records_processed,
            records_failed,
            status
        FROM ingestion_batches
        WHERE batch_start_time > NOW() - INTERVAL '4 hours'
        ORDER BY batch_start_time DESC
    """

    batches = hook.get_records(query)

    if batches:
        logger.info(f"📦 Recent Ingestion Batches: {len(batches)}")
        for batch in batches:
            batch_id, start, end, processed, failed, status = batch
            logger.info(f"  Batch {batch_id[:8]}...: {processed} processed, {failed} failed, status={status}")
    else:
        logger.info("📭 No recent batches found")

    return len(batches)


def skip_trigger_task(**context):
    """Task executed when no new data is detected"""
    logger.info("⏭️ Skipping feature computation - no new data detected")


# Define DAG
with DAG(
    dag_id='data_ingestion_monitor',
    default_args=default_args,
    description='Monitor new data ingestion and trigger feature engineering',
    schedule_interval='0 */4 * * *',  # Every 4 hours
    start_date=datetime(2024, 10, 10),
    catchup=False,
    tags=['ingestion', 'monitoring', 'sprint-1'],
) as dag:

    # Task 1: Check for new data (branching)
    check_data = BranchPythonOperator(
        task_id='check_new_data',
        python_callable=check_new_data,
        provide_context=True,
    )

    # Task 2a: Log detection (when new data found)
    log_detection = PythonOperator(
        task_id='log_detection',
        python_callable=log_data_detection,
        provide_context=True,
    )

    # Task 2b: Skip trigger (when no new data)
    skip_trigger = PythonOperator(
        task_id='skip_trigger',
        python_callable=skip_trigger_task,
        provide_context=True,
    )

    # Task 3: Get ingestion statistics
    get_stats = PythonOperator(
        task_id='get_ingestion_stats',
        python_callable=get_ingestion_stats,
        provide_context=True,
        trigger_rule='none_failed',  # Run if log_detection succeeds
    )

    # Task 4: Update monitoring metrics
    update_metrics = PostgresOperator(
        task_id='update_monitoring_metrics',
        postgres_conn_id='telco_postgres',
        sql="""
            -- Create monitoring table if not exists
            CREATE TABLE IF NOT EXISTS ingestion_monitoring (
                check_time TIMESTAMP PRIMARY KEY,
                new_records INTEGER,
                batches_processed INTEGER,
                feature_trigger_status VARCHAR(20)
            );

            -- Insert monitoring record
            INSERT INTO ingestion_monitoring (check_time, new_records, batches_processed, feature_trigger_status)
            VALUES (NOW(), {{ task_instance.xcom_pull(key='new_record_count', task_ids='check_new_data') }}, 1, 'triggered')
            ON CONFLICT (check_time) DO NOTHING;
        """,
        trigger_rule='none_failed',
    )

    # Task 5: Trigger feature engineering DAG
    trigger_features = TriggerDagRunOperator(
        task_id='trigger_feature_computation',
        trigger_dag_id='feature_engineering',
        conf={'triggered_by': 'data_ingestion_monitor', 'trigger_time': '{{ ts }}'},
        wait_for_completion=False,
        trigger_rule='none_failed',
    )

    # Define task dependencies
    check_data >> [log_detection, skip_trigger]
    log_detection >> get_stats >> update_metrics >> trigger_features
