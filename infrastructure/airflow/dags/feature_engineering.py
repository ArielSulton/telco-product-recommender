"""
Feature Engineering DAG
Sprint 1: Infrastructure & Streaming Foundation

Computes real-time features (RFM, ARPU, usage) when triggered by data ingestion
Event-driven: triggered by data_ingestion_monitor DAG
Workflow: compute features → cache to Redis → notify FastAPI
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.operators.http import SimpleHttpOperator
from datetime import datetime, timedelta
import logging
import json

# Configure logging
logger = logging.getLogger(__name__)

# Default arguments
default_args = {
    'owner': 'telco-ml-team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=3),
}


def compute_rfm_features(**context):
    """
    Compute Recency, Frequency, Monetary features for all users

    RFM Analysis:
    - Recency: Days since last purchase
    - Frequency: Total number of purchases
    - Monetary: Total revenue from user
    """
    hook = PostgresHook(postgres_conn_id='telco_postgres')

    logger.info("📊 Computing RFM features...")

    # Compute RFM metrics
    rfm_query = """
        WITH user_rfm AS (
            SELECT
                u.user_id,
                COALESCE(
                    EXTRACT(DAY FROM (NOW() - MAX(t.transaction_date))),
                    365
                )::INTEGER AS recency,
                COALESCE(COUNT(t.transaction_id), 0)::INTEGER AS frequency,
                COALESCE(SUM(t.amount), 0)::DECIMAL(10,2) AS monetary,
                MAX(t.transaction_date) AS last_purchase_date,
                COALESCE(AVG(t.amount), 0)::DECIMAL(10,2) AS avg_transaction_value
            FROM users u
            LEFT JOIN transactions t ON u.user_id = t.user_id AND t.status = 'completed'
            GROUP BY u.user_id
        )
        INSERT INTO user_features (user_id, recency, frequency, monetary, last_purchase_date, avg_transaction_value, updated_at)
        SELECT
            user_id,
            recency,
            frequency,
            monetary,
            last_purchase_date,
            avg_transaction_value,
            NOW()
        FROM user_rfm
        ON CONFLICT (user_id)
        DO UPDATE SET
            recency = EXCLUDED.recency,
            frequency = EXCLUDED.frequency,
            monetary = EXCLUDED.monetary,
            last_purchase_date = EXCLUDED.last_purchase_date,
            avg_transaction_value = EXCLUDED.avg_transaction_value,
            updated_at = NOW();
    """

    conn = hook.get_conn()
    cursor = conn.cursor()
    cursor.execute(rfm_query)
    affected_rows = cursor.rowcount
    conn.commit()
    cursor.close()

    logger.info(f"✅ RFM features computed for {affected_rows} users")

    # Push metrics to XCom
    context['task_instance'].xcom_push(key='rfm_users_processed', value=affected_rows)

    return affected_rows


def compute_arpu_buckets(**context):
    """
    Compute ARPU (Average Revenue Per User) buckets

    ARPU Segments:
    - Low: < 50,000
    - Medium: 50,000 - 100,000
    - High: 100,000 - 200,000
    - Premium: > 200,000
    """
    hook = PostgresHook(postgres_conn_id='telco_postgres')

    logger.info("💰 Computing ARPU buckets...")

    arpu_query = """
        WITH user_arpu AS (
            SELECT
                user_id,
                monetary / GREATEST(frequency, 1) AS arpu
            FROM user_features
            WHERE frequency > 0
        )
        UPDATE user_features uf
        SET
            arpu_bucket = CASE
                WHEN ua.arpu < 50000 THEN 'low'
                WHEN ua.arpu < 100000 THEN 'medium'
                WHEN ua.arpu < 200000 THEN 'high'
                ELSE 'premium'
            END,
            updated_at = NOW()
        FROM user_arpu ua
        WHERE uf.user_id = ua.user_id;
    """

    conn = hook.get_conn()
    cursor = conn.cursor()
    cursor.execute(arpu_query)
    affected_rows = cursor.rowcount
    conn.commit()
    cursor.close()

    logger.info(f"✅ ARPU buckets computed for {affected_rows} users")

    # Get ARPU distribution
    distribution_query = """
        SELECT arpu_bucket, COUNT(*) as user_count
        FROM user_features
        WHERE arpu_bucket IS NOT NULL
        GROUP BY arpu_bucket
        ORDER BY user_count DESC;
    """

    distribution = hook.get_records(distribution_query)
    logger.info(f"📊 ARPU Distribution:")
    for bucket, count in distribution:
        logger.info(f"  - {bucket}: {count} users")

    context['task_instance'].xcom_push(key='arpu_users_processed', value=affected_rows)

    return affected_rows


def compute_rfm_scores(**context):
    """
    Compute RFM scores (quintile-based scoring)

    Scores range from 1-5 for each dimension:
    - R score: Lower recency = higher score (5 = recent)
    - F score: Higher frequency = higher score (5 = frequent)
    - M score: Higher monetary = higher score (5 = high value)
    """
    hook = PostgresHook(postgres_conn_id='telco_postgres')

    logger.info("🎯 Computing RFM scores...")

    rfm_score_query = """
        WITH rfm_quintiles AS (
            SELECT
                user_id,
                recency,
                frequency,
                monetary,
                -- R score: inverse (lower recency = higher score)
                NTILE(5) OVER (ORDER BY recency DESC) AS r_score,
                -- F score: direct (higher frequency = higher score)
                NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
                -- M score: direct (higher monetary = higher score)
                NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
            FROM user_features
            WHERE frequency > 0
        )
        UPDATE user_features uf
        SET
            rfm_score = CONCAT(rq.r_score, rq.f_score, rq.m_score),
            updated_at = NOW()
        FROM rfm_quintiles rq
        WHERE uf.user_id = rq.user_id;
    """

    conn = hook.get_conn()
    cursor = conn.cursor()
    cursor.execute(rfm_score_query)
    affected_rows = cursor.rowcount
    conn.commit()
    cursor.close()

    logger.info(f"✅ RFM scores computed for {affected_rows} users")

    context['task_instance'].xcom_push(key='rfm_scores_processed', value=affected_rows)

    return affected_rows


def cache_hot_features(**context):
    """
    Cache frequently accessed features to Redis

    Caches top users by frequency to Redis for fast retrieval
    Cache structure: user_features:{user_id} -> hash of features
    """
    import redis
    import os

    hook = PostgresHook(postgres_conn_id='telco_postgres')

    # Connect to Redis
    redis_host = os.getenv('REDIS_HOST', 'redis')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_db = int(os.getenv('REDIS_DB', '0'))

    logger.info(f"📦 Connecting to Redis at {redis_host}:{redis_port}")

    try:
        r = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        r.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise

    # Get top users (active users with recent purchases)
    query = """
        SELECT
            user_id,
            recency,
            frequency,
            monetary,
            arpu_bucket,
            rfm_score,
            churn_score,
            segment_id
        FROM user_features
        WHERE frequency > 0
        ORDER BY frequency DESC, recency ASC
        LIMIT 10000;
    """

    users = hook.get_records(query)

    logger.info(f"🔄 Caching {len(users)} user feature sets to Redis...")

    cached_count = 0
    failed_count = 0

    for user in users:
        try:
            user_id = str(user[0])
            feature_hash = {
                'recency': user[1],
                'frequency': user[2],
                'monetary': float(user[3]) if user[3] else 0.0,
                'arpu_bucket': user[4] or 'low',
                'rfm_score': user[5] or '111',
                'churn_score': float(user[6]) if user[6] else 0.0,
                'segment_id': user[7] if user[7] is not None else -1,
                'cached_at': datetime.now().isoformat()
            }

            # Set hash with expiration (1 hour)
            r.hset(f"user_features:{user_id}", mapping=feature_hash)
            r.expire(f"user_features:{user_id}", 3600)

            cached_count += 1

        except Exception as e:
            logger.warning(f"⚠️ Failed to cache user {user_id}: {e}")
            failed_count += 1
            continue

    logger.info(f"✅ Cached {cached_count} users to Redis ({failed_count} failed)")

    # Set cache metadata
    r.set('feature_cache:last_update', datetime.now().isoformat())
    r.set('feature_cache:user_count', cached_count)

    context['task_instance'].xcom_push(key='cached_users', value=cached_count)

    return cached_count


def notify_fastapi_webhook(**context):
    """
    Prepare notification payload for FastAPI

    Returns:
        dict: Notification payload with feature computation metrics
    """
    ti = context['task_instance']
    dag_run = context.get('dag_run')
    run_id = dag_run.run_id if dag_run else "manual"
    dag_id = dag_run.dag_id if dag_run else "feature_engineering"

    # Gather metrics from upstream tasks
    rfm_users = ti.xcom_pull(key='rfm_users_processed', task_ids='compute_rfm')
    arpu_users = ti.xcom_pull(key='arpu_users_processed', task_ids='compute_arpu')
    rfm_scores = ti.xcom_pull(key='rfm_scores_processed', task_ids='compute_rfm_scores')
    cached_users = ti.xcom_pull(key='cached_users', task_ids='cache_to_redis')

    # Build payload that matches FastAPI schema (batch_id, num_users, metadata)
    batch_id = f"{dag_id}_{run_id}"
    num_users = cached_users or rfm_users or 0

    payload = {
        'batch_id': batch_id,
        'num_users': num_users,
        'timestamp': datetime.utcnow().isoformat(),
        'metadata': {
            'source': 'airflow',
            'dag_id': dag_id,
            'run_id': run_id,
            'metrics': {
                'rfm_users_processed': rfm_users,
                'arpu_users_processed': arpu_users,
                'rfm_scores_processed': rfm_scores,
                'cached_users': cached_users
            }
        }
    }

    logger.info(f"📨 Notification payload: {json.dumps(payload, indent=2)}")

    # Push to XCom for HTTP operator
    context['task_instance'].xcom_push(key='notification_payload', value=json.dumps(payload))

    return payload


# Define DAG
with DAG(
    dag_id='feature_engineering',
    default_args=default_args,
    description='Compute real-time features (RFM, ARPU, usage) and cache to Redis',
    schedule_interval=None,  # Triggered by data_ingestion_monitor
    start_date=datetime(2024, 10, 10),
    catchup=False,
    tags=['features', 'ml', 'sprint-1'],
) as dag:

    # Task 1: Compute RFM features
    compute_rfm = PythonOperator(
        task_id='compute_rfm',
        python_callable=compute_rfm_features,
        provide_context=True,
    )

    # Task 2: Compute ARPU buckets
    compute_arpu = PythonOperator(
        task_id='compute_arpu',
        python_callable=compute_arpu_buckets,
        provide_context=True,
    )

    # Task 3: Compute RFM scores
    compute_rfm_scores_task = PythonOperator(
        task_id='compute_rfm_scores',
        python_callable=compute_rfm_scores,
        provide_context=True,
    )

    # Task 4: Cache features to Redis
    cache_features = PythonOperator(
        task_id='cache_to_redis',
        python_callable=cache_hot_features,
        provide_context=True,
    )

    # Task 5: Prepare notification
    prepare_notification = PythonOperator(
        task_id='prepare_notification',
        python_callable=notify_fastapi_webhook,
        provide_context=True,
    )

    # Task 6: Notify FastAPI via webhook
    notify_api = SimpleHttpOperator(
        task_id='notify_fastapi',
        http_conn_id='fastapi_backend',
        endpoint='/api/v1/webhooks/features-updated',
        method='POST',
        headers={"Content-Type": "application/json"},
        data="{{ task_instance.xcom_pull(key='notification_payload', task_ids='prepare_notification') }}",
        response_check=lambda response: response.status_code in [200, 201, 204],
        extra_options={'timeout': 10},
        # Continue even if webhook fails (non-critical)
        trigger_rule='none_failed',
    )

    # Define task dependencies
    # Compute features in parallel, then cache, then notify
    [compute_rfm, compute_arpu] >> compute_rfm_scores_task >> cache_features >> prepare_notification >> notify_api
