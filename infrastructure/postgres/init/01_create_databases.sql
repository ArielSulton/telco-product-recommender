-- ============================================
-- Create Additional Databases for MLflow and Airflow
-- ============================================
-- This script runs before other init scripts (00_ prefix)
-- Creates databases needed by MLflow and Airflow services

-- Create MLflow database for experiment tracking
CREATE DATABASE mlflow;

-- Create Airflow database for workflow orchestration
CREATE DATABASE airflow;

-- Grant privileges to postgres user (already owner, but explicit)
GRANT ALL PRIVILEGES ON DATABASE mlflow TO postgres;
GRANT ALL PRIVILEGES ON DATABASE airflow TO postgres;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Additional databases created: mlflow, airflow';
END $$;
